"""
Retrieval service with hybrid search (vector + BM25/Full-text).
Implements Reciprocal Rank Fusion for combining results.
Supports multi-granularity retrieval (small + large chunks).
"""

import logging
import re
from typing import List, Tuple, Optional, Set
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk
from app.services.embedding import embedding_service
from app.core.config import settings

_CHUNK_COLS = (
    "c.id, c.document_id, c.content, c.page_number, c.chunk_index, "
    "c.token_count, c.chunk_type, c.bbox_x0, c.bbox_y0, c.bbox_x1, c.bbox_y1, "
    "c.caption, c.image_key"
)


def _row_to_chunk(row) -> Chunk:
    def _num(val):
        return val if isinstance(val, (int, float)) else None

    chunk_type = getattr(row, "chunk_type", None)
    if not isinstance(chunk_type, str) or not chunk_type:
        chunk_type = "text"
    return Chunk(
        id=row.id,
        document_id=row.document_id,
        content=row.content,
        page_number=row.page_number,
        chunk_index=row.chunk_index,
        token_count=getattr(row, "token_count", 0) or 0,
        chunk_type=chunk_type,
        bbox_x0=_num(getattr(row, "bbox_x0", None)),
        bbox_y0=_num(getattr(row, "bbox_y0", None)),
        bbox_x1=_num(getattr(row, "bbox_x1", None)),
        bbox_y1=_num(getattr(row, "bbox_y1", None)),
        caption=getattr(row, "caption", None) if isinstance(getattr(row, "caption", None), str) else None,
        image_key=getattr(row, "image_key", None) if isinstance(getattr(row, "image_key", None), str) else None,
    )

logger = logging.getLogger(__name__)

# Token count thresholds for granularity classification
SMALL_CHUNK_THRESHOLD = 500

# Keyword-heavy query patterns that benefit from higher BM25 weight
_KEYWORD_TRIGGERS = [
    "list of", "all the", "names of", "steps to", "parts of",
    "symptoms of", "types of", "examples of", "kinds of",
    "what are", "who are", "where is", "when did", "number of",
    "calculate", "formula", "equation",
]
# Semantic-heavy patterns that benefit from higher semantic weight
_SEMANTIC_TRIGGERS = [
    "explain", "describe", "how does", "why does", "compare",
    "difference between", "relationship between", "meaning of",
    "overview of", "summary of", "analysis of",
]


def _classify_query_for_hybrid(query: str) -> str:
    """Classify query for hybrid search weight selection."""
    q = query.lower()
    kw_score = sum(1 for t in _KEYWORD_TRIGGERS if t in q)
    sem_score = sum(1 for t in _SEMANTIC_TRIGGERS if t in q)
    if kw_score > sem_score:
        return "keyword_heavy"
    if sem_score > kw_score:
        return "semantic_heavy"
    return "balanced"


_IDENT = re.compile(r"\b(?:SKU-[A-Z0-9-]+|FIG-[A-Z0-9-]+|site\s+\d+)\b", re.I)

_VISUAL_TRIGGERS = (
    "figure", "diagram", "image", "photo", "chart", "plot", "picture",
    "illustration", "fig-", "fig ", "what does fig", "screenshot", "visual",
)


def query_wants_visual(query: str) -> bool:
    q = (query or "").lower()
    return any(t in q for t in _VISUAL_TRIGGERS)


def _get_adaptive_semantic_weight(query: str, fallback: float) -> float:
    """
    Return an adaptive semantic weight based on query type.
    Keyword-heavy queries need more BM25; semantic queries need more vector search.
    """
    qtype = _classify_query_for_hybrid(query)
    if qtype == "keyword_heavy":
        return max(0.4, fallback - 0.2)
    if qtype == "semantic_heavy":
        return min(0.85, fallback + 0.1)
    return fallback


