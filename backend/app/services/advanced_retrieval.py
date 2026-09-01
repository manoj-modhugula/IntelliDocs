"""HyDE, cross-encoder rerank, multi-query expansion, and RRF merge."""

import logging
import asyncio
import numpy as np
from typing import List, Tuple

from app.models import Chunk

logger = logging.getLogger(__name__)

# Lazy-loaded cross-encoder (avoids loading ~80MB at import)
_reranker = None
_reranker_loading = False

# Query type patterns for deciding when HyDE is most effective
_FACTUAL_QUERY_PATTERNS = [
    "what is", "what are", "how does", "how do", "define",
    "explain", "describe", "compare", "contrast", "difference between",
    "list the", "who is", "who was", "when did", "where is", "why does",
    "symptoms", "causes", "treatment", "definition", "meaning",
]
_OPINION_QUERY_PATTERNS = [
    "think", "feel", "opinion", "best way", "suggest", "recommend",
    "should i", "would you", "personal", "your experience",
]


def _classify_query_type(query: str) -> str:
    """
    Classify whether a query is factual or open-ended.
    Factual queries (definition, how, what) benefit most from HyDE.
    """
    q = query.lower()
    factual_score = sum(1 for p in _FACTUAL_QUERY_PATTERNS if p in q)
    opinion_score = sum(1 for p in _OPINION_QUERY_PATTERNS if p in q)
    if factual_score > opinion_score:
        return "factual"
    if opinion_score > 0:
        return "opinion"
    return "neutral"


def _is_simple_query(query: str) -> bool:
    """Simple queries (short, single topic) may not benefit from HyDE overhead."""
    words = query.lower().split()
    if len(words) <= 4:
        return True
    question_words = {"what", "who", "where", "when", "why", "how", "is", "are", "do", "does"}
    simple_count = sum(1 for w in words if w in question_words)
    return simple_count >= len(words) * 0.6


def _get_hyde_diversity_count(query: str) -> int:
    """
    Determine how many diverse hypothetical documents to generate.
    Factual + complex queries get more candidates.
    """
    qtype = _classify_query_type(query)
    if qtype == "factual" and not _is_simple_query(query):
        return 3
    if qtype == "opinion":
        return 2
    return 2


def _build_hyde_prompt(query: str) -> str:
    """Build an improved HyDE prompt that generates more realistic document passages."""
    return f"""Write a factual passage of 2-4 sentences that directly answers the given question.
The passage should present the information as established fact from a reliable technical source.
Do not include opinions, caveats, or hedging. Do not say "in general" or "typically".
Do not say "I think" or "it may be". State facts directly.

Question: {query}

Passage:"""


def _validate_hyde_output(text: str) -> bool:
    """
    Check if a HyDE output is worth using.
    Reject outputs that are too short, too long, or contain hedging/uncertainty.
    """
    if not text or len(text.strip()) < 30:
        return False
    if len(text.strip()) > 600:
        return False
    hedging_phrases = [
        "i think", "i believe", "may be", "might be", "could be",
        "it seems", "probably", "possibly", "in general", "typically",
        "often", "sometimes", "usually", "i'm not sure", "not certain",
        "your opinion", "you might", "you should", "i would recommend",
    ]
    lower = text.lower()
    if any(phrase in lower for phrase in hedging_phrases):
        return False
    return True


def _get_reranker():
    """Load cross-encoder reranker."""
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder  # type: ignore
            _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
            logger.info("CrossEncoder reranker loaded (ms-marco-MiniLM-L-6-v2)")
        except Exception as e:
            logger.warning(f"CrossEncoder unavailable (reranking disabled): {e}")
            _reranker = False
    return _reranker if _reranker else None


def warm_reranker():
    """Pre-load reranker model in background thread."""
    global _reranker_loading
    if _reranker is not None or _reranker_loading:
        return
    _reranker_loading = True
    import threading
    def _load():
        _get_reranker()
    threading.Thread(target=_load, daemon=True).start()


warm_reranker()


