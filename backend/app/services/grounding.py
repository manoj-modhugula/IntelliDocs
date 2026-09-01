"""Claim-level NLI filter: drop generated sentences not entailed by evidence."""

from __future__ import annotations

import logging
import re
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

_nli_model = None

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_TOKEN = re.compile(r"[a-z0-9]+")
_CITE = re.compile(r"\[(\d+)\]")

_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "be", "been", "with", "as", "by", "at", "from", "that",
    "this", "it", "its", "if", "not", "but", "than", "then", "also", "may",
    "can", "will", "into", "their", "they", "them", "you", "your", "we",
}


def split_claims(answer: str) -> List[str]:
    """Split an answer into atomic claims (sentences / list items)."""
    if not answer or not answer.strip():
        return []
    lines: List[str] = []
    for raw in answer.replace("\r\n", "\n").split("\n"):
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            lines.append(stripped)
            continue
        bullet = re.match(r"^[-*•]\s+(.+)", stripped)
        numbered = re.match(r"^\d+[.)]\s+(.+)", stripped)
        if bullet:
            lines.append(bullet.group(1).strip())
            continue
        if numbered:
            lines.append(numbered.group(1).strip())
            continue
        parts = _SENTENCE_SPLIT.split(stripped)
        for part in parts:
            claim = part.strip()
            if claim:
                lines.append(claim)
    return lines


def evidence_text(chunks: Sequence, max_chars_per: int = 800) -> str:
    parts: List[str] = []
    for item in chunks:
        chunk = item[0] if isinstance(item, tuple) else item
        caption = getattr(chunk, "caption", None)
        content = getattr(chunk, "content", None)
        caption = caption if isinstance(caption, str) else ""
        content = content if isinstance(content, str) else ""
        text = " ".join(p for p in (caption, content) if p).strip()
        if text:
            parts.append(text[:max_chars_per])
    return "\n".join(parts)


def _content_tokens(text: str) -> List[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 2]


def mock_entailed(claim: str, evidence: str) -> bool:
    """Token/number overlap stand-in used when MOCK_LLM_AND_EMBEDDINGS is on."""
    ev = evidence.lower()
    nums = _NUMBER.findall(claim)
    if any(n not in evidence for n in nums):
        return False
    toks = _content_tokens(claim)
    if not toks:
        return True
    hits = 0
    for tok in toks:
        if tok in ev or (len(tok) > 4 and tok[:-1] in ev):
            hits += 1
    return (hits / len(toks)) >= 0.5


def _get_nli():
    global _nli_model
    if _nli_model is False:
        return None
    if _nli_model is not None:
        return _nli_model
    try:
        from sentence_transformers import CrossEncoder

        _nli_model = CrossEncoder(settings.NLI_MODEL_ID, max_length=512)
        logger.info("NLI model loaded (%s)", settings.NLI_MODEL_ID)
        return _nli_model
    except Exception as e:
        logger.warning("NLI model unavailable: %s", e)
        _nli_model = False
        return None


_minicheck = None


def _get_minicheck():
    global _minicheck
    if _minicheck is False:
        return None
    if _minicheck is not None:
        return _minicheck
    try:
        from minicheck.minicheck import MiniCheck

        _minicheck = MiniCheck(model_name="flan-t5-large")
        logger.info("MiniCheck-Flan-T5-Large loaded")
        return _minicheck
    except Exception as e:
        logger.warning("MiniCheck unavailable: %s", e)
        _minicheck = False
        return None


def nli_label(claim: str, evidence: str) -> str:
    """Return entailment | neutral | contradiction."""
    if not claim.strip():
        return "neutral"
    backend = (getattr(settings, "NLI_BACKEND", "auto") or "auto").lower()
    if getattr(settings, "MOCK_LLM_AND_EMBEDDINGS", False) and backend != "minicheck":
        return "entailment" if mock_entailed(claim, evidence) else "neutral"
    if backend in ("auto", "minicheck") and not getattr(settings, "MOCK_LLM_AND_EMBEDDINGS", False):
        mc = _get_minicheck()
        if mc is not None:
            try:
                pred, prob, *_ = mc.score(docs=[evidence[:4000]], claims=[claim[:500]])
                ok = bool(pred[0]) if pred is not None else False
                if not ok and isinstance(prob, (list, tuple)) and prob:
                    ok = float(prob[0]) >= 0.5
                return "entailment" if ok else "neutral"
            except Exception as e:
                logger.warning("MiniCheck score failed: %s", e)
    model = _get_nli()
    if model is None:
        return "entailment" if mock_entailed(claim, evidence) else "neutral"
    try:
        scores = model.predict([(evidence[:2000], claim[:500])])
        labels = ["contradiction", "entailment", "neutral"]
        import numpy as np

        arr = np.array(scores).reshape(-1)
        if arr.size >= 3:
            return labels[int(arr.argmax())]
        # Some checkpoints return a single entailment logit
        return "entailment" if float(arr[0]) > 0.0 else "neutral"
    except Exception as e:
        logger.warning("NLI predict failed: %s", e)
        return "entailment" if mock_entailed(claim, evidence) else "neutral"


def _citation_indexes(claim: str) -> Set[int]:
    return {int(n) for n in _CITE.findall(claim)}


def filter_answer(
    answer: str,
    chunks: Sequence,
) -> Tuple[str, List[str], Set[int]]:
    """Drop claims not entailed by retrieved chunks.

    Returns (filtered_text, dropped_claims, kept_citation_indexes 1-based).
    """
    evidence = evidence_text(chunks)
    claims = split_claims(answer)
    kept: List[str] = []
    dropped: List[str] = []
    kept_cites: Set[int] = set()
    for claim in claims:
        if claim.startswith("#"):
            kept.append(claim)
            continue
        label = nli_label(claim, evidence)
        if label == "entailment":
            kept.append(claim)
            kept_cites |= _citation_indexes(claim)
        else:
            dropped.append(claim)
    if not kept and claims:
        # Never return an empty answer if the model produced something; keep the
        # first claim that cites evidence, else the first claim.
        fallback = next((c for c in claims if _citation_indexes(c)), claims[0])
        kept = [fallback]
        dropped = [c for c in claims if c != fallback]
        kept_cites |= _citation_indexes(fallback)
    text = " ".join(kept).strip()
    # Restore markdown list items that were split out
    return text, dropped, kept_cites


def filter_citations(citations: List[dict], kept_indexes: Set[int]) -> List[dict]:
    if not kept_indexes:
        return citations
    filtered = []
    for i, cite in enumerate(citations, 1):
        if i in kept_indexes:
            filtered.append(cite)
    return filtered or citations
