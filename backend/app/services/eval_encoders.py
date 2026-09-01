"""Local eval encoders (BGE dense + CLIP vision). Production Titan path is unchanged."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Sequence, Union

import numpy as np

from app.core.config import settings
from app.services.visual_embedding import lexical_clip_vector

logger = logging.getLogger(__name__)


def real_encoders_enabled() -> bool:
    return bool(getattr(settings, "EVAL_REAL_ENCODERS", False)) and not getattr(
        settings, "MOCK_LLM_AND_EMBEDDINGS", False
    )


@lru_cache(maxsize=1)
def _dense_model():
    from sentence_transformers import SentenceTransformer

    name = getattr(settings, "EVAL_DENSE_MODEL", "BAAI/bge-small-en-v1.5")
    logger.info("Loading eval dense encoder %s", name)
    return SentenceTransformer(name)


@lru_cache(maxsize=1)
def _vision_model():
    from sentence_transformers import SentenceTransformer

    name = getattr(settings, "EVAL_VISION_MODEL", "clip-ViT-B-32")
    logger.info("Loading eval vision encoder %s", name)
    return SentenceTransformer(name)


def encode_texts(texts: Sequence[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    if not real_encoders_enabled():
        vecs = [lexical_clip_vector(t, 384) for t in texts]
        arr = np.array(vecs, dtype=np.float32)
        return arr
    model = _dense_model()
    return np.array(model.encode(list(texts), normalize_embeddings=True), dtype=np.float32)


def encode_query(text: str) -> np.ndarray:
    return encode_texts([text])[0]


def encode_images(sources: Sequence[Union[bytes, str]]) -> np.ndarray:
    if not sources:
        return np.zeros((0, 512), dtype=np.float32)
    if not real_encoders_enabled():
        # lexical stand-in cannot see pixels; caller should pass captions via encode_texts
        return np.zeros((len(sources), 512), dtype=np.float32)
    from io import BytesIO
    from PIL import Image

    model = _vision_model()
    images = []
    for src in sources:
        if isinstance(src, (bytes, bytearray)):
            images.append(Image.open(BytesIO(src)).convert("RGB"))
        else:
            images.append(Image.open(str(src)).convert("RGB"))
    return np.array(model.encode(images, normalize_embeddings=True), dtype=np.float32)


def cosine_topk(query: np.ndarray, matrix: np.ndarray, k: int) -> List[tuple]:
    if matrix.size == 0:
        return []
    q = query / (np.linalg.norm(query) + 1e-9)
    m = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9)
    scores = m @ q
    k = min(k, len(scores))
    idx = np.argpartition(-scores, k - 1)[:k]
    idx = idx[np.argsort(-scores[idx])]
    return [(int(i), float(scores[i])) for i in idx]