def rerank_chunks(
    query: str,
    chunks: List[Tuple[Chunk, float]],
    top_k: int = 10,
    blend_original: float = 0.3,
) -> List[Tuple[Chunk, float]]:
    """
    Re-rank chunks using cross-encoder, optionally blending with original retrieval scores.

    blend_original: weight for original score in [0, 1]. Higher values preserve more
    of the original retrieval ranking (useful when cross-encoder confidence is low).
    """
    reranker = _get_reranker()
    if reranker is None or not chunks:
        return chunks[:top_k]

    try:
        pairs = [
            (
                query,
                ((getattr(c[0], "caption", None) or "") + " " + (c[0].content or "")).strip()[:800],
            )
            for c in chunks
        ]
        ce_scores = reranker.predict(pairs)

        ce_min = ce_scores.min()
        ce_max = ce_scores.max()
        if ce_max > ce_min:
            ce_norm = (ce_scores - ce_min) / (ce_max - ce_min)
        else:
            ce_norm = ce_scores * 0 + 0.5

        orig_scores = np.array([c[1] for c in chunks])
        orig_min = orig_scores.min()
        orig_max = orig_scores.max()
        if orig_max > orig_min:
            orig_norm = (orig_scores - orig_min) / (orig_max - orig_min)
        else:
            orig_norm = orig_scores * 0 + 0.5

        blend = blend_original
        combined = (1 - blend) * ce_norm + blend * orig_norm

        scored = list(zip([c[0] for c in chunks], combined.tolist()))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
    except Exception as e:
        logger.warning(f"Reranking failed: {e}")
        return chunks[:top_k]


async def hyde_embed(
    query: str,
    llm_generate_fn,
    embed_fn,
    num_hypothetical: int = 2,
) -> List[List[float]]:
    """
    Generate hypothetical document embeddings via HyDE.
    Uses query-type-aware generation count and output validation.
    """
    num_to_generate = _get_hyde_diversity_count(query)
    prompt = _build_hyde_prompt(query)

    async def _generate_and_embed():
        try:
            hypo = await llm_generate_fn(prompt, max_tokens=150, temperature=0.3)
            if not hypo or not _validate_hyde_output(hypo):
                return None
            emb = await embed_fn(hypo.strip())
            if emb:
                return emb
        except Exception as e:
            logger.debug(f"HyDE generation failed: {e}")
        return None

    results = await asyncio.gather(*[_generate_and_embed() for _ in range(num_to_generate)])
    embeddings = [emb for emb in results if emb is not None]
    if not embeddings:
        logger.debug(f"All {num_to_generate} HyDE candidates rejected, falling back to query embedding")
    return embeddings


def rrf_merge(
    result_lists: List[List[Tuple[Chunk, float]]],
    k: int = 60,
) -> List[Tuple[Chunk, float]]:
    chunk_scores = {}
    chunk_map = {}

    for results in result_lists:
        for rank, (chunk, _) in enumerate(results):
            cid = chunk.id
            chunk_map[cid] = chunk
            chunk_scores[cid] = chunk_scores.get(cid, 0) + 1 / (k + rank + 1)

    sorted_items = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)
    return [(chunk_map[cid], score) for cid, score in sorted_items]


async def multi_query_expand(
    query: str,
    llm_generate_fn,
    num_queries: int = 3,
) -> List[str]:
    """Generate multiple query variations with better diversity."""
    qtype = _classify_query_type(query)
    if qtype == "factual":
        prompt_type = "different factual angles"
    elif qtype == "opinion":
        prompt_type = "different perspectives"
    else:
        prompt_type = "different phrasings"

    prompt = f"""Generate {num_queries} variations of this question from {prompt_type}.
One per line. Keep each variation concise (under 15 words). Include the original.

Original: {query}

Variations:"""

    try:
        out = await llm_generate_fn(prompt, max_tokens=150, temperature=0.5)
        if not out:
            return [query]
        lines = [q.strip() for q in out.split("\n") if q.strip() and len(q.strip()) > 5]
        seen = {query}
        result = [query]
        for line in lines:
            if line not in seen:
                seen.add(line)
                result.append(line)
            if len(result) >= num_queries + 1:
                break
        return result[:num_queries + 1]
    except Exception as e:
        logger.debug(f"Multi-query expansion failed: {e}")
        return [query]


def assess_retrieval_confidence(chunks: List[Tuple[Chunk, float]]) -> str:
    if not chunks:
        return "very_low"
    top_score = chunks[0][1]
    if top_score >= 0.7:
        return "high"
    if top_score >= 0.5:
        return "low"
    return "very_low"