class RetrievalService:
    
    def __init__(self, embedding_svc=None):
        self._embedding_service = embedding_svc or embedding_service
    
    async def semantic_search_by_embedding(
        self,
        db: AsyncSession,
        embedding: List[float],
        top_k: int = 5,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
    ) -> List[Tuple[Chunk, float]]:
        try:
            emb_str = self._format_embedding(embedding)
            params: dict = {"embedding": emb_str, "top_k": top_k}
            where_extra = ""
            if workspace_id:
                where_extra = " AND d.workspace_id = :workspace_id"
                params["workspace_id"] = workspace_id
            if user_id:
                where_extra += " AND d.user_id = :user_id"
                params["user_id"] = user_id
            if document_ids:
                where_extra += " AND d.id IN :document_ids"
                params["document_ids"] = document_ids
            sql = text(f"""
                SELECT {_CHUNK_COLS},
                       1 - (c.embedding <=> CAST(:embedding AS vector)) as similarity
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.status = 'ready' AND c.embedding IS NOT NULL{where_extra}
                ORDER BY c.embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
            """)
            if document_ids:
                sql = sql.bindparams(bindparam("document_ids", expanding=True))
            result = await db.execute(sql, params)
            rows = result.fetchall()
            chunks = []
            for row in rows:
                chunks.append((_row_to_chunk(row), float(row.similarity) if row.similarity else 0.0))
            return chunks
        except Exception as e:
            logger.error(f"Semantic search by embedding failed: {e}")
            raise

    async def semantic_search(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 5,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
    ) -> List[Tuple[Chunk, float]]:
        try:
            query_embedding = await self._embedding_service.embed_text(query)
            params: dict = {
                "embedding": self._format_embedding(query_embedding),
                "top_k": top_k,
            }
            where_extra = ""
            if workspace_id:
                where_extra = " AND d.workspace_id = :workspace_id"
                params["workspace_id"] = workspace_id
            if user_id:
                where_extra += " AND d.user_id = :user_id"
                params["user_id"] = user_id
            if document_ids:
                where_extra += " AND d.id IN :document_ids"
                params["document_ids"] = document_ids
            sql = text(f"""
                SELECT {_CHUNK_COLS},
                       1 - (c.embedding <=> CAST(:embedding AS vector)) as similarity
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.status = 'ready' AND c.embedding IS NOT NULL{where_extra}
                ORDER BY c.embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
            """)
            if document_ids:
                sql = sql.bindparams(bindparam("document_ids", expanding=True))
            result = await db.execute(sql, params)
            rows = result.fetchall()
            
            chunks = []
            for row in rows:
                chunks.append((_row_to_chunk(row), float(row.similarity) if row.similarity else 0.0))
            
            logger.debug(f"Semantic search returned {len(chunks)} results")
            return chunks
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise
    
    def _format_embedding(self, embedding: List[float]) -> str:
        """Format embedding as PostgreSQL vector string for injection prevention."""
        # Validate all values are numeric
        validated = []
        for val in embedding:
            if not isinstance(val, (int, float)):
                raise ValueError(f"Invalid embedding value: {val}")
            validated.append(float(val))
        
        return "[" + ",".join(f"{x:.8f}" for x in validated) + "]"
    
    async def bm25_search(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 5,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
    ) -> List[Tuple[Chunk, float]]:
        """
        Perform BM25-style full-text search using PostgreSQL tsvector.
        Uses ts_rank for relevance scoring (BM25-like ranking).
        """
        try:
            where_extra = ""
            params: dict = {"query": query, "top_k": top_k}
            if workspace_id:
                where_extra = " AND d.workspace_id = :workspace_id"
                params["workspace_id"] = workspace_id
            if user_id:
                where_extra += " AND d.user_id = :user_id"
                params["user_id"] = user_id
            if document_ids:
                where_extra += " AND d.id IN :document_ids"
                params["document_ids"] = document_ids
            sql = text(f"""
                SELECT {_CHUNK_COLS},
                       ts_rank_cd(
                           to_tsvector('english', c.content || ' ' || coalesce(c.caption, '')),
                           plainto_tsquery('english', :query)
                       ) as rank_score
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.status = 'ready'{where_extra}
                AND to_tsvector('english', c.content || ' ' || coalesce(c.caption, ''))
                    @@ plainto_tsquery('english', :query)
                ORDER BY rank_score DESC
                LIMIT :top_k
            """)
            if document_ids:
                sql = sql.bindparams(bindparam("document_ids", expanding=True))
            result = await db.execute(sql, params)
            rows = result.fetchall()
            
            chunks = []
            for row in rows:
                normalized_score = min(float(row.rank_score), 1.0) if row.rank_score else 0.0
                chunks.append((_row_to_chunk(row), normalized_score))
            
            logger.debug(f"BM25 search returned {len(chunks)} results")
            return chunks
            
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            raise

    async def visual_search(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 5,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
    ) -> List[Tuple[Chunk, float]]:
        """CLIP cosine search over figure/table screenshot embeddings."""
        if not getattr(settings, "ENABLE_CLIP", True):
            return []
        try:
            from app.services.visual_embedding import visual_embedding_service

            query_clip = visual_embedding_service.embed_query(query)
            params: dict = {
                "embedding": self._format_embedding(query_clip),
                "top_k": top_k,
            }
            where_extra = ""
            if workspace_id:
                where_extra = " AND d.workspace_id = :workspace_id"
                params["workspace_id"] = workspace_id
            if user_id:
                where_extra += " AND d.user_id = :user_id"
                params["user_id"] = user_id
            if document_ids:
                where_extra += " AND d.id IN :document_ids"
                params["document_ids"] = document_ids
            sql = text(f"""
                SELECT {_CHUNK_COLS},
                       1 - (c.clip_embedding <=> CAST(:embedding AS vector)) as similarity
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.status = 'ready' AND c.clip_embedding IS NOT NULL{where_extra}
                ORDER BY c.clip_embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
            """)
            if document_ids:
                sql = sql.bindparams(bindparam("document_ids", expanding=True))
            result = await db.execute(sql, params)
            rows = result.fetchall()
            chunks = []
            for row in rows:
                chunks.append((_row_to_chunk(row), float(row.similarity) if row.similarity else 0.0))
            logger.debug(f"CLIP search returned {len(chunks)} results")
            return chunks
        except Exception as e:
            logger.warning(f"CLIP visual search skipped: {e}")
            return []

    async def identifier_search(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 5,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
    ) -> List[Tuple[Chunk, float]]:
        """Exact lexical hits for SKUs, figure ids, and 'site N' mentions."""
        if not getattr(settings, "ENABLE_IDENTIFIER_SEARCH", True):
            return []
        idents = _IDENT.findall(query or "")
        if not idents:
            return []
        try:
            params: dict = {"top_k": top_k}
            where_extra = ""
            if workspace_id:
                where_extra += " AND d.workspace_id = :workspace_id"
                params["workspace_id"] = workspace_id
            if user_id:
                where_extra += " AND d.user_id = :user_id"
                params["user_id"] = user_id
            if document_ids:
                where_extra += " AND d.id IN :document_ids"
                params["document_ids"] = document_ids
            ident_clauses = []
            for i, ident in enumerate(idents[:4]):
                key = f"ident{i}"
                params[key] = f"%{ident}%"
                ident_clauses.append(
                    f"(c.content ILIKE :{key} OR coalesce(c.caption,'') ILIKE :{key})"
                )
            sql = text(f"""
                SELECT {_CHUNK_COLS}
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.status = 'ready'{where_extra}
                AND ({' OR '.join(ident_clauses)})
                LIMIT :top_k
            """)
            if document_ids:
                sql = sql.bindparams(bindparam("document_ids", expanding=True))
            result = await db.execute(sql, params)
            chunks = [(_row_to_chunk(row), 1.0) for row in result.fetchall()]
            return chunks
        except Exception as e:
            logger.debug("identifier_search skipped: %s", e)
            return []
    
    async def hybrid_search(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 5,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        semantic_weight: Optional[float] = None,
    ) -> List[Tuple[Chunk, float]]:
        """
        Perform hybrid search with Reciprocal Rank Fusion (RRF).
        Combines semantic (vector) and BM25 (keyword) results.
        Uses adaptive semantic_weight based on query type when not explicitly provided.
        """
        try:
            weight = semantic_weight if semantic_weight is not None else _get_adaptive_semantic_weight(
                query, settings.SEMANTIC_WEIGHT
            )

            semantic_results = await self.semantic_search(
                db, query, top_k * 2, workspace_id, user_id, document_ids=document_ids
            )
            bm25_results = await self.bm25_search(
                db, query, top_k * 2, workspace_id, user_id, document_ids=document_ids
            )
            ident_results = await self.identifier_search(
                db, query, top_k, workspace_id, user_id, document_ids=document_ids
            )
            visual_results: List[Tuple[Chunk, float]] = []
            if getattr(settings, "ENABLE_CLIP", True):
                try:
                    visual_results = await self.visual_search(
                        db, query, top_k * 2, workspace_id, user_id, document_ids=document_ids
                    )
                except Exception as e:
                    logger.debug("visual_search skipped: %s", e)

            lists = [semantic_results, bm25_results, ident_results]
            weights = [1.0, 1.0, 1.0]
            if visual_results:
                lists.append(visual_results)
                weights.append(float(getattr(settings, "VISUAL_RRF_WEIGHT", 0.7)))
            if ident_results or visual_results:
                merged = self._rrf_merge_lists(lists, top_k, weights=weights)
                logger.debug(
                    "Hybrid RRF lists semantic=%s bm25=%s ident=%s visual=%s -> %s",
                    len(semantic_results),
                    len(bm25_results),
                    len(ident_results),
                    len(visual_results),
                    len(merged),
                )
                return merged

            k = 60
            chunk_scores: dict = {}
            chunk_map: dict = {}

            for rank, (chunk, score) in enumerate(semantic_results):
                chunk_id = chunk.id
                chunk_map[chunk_id] = chunk
                chunk_scores[chunk_id] = weight * (1 / (k + rank + 1))

            for rank, (chunk, score) in enumerate(bm25_results):
                chunk_id = chunk.id
                chunk_map[chunk_id] = chunk
                keyword_weight = 1 - weight
                if chunk_id in chunk_scores:
                    chunk_scores[chunk_id] += keyword_weight * (1 / (k + rank + 1))
                else:
                    chunk_scores[chunk_id] = keyword_weight * (1 / (k + rank + 1))

            sorted_chunks = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)

            results = []
            for chunk_id, score in sorted_chunks[:top_k]:
                results.append((chunk_map[chunk_id], score))

            logger.debug(f"Hybrid search returned {len(results)} results (weight={weight:.2f})")
            return results

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            raise
    
    async def multi_granularity_search(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 5,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        strategy: str = "HYBRID",
    ) -> List[Tuple[Chunk, float]]:
        """
        Multi-granularity retrieval: fetch from both small and large chunks,
        then merge and deduplicate using RRF.
        
        Per the execution plan:
        - Retrieve from ~300-token chunks (precise retrieval)
        - Retrieve from ~700-token chunks (context-rich retrieval)  
        - Merge + dedupe top-k
        """
        try:
            query_embedding = await self._embedding_service.embed_text(query)
            emb_str = self._format_embedding(query_embedding)
            
            # Fetch small chunks (token_count < 500) via semantic search
            small_results = await self._search_by_granularity(
                db, emb_str, top_k, workspace_id, user_id, document_ids=document_ids,
                max_tokens=SMALL_CHUNK_THRESHOLD
            )
            
            # Fetch large chunks (token_count >= 500) via semantic search
            large_results = await self._search_by_granularity(
                db, emb_str, top_k, workspace_id, user_id, document_ids=document_ids,
                min_tokens=SMALL_CHUNK_THRESHOLD
            )

            # Optional keyword/BM25 list (for HYBRID/KEYWORD strategies)
            bm25_results: List[Tuple[Chunk, float]] = []
            if strategy in ("HYBRID", "KEYWORD"):
                bm25_results = await self.bm25_search(
                    db, query, top_k, workspace_id, user_id, document_ids=document_ids
                )
            ident_results = await self.identifier_search(
                db, query, top_k, workspace_id, user_id, document_ids=document_ids
            )
            visual_results: List[Tuple[Chunk, float]] = []
            if getattr(settings, "ENABLE_CLIP", True):
                try:
                    visual_results = await self.visual_search(
                        db, query, top_k, workspace_id, user_id, document_ids=document_ids
                    )
                except Exception as e:
                    logger.debug("visual_search skipped: %s", e)
            
            vw = float(getattr(settings, "VISUAL_RRF_WEIGHT", 0.7))
            merged = self._rrf_merge_lists(
                [small_results, large_results, bm25_results, ident_results, visual_results],
                top_k,
                weights=[1.0, 1.0, 1.0, 1.0, vw],
            )
            
            logger.debug(f"Multi-granularity search: {len(small_results)} small, {len(large_results)} large, {len(merged)} merged")
            return merged
            
        except Exception as e:
            logger.error(f"Multi-granularity search failed: {e}")
            # Fallback to regular hybrid search
            return await self.hybrid_search(db, query, top_k, workspace_id, user_id)
    
    async def _search_by_granularity(
        self,
        db: AsyncSession,
        embedding_str: str,
        top_k: int,
        workspace_id: Optional[str],
        user_id: Optional[str],
        document_ids: Optional[List[str]] = None,
        min_tokens: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ) -> List[Tuple[Chunk, float]]:
        params: dict = {"embedding": embedding_str, "top_k": top_k}
        where_extra = ""
        
        if workspace_id:
            where_extra += " AND d.workspace_id = :workspace_id"
            params["workspace_id"] = workspace_id
        if user_id:
            where_extra += " AND d.user_id = :user_id"
            params["user_id"] = user_id
        if document_ids:
            where_extra += " AND d.id IN :document_ids"
            params["document_ids"] = document_ids
        if min_tokens is not None:
            where_extra += " AND c.token_count >= :min_tokens"
            params["min_tokens"] = min_tokens
        if max_tokens is not None:
            where_extra += " AND c.token_count < :max_tokens"
            params["max_tokens"] = max_tokens
            
        sql = text(f"""
            SELECT {_CHUNK_COLS},
                   1 - (c.embedding <=> CAST(:embedding AS vector)) as similarity
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.status = 'ready' AND c.embedding IS NOT NULL{where_extra}
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """)
        if document_ids:
            sql = sql.bindparams(bindparam("document_ids", expanding=True))
        result = await db.execute(sql, params)
        rows = result.fetchall()
        
        chunks = []
        for row in rows:
            chunks.append((_row_to_chunk(row), float(row.similarity) if row.similarity else 0.0))
        return chunks
    
    def _merge_granularity_results(
        self,
        small_results: List[Tuple[Chunk, float]],
        large_results: List[Tuple[Chunk, float]],
        top_k: int,
    ) -> List[Tuple[Chunk, float]]:
        k = 60  # RRF constant
        chunk_scores: dict = {}
        chunk_map: dict = {}
        seen_ids: Set[str] = set()
        
        # Process small chunks (weight: 0.5)
        for rank, (chunk, score) in enumerate(small_results):
            if chunk.id not in seen_ids:
                chunk_map[chunk.id] = chunk
                chunk_scores[chunk.id] = 0.5 * (1 / (k + rank + 1))
                seen_ids.add(chunk.id)
        
        # Process large chunks (weight: 0.5)
        for rank, (chunk, score) in enumerate(large_results):
            if chunk.id not in seen_ids:
                chunk_map[chunk.id] = chunk
                chunk_scores[chunk.id] = 0.5 * (1 / (k + rank + 1))
                seen_ids.add(chunk.id)
            elif chunk.id in chunk_scores:
                chunk_scores[chunk.id] += 0.5 * (1 / (k + rank + 1))
        
        # Sort by combined score
        sorted_chunks = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Ensure diversity: at least 1 from each granularity if available
        results = []
        has_small = False
        has_large = False
        
        for chunk_id, score in sorted_chunks[:top_k]:
            chunk = chunk_map[chunk_id]
            results.append((chunk, score))
            if chunk.token_count < SMALL_CHUNK_THRESHOLD:
                has_small = True
            else:
                has_large = True
        
        # If missing a granularity and we have room, add one
        if not has_small and small_results and len(results) < top_k:
            chunk, score = small_results[0]
            if chunk.id not in {r[0].id for r in results}:
                results.append((chunk, score))
        
        if not has_large and large_results and len(results) < top_k:
            chunk, score = large_results[0]
            if chunk.id not in {r[0].id for r in results}:
                results.append((chunk, score))
        
        return results[:top_k]

    def _rrf_merge_lists(
        self,
        result_lists: List[List[Tuple[Chunk, float]]],
        top_k: int,
        k: int = 60,
        weights: Optional[List[float]] = None,
    ) -> List[Tuple[Chunk, float]]:
        chunk_scores: dict = {}
        chunk_map: dict = {}
        for i, results in enumerate(result_lists):
            if not results:
                continue
            w = 1.0 if not weights or i >= len(weights) else float(weights[i])
            for rank, (chunk, _) in enumerate(results):
                chunk_map[chunk.id] = chunk
                chunk_scores[chunk.id] = chunk_scores.get(chunk.id, 0) + w / (k + rank + 1)
        sorted_chunks = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)
        return [(chunk_map[cid], score) for cid, score in sorted_chunks[:top_k]]

    async def search(
        self,
        db: AsyncSession,
        query: str,
        strategy: str = "HYBRID",
        top_k: int = 5,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        use_multi_granularity: Optional[bool] = None,
    ) -> List[Tuple[Chunk, float]]:
        logger.info(
            f"Searching with strategy={strategy}, top_k={top_k}, workspace_id={workspace_id}, "
            f"user_id={user_id}, document_ids={len(document_ids) if document_ids else 0}"
        )

        # Determine multi-granularity mode:
        # - If explicitly True/False, use that
        # - If None, use settings.ENABLE_MULTI_GRANULARITY
        should_use_multi_granularity = (
            use_multi_granularity if use_multi_granularity is not None 
            else settings.ENABLE_MULTI_GRANULARITY
        )
        
        if should_use_multi_granularity:
            return await self.multi_granularity_search(
                db, query, top_k, workspace_id, user_id,
                document_ids=document_ids, strategy=strategy
            )

        async def _do_search(s: str) -> List[Tuple[Chunk, float]]:
            if s == "SEMANTIC":
                return await self.semantic_search(
                    db, query, top_k, workspace_id, user_id, document_ids=document_ids
                )
            elif s == "KEYWORD":
                return await self.bm25_search(
                    db, query, top_k, workspace_id, user_id, document_ids=document_ids
                )
            else:
                return await self.hybrid_search(
                    db, query, top_k, workspace_id, user_id, document_ids=document_ids
                )

        results = await _do_search(strategy)

        if not results and strategy == "KEYWORD":
            logger.info("KEYWORD returned empty, falling back to SEMANTIC")
            results = await self.semantic_search(
                db, query, top_k, workspace_id, user_id, document_ids=document_ids
            )

        if not results and strategy == "SEMANTIC":
            logger.info("SEMANTIC returned empty, falling back to HYBRID")
            results = await self.hybrid_search(
                db, query, top_k, workspace_id, user_id, document_ids=document_ids
            )

        return results


def create_retrieval_service(embedding_svc=None) -> RetrievalService:
    return RetrievalService(embedding_svc=embedding_svc)


# Default singleton instance
retrieval_service = create_retrieval_service()
