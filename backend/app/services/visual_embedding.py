"""CLIP visual embeddings (figures + table screenshots).

Real path: sentence-transformers clip-ViT-B-32 (512-d).
MOCK_LLM_AND_EMBEDDINGS: bag-of-words hash vector over caption/query text so
tests and local demo can rank without downloading CLIP.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from pathlib import Path
from typing import List, Optional, Sequence, Union

from app.core.config import settings

logger = logging.getLogger(__name__)

CLIP_DIM = 512

_clip_model = None
_clip_loading = False


def lexical_clip_vector(text: str, dim: int = CLIP_DIM) -> List[float]:
    """Deterministic 512-d vector from tokens. Shared tokens → closer vectors."""
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    if not tokens:
        tokens = ["empty"]
    vec = [0.0] * dim
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        for i in range(0, 16, 4):
            idx = int.from_bytes(digest[i : i + 4], "big") % dim
            sign = 1.0 if digest[i] % 2 == 0 else -1.0
            vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _get_clip():
    global _clip_model
    if _clip_model is False:
        return None
    if _clip_model is not None:
        return _clip_model
    try:
        from sentence_transformers import SentenceTransformer

        _clip_model = SentenceTransformer(settings.CLIP_MODEL_ID)
        logger.info("CLIP model loaded (%s)", settings.CLIP_MODEL_ID)
        return _clip_model
    except Exception as e:
        logger.warning("CLIP unavailable: %s", e)
        _clip_model = False
        return None


def warm_clip():
    global _clip_loading
    if settings.MOCK_LLM_AND_EMBEDDINGS or _clip_model is not None or _clip_loading:
        return
    _clip_loading = True
    import threading

    def _load():
        _get_clip()

    threading.Thread(target=_load, daemon=True).start()


class VisualEmbeddingService:
    embedding_dim = CLIP_DIM

    def _use_mock(self) -> bool:
        return bool(getattr(settings, "MOCK_LLM_AND_EMBEDDINGS", False))

    def embed_query(self, text: str) -> List[float]:
        if self._use_mock():
            return lexical_clip_vector(text, self.embedding_dim)
        model = _get_clip()
        if model is None:
            return lexical_clip_vector(text, self.embedding_dim)
        vec = model.encode([text], normalize_embeddings=True)[0]
        return [float(x) for x in vec]

    def embed_image(
        self,
        source: Union[str, Path, bytes],
        caption: Optional[str] = None,
    ) -> List[float]:
        if self._use_mock():
            return lexical_clip_vector(caption or "", self.embedding_dim)
        model = _get_clip()
        if model is None:
            return lexical_clip_vector(caption or "", self.embedding_dim)
        try:
            from PIL import Image
            import io

            if isinstance(source, (bytes, bytearray)):
                img = Image.open(io.BytesIO(source)).convert("RGB")
            else:
                img = Image.open(str(source)).convert("RGB")
            vec = model.encode([img], normalize_embeddings=True)[0]
            return [float(x) for x in vec]
        except Exception as e:
            logger.warning("CLIP image embed failed, falling back to caption: %s", e)
            return lexical_clip_vector(caption or "", self.embedding_dim)

    def embed_images(
        self,
        sources: Sequence[Union[str, Path, bytes]],
        captions: Optional[Sequence[Optional[str]]] = None,
    ) -> List[List[float]]:
        caps = list(captions or [None] * len(sources))
        return [self.embed_image(src, caps[i] if i < len(caps) else None) for i, src in enumerate(sources)]


visual_embedding_service = VisualEmbeddingService()
