"""
Embedding service using AWS Bedrock Titan with parallel processing.
Implements batch embedding with concurrent API calls for improved throughput.
Supports MOCK_LLM_AND_EMBEDDINGS for cost-free benchmarking.
Includes circuit breaker for resilience.
"""

import hashlib
import json
import asyncio
import logging
import math
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import time
import random
from collections import OrderedDict

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.circuit_breaker import get_bedrock_embedding_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

# Thread pool for parallel embedding calls
_executor = ThreadPoolExecutor(max_workers=10)


class EmbeddingService:
    """
    Service for generating embeddings using AWS Bedrock Titan.
    Supports parallel batch processing for improved throughput.
    """
    
    def __init__(self):
        self._client = None
        self.model_id = settings.BEDROCK_EMBEDDING_MODEL_ID
        self.embedding_dim = 1024
        self.max_retries = 3
        self.batch_size = settings.EMBEDDING_BATCH_SIZE
        self.total_embeddings = 0
        self.total_time_ms = 0
        self.cache_hits = 0
        self.throttle_count = 0
        self._cache: OrderedDict[str, List[float]] = OrderedDict()
        self._cache_max_size = 1000
        self._semaphore = asyncio.Semaphore(settings.EMBEDDING_MAX_CONCURRENCY)
        self._rate_lock = asyncio.Lock()
        self._last_request_ts = 0.0

    def _cache_get(self, cache_key: str) -> Optional[List[float]]:
        """Get from cache and mark as recently used."""
        value = self._cache.get(cache_key)
        if value is not None:
            self._cache.move_to_end(cache_key)
        return value

    def _cache_set(self, cache_key: str, value: List[float]) -> None:
        """Set cache value with simple LRU eviction."""
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
        self._cache[cache_key] = value
        if len(self._cache) > self._cache_max_size:
            self._cache.popitem(last=False)

    @property
    def client(self):
        """Lazy init to avoid AWS cred errors when MOCK_LLM_AND_EMBEDDINGS is True."""
        if self._client is None:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
        return self._client
    
    def _sync_embed(self, text: str) -> List[float]:
        """Synchronous embedding call (runs in thread pool)."""
        # Truncate to avoid token limit
        truncated = text[:8000] if len(text) > 8000 else text
        
        body = json.dumps({
            "inputText": truncated,
            "dimensions": self.embedding_dim,
            "normalize": True,
        })
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )
                
                response_body = json.loads(response["body"].read())
                return response_body["embedding"]
                
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ["ThrottlingException", "ServiceUnavailableException"]:
                    wait_time = (2 ** attempt) * 0.5
                    jitter_range = wait_time * 0.25
                    wait_time += random.uniform(-jitter_range, jitter_range)
                    wait_time = max(0.1, wait_time)
                    logger.warning(f"Embedding throttled, retrying in {wait_time:.2f}s")
                    self.throttle_count += 1
                    time.sleep(wait_time)
                else:
                    raise
        
        raise Exception(f"Failed to generate embedding after {self.max_retries} attempts")
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(text.encode()).hexdigest()

    def _mock_embed(self, text: str) -> List[float]:
        """Deterministic fake embedding for cost-free benchmarking (no AWS)."""
        h = hashlib.sha256(text.encode()).hexdigest()
        dim = self.embedding_dim
        return [math.sin(i * 0.1 + int(h[:8], 16) % 100) * 0.1 for i in range(dim)]
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text with caching and circuit breaker."""
        if getattr(settings, "MOCK_LLM_AND_EMBEDDINGS", False):
            return self._mock_embed(text)
        
        # Check cache
        cache_key = self._get_cache_key(text)
        cached = self._cache_get(cache_key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        
        circuit = get_bedrock_embedding_circuit()
        
        # Generate embedding with rate limiting and circuit breaker
        start = time.perf_counter()
        loop = asyncio.get_event_loop()
        
        async def _do_embed():
            async with self._semaphore:
                await self._throttle()
                return await loop.run_in_executor(_executor, partial(self._sync_embed, text))
        
        try:
            embedding = await circuit.call(_do_embed)
        except CircuitOpenError as e:
            logger.warning(f"Embedding circuit open, returning zero embedding: {e}")
            embedding = [0.0] * self.embedding_dim
        except Exception as e:
            logger.warning(f"Embedding failed, returning zero embedding: {e}")
            embedding = [0.0] * self.embedding_dim
        
        elapsed = (time.perf_counter() - start) * 1000
        
        # Update metrics
        self.total_embeddings += 1
        self.total_time_ms += elapsed
        
        # Cache result
        self._cache_set(cache_key, embedding)
        
        return embedding
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with parallel processing.
        Uses concurrent API calls for improved throughput.
        Includes circuit breaker for resilience.
        """
        if not texts:
            return []
        if getattr(settings, "MOCK_LLM_AND_EMBEDDINGS", False):
            return [self._mock_embed(t) for t in texts]

        circuit = get_bedrock_embedding_circuit()

        if circuit.state.value == "open":
            logger.warning("Embedding circuit open, returning zero embeddings")
            return [[0.0] * self.embedding_dim for _ in texts]

        start_time = time.perf_counter()
        results: List[Optional[List[float]]] = [None] * len(texts)

        # Check cache first
        uncached_indices = []
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            cached = self._cache_get(cache_key)
            if cached is not None:
                results[i] = cached
                self.cache_hits += 1
            else:
                uncached_indices.append(i)

        if not uncached_indices:
            return results

        # Adapt batch size based on average text length.
        # Titan embed-text-v2 accepts ~8192 tokens per call.
        # Short texts (<500 chars) can be batched densely; long texts need smaller batches.
        uncached_texts = [texts[i] for i in uncached_indices]
        avg_len = sum(len(t) for t in uncached_texts) / len(uncached_texts)
        base_batch = self.batch_size
        if avg_len < 300:
            adaptive_batch = min(base_batch * 2, 32)
        elif avg_len > 2000:
            adaptive_batch = max(base_batch // 2, 4)
        else:
            adaptive_batch = base_batch

        # Process uncached texts in parallel batches
        loop = asyncio.get_event_loop()

        async def embed_with_index(idx: int) -> tuple:
            text = texts[idx]
            async with self._semaphore:
                await self._throttle()
                embedding = await loop.run_in_executor(
                    _executor,
                    partial(self._sync_embed, text)
                )
            return idx, embedding

        # Process in batches to avoid overwhelming the API
        for batch_start in range(0, len(uncached_indices), adaptive_batch):
            batch_indices = uncached_indices[batch_start:batch_start + adaptive_batch]
            
            # Create concurrent tasks
            tasks = [embed_with_index(idx) for idx in batch_indices]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Embedding failed: {result}")
                    continue
                    
                idx, embedding = result
                results[idx] = embedding
                
                # Cache the result
                cache_key = self._get_cache_key(texts[idx])
                self._cache_set(cache_key, embedding)
        
        # Fill any failed embeddings with zeros
        for i, result in enumerate(results):
            if result is None:
                results[i] = [0.0] * self.embedding_dim
        
        elapsed = time.perf_counter() - start_time
        self.total_embeddings += len(uncached_indices)
        self.total_time_ms += elapsed * 1000
        
        texts_per_second = len(texts) / elapsed if elapsed > 0 else 0
        logger.info(
            f"Generated {len(texts)} embeddings in {elapsed:.2f}s "
            f"({texts_per_second:.1f}/sec, {len(texts) - len(uncached_indices)} cached)"
        )
        
        return results
    
    def get_metrics(self) -> dict:
        """Get embedding service metrics."""
        avg_time = self.total_time_ms / self.total_embeddings if self.total_embeddings > 0 else 0
        return {
            "total_embeddings": self.total_embeddings,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": self.cache_hits / (self.total_embeddings + self.cache_hits) if (self.total_embeddings + self.cache_hits) > 0 else 0,
            "avg_embedding_time_ms": avg_time,
            "throttle_count": self.throttle_count,
            "cache_size": len(self._cache),
        }

    async def _throttle(self) -> None:
        """Rate-limit embedding calls to reduce Bedrock throttling."""
        rps = max(settings.EMBEDDING_RPS, 0.1)
        min_interval = 1.0 / rps
        jitter = settings.EMBEDDING_JITTER_MS / 1000.0
        async with self._rate_lock:
            now = time.perf_counter()
            elapsed = now - self._last_request_ts
            if elapsed < min_interval:
                await asyncio.sleep((min_interval - elapsed) + random.random() * jitter)
            self._last_request_ts = time.perf_counter()
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self._cache.clear()


# Singleton instance
embedding_service = EmbeddingService()


def create_embedding_service() -> EmbeddingService:
    """Factory function for dependency injection."""
    return EmbeddingService()
