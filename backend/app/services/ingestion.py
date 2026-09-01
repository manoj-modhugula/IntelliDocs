"""Parse documents, chunk text, embed, and persist chunks."""

import asyncio
import uuid
import logging
import time
import hashlib
from typing import List, Optional, Tuple
import json
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.models import Document, Chunk, DocumentStatus
from app.services.embedding import embedding_service
from app.core.config import settings

logger = logging.getLogger(__name__)

# Thread pool for parallel page processing
_page_executor = ThreadPoolExecutor(max_workers=8)

# Token estimation: 1 token ≈ 4 characters for English text
CHARS_PER_TOKEN = 4

# Section boundary patterns for semantic chunking
_HEADING_PATTERNS = [
    r'^(?:#{1,6}\s+.+)$',                    # Markdown headings
    r'^\s*\d+\.\s+[A-Z][^\n]+$',           # Numbered sections: "1. Introduction"
    r'^(?:\*{2,}|_{2,})[^\n]+(?:\*{2,}|_{2,})$',  # Bold underline headings
    r'^(?:[A-Z][A-Z\s]{3,}:)$',           # ALL CAPS labels: "INTRODUCTION:"
    r'^\s*[-=]{3,}\s*$',                   # Horizontal rule dividers
]
_SECTION_BREAK_TOKENS = 50  # Min tokens to consider a section worth keeping separate


def _is_section_boundary(text: str) -> bool:
    """Check if a line looks like a section heading or divider."""
    import re
    for pattern in _HEADING_PATTERNS:
        if re.match(pattern, text.strip(), re.MULTILINE):
            return True
    return False


def _split_into_paragraphs(text: str) -> List[str]:
    """
    Split text into semantic paragraphs, respecting section boundaries.
    Returns paragraphs separated by blank lines or section headings.
    """
    lines = text.split('\n')
    paragraphs: List[str] = []
    current: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                para = ' '.join(current).strip()
                if para:
                    paragraphs.append(para)
                current = []
        elif _is_section_boundary(stripped):
            if current:
                para = ' '.join(current).strip()
                if para:
                    paragraphs.append(para)
                current = []
            paragraphs.append(stripped)
        else:
            current.append(stripped)

    if current:
        para = ' '.join(current).strip()
        if para:
            paragraphs.append(para)

    return paragraphs


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


class IngestionService:
    """
    Service for document ingestion with parallel processing.
    Uses pdfplumber (primary) with pypdf/pymupdf fallback for ~99% parse success.
    Supports multi-granularity chunking (300 + 700 tokens).
    """
    
    def __init__(self):
        self.chunk_size_small = settings.CHUNK_SIZE_SMALL
        self.chunk_size_large = settings.CHUNK_SIZE_LARGE
        self.chunk_overlap = settings.CHUNK_OVERLAP
        self.enable_multi_granularity = settings.ENABLE_MULTI_GRANULARITY
        self.semantic_chunking = getattr(settings, 'SEMANTIC_CHUNKING', False)

        self.total_pages_processed = 0
        self.total_parse_time_ms = 0
        self.parse_failures = 0
        self.parse_successes = 0
    
    def _parse_pdf_page_pdfplumber(self, page) -> str:
        try:
            text = page.extract_text() or ""
            return text.strip()
        except Exception:
            return ""
    
    def _parse_pdf_pdfplumber_parallel(self, file_bytes: bytes) -> List[Tuple[int, str]]:
        """Parse PDF using pdfplumber with parallel page extraction."""
        try:
            import pdfplumber
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                num_pages = len(pdf.pages)
                if num_pages == 0:
                    return []
                
                # For small PDFs, sequential is faster (no thread overhead)
                if num_pages <= 3:
                    pages = []
                    for page_num, page in enumerate(pdf.pages, 1):
                        text = self._parse_pdf_page_pdfplumber(page)
                        if text:
                            pages.append((page_num, text))
                    return pages
                
                # For larger PDFs, use parallel extraction
                # Note: pdfplumber pages must be processed within the context manager
                results = [None] * num_pages
                
                def extract_page(idx: int) -> Tuple[int, str]:
                    page = pdf.pages[idx]
                    text = self._parse_pdf_page_pdfplumber(page)
                    return (idx + 1, text)
                
                # Use up to 8 workers for page extraction
                with ThreadPoolExecutor(max_workers=min(8, num_pages)) as executor:
                    futures = {executor.submit(extract_page, i): i for i in range(num_pages)}
                    for future in as_completed(futures):
                        try:
                            page_num, text = future.result()
                            results[page_num - 1] = (page_num, text)
                        except Exception as e:
                            logger.warning(f"Page extraction failed: {e}")
                
                # Filter out None/empty results and maintain order
                return [(pn, text) for item in results if item is not None for pn, text in [item] if text]
                
        except Exception as e:
            logger.warning(f"pdfplumber parallel failed: {e}, trying sequential")
            return self._parse_pdf_pdfplumber_sequential(file_bytes)
    
    def _parse_pdf_pdfplumber_sequential(self, file_bytes: bytes) -> List[Tuple[int, str]]:
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = self._parse_pdf_page_pdfplumber(page)
                    if text:
                        pages.append((page_num, text))
            return pages
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}, trying fallback")
            return []
    
    def _parse_pdf_pdfplumber(self, file_bytes: bytes) -> List[Tuple[int, str]]:
        return self._parse_pdf_pdfplumber_parallel(file_bytes)
    
    def _parse_pdf_pymupdf(self, file_bytes: bytes) -> List[Tuple[int, str]]:
        try:
            import fitz  # pymupdf
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            num_pages = len(doc)
            
            if num_pages == 0:
                doc.close()
                return []
            
            # For small PDFs, sequential is faster
            if num_pages <= 3:
                pages = []
                for page_num, page in enumerate(doc, 1):
                    text = page.get_text().strip()
                    if text:
                        pages.append((page_num, text))
                doc.close()
                return pages
            
            # Parallel extraction for larger PDFs
            results = [None] * num_pages
            
            def extract_page(idx: int) -> Tuple[int, str]:
                page = doc[idx]
                text = page.get_text().strip()
                return (idx + 1, text)
            
            with ThreadPoolExecutor(max_workers=min(8, num_pages)) as executor:
                futures = {executor.submit(extract_page, i): i for i in range(num_pages)}
                for future in as_completed(futures):
                    try:
                        page_num, text = future.result()
                        results[page_num - 1] = (page_num, text)
                    except Exception as e:
                        logger.warning(f"pymupdf page extraction failed: {e}")
            
            doc.close()
            # Filter out None/empty results and maintain order
            return [(pn, text) for item in results if item is not None for pn, text in [item] if text]
            
        except Exception as e:
            logger.warning(f"pymupdf failed: {e}, trying pypdf")
            return []
    
    def _parse_pdf_pypdf(self, file_bytes: bytes) -> List[Tuple[int, str]]:
        try:
            from pypdf import PdfReader
            pages = []
            reader = PdfReader(BytesIO(file_bytes))
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text and text.strip():
                    pages.append((page_num, text.strip()))
            return pages
        except Exception as e:
            logger.error(f"All PDF parsers failed: {e}")
            return []
    
    async def parse_pdf(self, file_bytes: bytes) -> List[dict]:
        """Parse PDF with fallback chain."""
        start = time.perf_counter()
        loop = asyncio.get_event_loop()
        
        # Try pdfplumber first (best quality)
        pages = await loop.run_in_executor(_page_executor, self._parse_pdf_pdfplumber, file_bytes)
        
        # Fallback to pymupdf if pdfplumber fails
        if not pages:
            pages = await loop.run_in_executor(_page_executor, self._parse_pdf_pymupdf, file_bytes)
        
        # Last resort: pypdf
        if not pages:
            pages = await loop.run_in_executor(_page_executor, self._parse_pdf_pypdf, file_bytes)
        
        elapsed = (time.perf_counter() - start) * 1000
        self.total_parse_time_ms += elapsed
        self.total_pages_processed += len(pages)
        
        if pages:
            self.parse_successes += 1
        else:
            self.parse_failures += 1
        
        return [{"content": text, "page_number": pn} for pn, text in pages]
    
    async def parse_docx(self, file_bytes: bytes) -> List[dict]:
        from docx import Document as DocxDocument
        doc = DocxDocument(BytesIO(file_bytes))
        paragraphs = []
        
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append({
                    "content": para.text.strip(),
                    "page_number": None,
                })
        
        if paragraphs:
            self.parse_successes += 1
        else:
            self.parse_failures += 1
        
        return paragraphs
    
    async def parse_text(self, file_bytes: bytes) -> List[dict]:
        text = file_bytes.decode("utf-8", errors="ignore").strip()
        self.parse_successes += 1
        return [{"content": text, "page_number": None}] if text else []
    
    async def parse_document(self, file_bytes: bytes, file_type: str) -> List[dict]:
        """Parse document based on file type."""
        if "pdf" in file_type.lower():
            return await self.parse_pdf(file_bytes)
        elif "word" in file_type.lower() or "docx" in file_type.lower():
            return await self.parse_docx(file_bytes)
        else:
            return await self.parse_text(file_bytes)
    
    def chunk_text_by_tokens(
        self,
        text: str,
        page_number: Optional[int] = None,
        target_tokens: int = 300,
        granularity: str = "small"
    ) -> List[dict]:
        """
        Split text into overlapping chunks by token count.
        Token estimation: 1 token ≈ 4 characters.
        When semantic_chunking is enabled, splits by paragraph/section boundaries first.
        """
        target_chars = target_tokens * CHARS_PER_TOKEN
        overlap_chars = self.chunk_overlap * CHARS_PER_TOKEN

        if self.semantic_chunking:
            units = _split_into_paragraphs(text)
        else:
            import re
            units = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current_chunk = []
        current_chars = 0
        chunk_index = 0

        for unit in units:
            unit_chars = len(unit)

            if current_chars + unit_chars > target_chars and current_chunk:
                content = " ".join(current_chunk)
                chunks.append({
                    "content": content,
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                    "token_count": estimate_tokens(content),
                    "granularity": granularity,
                })
                chunk_index += 1

                overlap_text = content[-overlap_chars:] if len(content) > overlap_chars else content
                current_chunk = [overlap_text] if overlap_text else []
                current_chars = len(overlap_text) if overlap_text else 0

            current_chunk.append(unit)
            current_chars += unit_chars + 1

        if current_chunk:
            content = " ".join(current_chunk)
            if content.strip():
                chunks.append({
                    "content": content,
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                    "token_count": estimate_tokens(content),
                    "granularity": granularity,
                })

        return chunks
    
    def chunk_text(self, text: str, page_number: Optional[int] = None) -> List[dict]:
        if self.enable_multi_granularity:
            # Create both small and large chunks
            small_chunks = self.chunk_text_by_tokens(
                text, page_number, 
                target_tokens=self.chunk_size_small, 
                granularity="small"
            )
            large_chunks = self.chunk_text_by_tokens(
                text, page_number, 
                target_tokens=self.chunk_size_large, 
                granularity="large"
            )
            # Combine: small chunks first, then large chunks
            return small_chunks + large_chunks
        else:
            # Single granularity (default: small)
            return self.chunk_text_by_tokens(
                text, page_number, 
                target_tokens=self.chunk_size_small, 
                granularity="small"
            )

    def _prune_chunks(self, chunks: List[dict]) -> List[dict]:
        if not settings.ENABLE_CHUNK_PRUNING:
            return chunks

        pruned: List[dict] = []
        for chunk in chunks:
            content = chunk.get("content", "")
            token_count = chunk.get("token_count", 0)
            if token_count < settings.PRUNE_MIN_TOKENS or token_count > settings.PRUNE_MAX_TOKENS:
                continue
            if not content:
                continue
            alnum = sum(1 for c in content if c.isalnum())
            alnum_ratio = alnum / max(len(content), 1)
            if alnum_ratio < settings.PRUNE_MIN_ALNUM_RATIO:
                continue
            tokens = [t for t in content.lower().split() if t.isalnum()]
            unique_ratio = len(set(tokens)) / max(len(tokens), 1)
            if unique_ratio < settings.PRUNE_MIN_UNIQUE_RATIO:
                continue
            pruned.append(chunk)

        return pruned

    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()

    def _normalize_embedding(self, embedding) -> List[float]:
        if embedding is None:
            return []
        if isinstance(embedding, str):
            try:
                parsed = json.loads(embedding)
                return [float(x) for x in parsed]
            except Exception as e:
                raise ValueError(f"Invalid embedding string: {e}") from e
        if isinstance(embedding, list):
            return [float(x) for x in embedding]
        raise ValueError(f"Unsupported embedding type: {type(embedding)}")

    def _attach_hashes(self, chunks: List[dict]) -> List[dict]:
        for chunk in chunks:
            if "content_hash" not in chunk:
                chunk["content_hash"] = self._hash_content(chunk.get("content", ""))
        return chunks

    def _dedupe_chunks(self, chunks: List[dict]) -> List[dict]:
        if not settings.ENABLE_CHUNK_DEDUP:
            return chunks
        seen = set()
        deduped: List[dict] = []
        for chunk in chunks:
            content = chunk.get("content", "")
            key = chunk.get("content_hash") or self._hash_content(content)
            chunk["content_hash"] = key
            if key in seen:
                continue
            seen.add(key)
            deduped.append(chunk)
        return deduped

    def _score_chunk(self, chunk: dict) -> float:
        content = chunk.get("content", "")
        token_count = chunk.get("token_count", 0)
        if not content or token_count <= 0:
            return 0.0
        alnum = sum(1 for c in content if c.isalnum())
        alnum_ratio = alnum / max(len(content), 1)
        tokens = [t for t in content.lower().split() if t.isalnum()]
        unique_ratio = len(set(tokens)) / max(len(tokens), 1)
        return token_count * alnum_ratio * unique_ratio

    def _select_chunks_for_embedding(self, chunks: List[dict]) -> tuple[list[dict], list[dict]]:
        if not settings.ENABLE_SELECTIVE_EMBEDDING:
            return chunks, []
        scored = [(self._score_chunk(c), c) for c in chunks]
        scored.sort(key=lambda x: x[0], reverse=True)
        max_count = max(1, int(len(scored) * settings.EMBEDDING_TOP_PCT))
        total_doc_tokens = sum(c.get("token_count", 0) for _, c in scored)
        budget = int(total_doc_tokens * settings.EMBEDDING_TOKEN_BUDGET_PCT)
        budget = max(settings.EMBEDDING_TOKEN_BUDGET_MIN, min(budget, settings.EMBEDDING_TOKEN_BUDGET_MAX))
        selected: List[dict] = []
        skipped: List[dict] = []
        total_tokens = 0
        for idx, (_, chunk) in enumerate(scored):
            token_count = chunk.get("token_count", 0)
            if idx < max_count and (total_tokens + token_count) <= budget:
                selected.append(chunk)
                total_tokens += token_count
            else:
                skipped.append(chunk)
        return selected, skipped

    async def _fetch_existing_embeddings(
        self, db: AsyncSession, hashes: List[str]
    ) -> dict:
        if not hashes:
            return {}
        existing: dict = {}
        batch_size = 200
        for i in range(0, len(hashes), batch_size):
            batch = hashes[i:i + batch_size]
            result = await db.execute(
                text(
                    "SELECT content_hash, embedding FROM chunks "
                    "WHERE content_hash = ANY(:hashes) AND embedding IS NOT NULL"
                ),
                {"hashes": batch},
            )
            for row in result.fetchall():
                try:
                    existing[row.content_hash] = self._normalize_embedding(row.embedding)
                except Exception as e:
                    logger.warning(f"Skipping invalid cached embedding: {e}")
        return existing
    
    async def process_document(
        self,
        db: AsyncSession,
        document_id: str,
        file_bytes: bytes,
        file_type: str,
    ) -> int:
        try:
            document = await db.get(Document, document_id)
            if not document:
                raise ValueError(f"Document {document_id} not found")
            
            document.status = DocumentStatus.PROCESSING.value
            await db.commit()
            
            # Parse document
            pages = await self.parse_document(file_bytes, file_type)
            
            # Chunk all pages
            all_chunks = []
            for page in pages:
                chunks = self.chunk_text(page["content"], page["page_number"])
                all_chunks.extend(chunks)
            
            # Prune low-value chunks before embedding
            if settings.ENABLE_CHUNK_PRUNING:
                before = len(all_chunks)
                all_chunks = self._prune_chunks(all_chunks)
                logger.info(f"Pruned chunks: {before} -> {len(all_chunks)}")
            all_chunks = self._attach_hashes(all_chunks)
            if settings.ENABLE_CHUNK_DEDUP:
                before = len(all_chunks)
                all_chunks = self._dedupe_chunks(all_chunks)
                logger.info(f"Deduped chunks: {before} -> {len(all_chunks)}")

            selected_chunks, skipped_chunks = self._select_chunks_for_embedding(all_chunks)
            logger.info(
                f"Selective embedding: {len(selected_chunks)} embed, {len(skipped_chunks)} skipped"
            )
            
            if not all_chunks:
                document.status = DocumentStatus.ERROR.value
                document.error_message = "No text content found in document"
                await db.commit()
                return 0
            
            existing_embeddings = await self._fetch_existing_embeddings(
                db, [c["content_hash"] for c in selected_chunks]
            )
            reused = 0
            embed_indices = []
            for idx, chunk in enumerate(selected_chunks):
                existing = existing_embeddings.get(chunk["content_hash"])
                if existing is not None:
                    chunk["embedding"] = existing
                    reused += 1
                else:
                    embed_indices.append(idx)
            logger.info(f"Reused embeddings: {reused}")

            # Generate embeddings in batches to avoid memory spikes
            batch_size = embedding_service.batch_size
            for batch_start in range(0, len(embed_indices), batch_size):
                batch_indices = embed_indices[batch_start:batch_start + batch_size]
                batch = [selected_chunks[i] for i in batch_indices]
                batch_texts = [c["content"] for c in batch]
                embeddings = await embedding_service.embed_texts(batch_texts)
                for chunk_data, embedding in zip(batch, embeddings):
                    chunk_data["embedding"] = embedding

            # Store chunks for all embedded items (including reused)
            for chunk_data in selected_chunks:
                embedding = chunk_data.get("embedding")
                if embedding is None:
                    embedding = [0.0] * embedding_service.embedding_dim
                else:
                    embedding = self._normalize_embedding(embedding)
                chunk = Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    content=chunk_data["content"],
                    page_number=chunk_data["page_number"],
                    chunk_index=chunk_data["chunk_index"],
                    token_count=chunk_data["token_count"],
                    embedding=embedding,
                    content_hash=chunk_data.get("content_hash"),
                    workspace_id=document.workspace_id,
                )
                db.add(chunk)

            # Store skipped chunks without embeddings (keyword/BM25 only)
            for chunk_data in skipped_chunks:
                chunk = Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    content=chunk_data["content"],
                    page_number=chunk_data["page_number"],
                    chunk_index=chunk_data["chunk_index"],
                    token_count=chunk_data["token_count"],
                    embedding=None,
                    content_hash=chunk_data.get("content_hash"),
                    workspace_id=document.workspace_id,
                )
                db.add(chunk)
            
            document.status = DocumentStatus.READY.value
            document.chunk_count = len(all_chunks)
            await db.commit()
            
            return len(all_chunks)
            
        except Exception as e:
            document = await db.get(Document, document_id)
            if document:
                document.status = DocumentStatus.ERROR.value
                document.error_message = str(e)[:500]
                await db.commit()
            raise
    
    def get_stats(self) -> dict:
        total = self.parse_successes + self.parse_failures
        success_rate = (self.parse_successes / total * 100) if total > 0 else 0
        pages_per_sec = (
            self.total_pages_processed / (self.total_parse_time_ms / 1000)
            if self.total_parse_time_ms > 0 else 0
        )
        return {
            "total_documents": total,
            "successes": self.parse_successes,
            "failures": self.parse_failures,
            "success_rate": f"{success_rate:.1f}%",
            "total_pages": self.total_pages_processed,
            "parse_time_ms": self.total_parse_time_ms,
            "pages_per_sec": f"{pages_per_sec:.1f}",
        }


# Singleton instance
ingestion_service = IngestionService()
