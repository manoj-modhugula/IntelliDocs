"""
Query cache with exact and semantic matching.

Uses Upstash REST when REST URL+token are set, otherwise a native redis://
connection (Docker Compose). Falls back to process memory if Redis is down.
"""

import json
import hashlib
import threading
import time
import logging
import numpy as np
from typing import Any, Optional, List
from collections import OrderedDict
import httpx

from app.core.config import settings
from app.core.circuit_breaker import get_redis_circuit, CircuitOpenError

logger = logging.getLogger(__name__)


class CacheService:
    """Redis caching service with semantic caching and LRU eviction."""
    
    # Maximum entries in memory cache to prevent memory leaks
    MAX_MEMORY_CACHE_SIZE = 10000
    # Evict this percentage when max is reached
    EVICTION_RATIO = 0.1
    
    def __init__(self):
        self.redis_url = settings.UPSTASH_REDIS_REST_URL
        self.redis_token = settings.UPSTASH_REDIS_REST_TOKEN
        self.redis_native_url = getattr(settings, "REDIS_URL", "") or ""
        self.headers = {
            "Authorization": f"Bearer {self.redis_token}",
            "Content-Type": "application/json",
        }
        self.similarity_threshold = settings.SEMANTIC_CACHE_THRESHOLD
        self.cache_ttl = settings.CACHE_TTL_SECONDS
        self._memory: OrderedDict = OrderedDict()
        self._memory_ttl: dict = {}
        self._memory_lock = threading.RLock()
        self._native_redis = None
        self._use_upstash = bool(self.redis_url and self.redis_token)
        self._use_native = (not self._use_upstash) and self.redis_native_url.startswith(
            ("redis://", "rediss://")
        )
        self._use_redis = self._use_upstash or self._use_native
        self._redis_available = True
        self._metrics = {
            "exact_hits": 0,
            "semantic_hits": 0,
            "memory_evictions": 0,
            "redis_fallbacks": 0,
        }

        if not self._use_redis:
            logger.warning("Redis not configured; using in-memory cache only")
        elif self._use_native:
            logger.info("Redis cache using native protocol at REDIS_URL")
        else:
            logger.info("Redis cache using Upstash REST")
    
    def _evict_lru(self, count: int) -> None:
        """Evict oldest entries from memory cache (LRU policy)."""
        with self._memory_lock:
            keys_to_remove = list(self._memory.keys())[:count]
            for key in keys_to_remove:
                self._memory.pop(key, None)
                self._memory_ttl.pop(key, None)
                self._metrics["memory_evictions"] += 1
    
    def _touch_memory(self, key: str) -> None:
        """Move key to end of OrderedDict (mark as recently used)."""
        with self._memory_lock:
            if key in self._memory:
                self._memory.move_to_end(key)
    
    async def _get_native_client(self):
        if self._native_redis is None:
            import redis.asyncio as redis_async

            self._native_redis = redis_async.from_url(
                self.redis_native_url, decode_responses=True
            )
        return self._native_redis

    async def _execute_native(self, command: List[str]) -> Any:
        client = await self._get_native_client()
        op = command[0].upper()
        args = command[1:]
        if op == "GET":
            return await client.get(*args)
        if op == "SET":
            if len(args) >= 4 and str(args[2]).upper() == "EX":
                ok = await client.set(args[0], args[1], ex=int(args[3]))
            else:
                ok = await client.set(args[0], args[1])
            return "OK" if ok else None
        if op == "DEL":
            return await client.delete(*args)
        if op == "SADD":
            return await client.sadd(args[0], *args[1:])
        if op == "SMEMBERS":
            members = await client.smembers(args[0])
            return list(members) if members else []
        if op == "SCARD":
            return await client.scard(args[0])
        if op == "EXPIRE":
            return await client.expire(args[0], int(args[1]))
        if op == "PING":
            pong = await client.ping()
            return "PONG" if pong else None
        raise ValueError(f"Unsupported Redis command: {op}")

    async def _execute(self, command: List[str]) -> Any:
        if not self._use_redis:
            return None

        circuit = get_redis_circuit()

        try:
            async def _redis_call():
                if self._use_native:
                    result = await self._execute_native(command)
                    self._redis_available = True
                    return result

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.redis_url,
                        headers=self.headers,
                        json=command,
                        timeout=5.0,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        result = data.get("result")
                        self._redis_available = True
                        return result
                    if response.status_code >= 500:
                        raise Exception(f"Redis server error: {response.status_code}")
                    return None

            return await circuit.call(_redis_call)

        except CircuitOpenError as e:
            logger.warning("Redis circuit open: %s", e)
            self._redis_available = False
            self._metrics["redis_fallbacks"] += 1
            return None
        except Exception as e:
            logger.warning("Redis command failed: %s", e)
            self._redis_available = False
            self._metrics["redis_fallbacks"] += 1
            return None
    
    async def get(self, key: str) -> Optional[str]:
        """Get a value from cache. Always check memory first (works without Redis)."""
        with self._memory_lock:
            if key in self._memory:
                # Check TTL
                if self._memory_ttl.get(key, 0) > time.time():
                    # Mark as recently used
                    self._memory.move_to_end(key)
                    return self._memory[key]
                else:
                    # Expired, remove it
                    self._memory.pop(key, None)
                    self._memory_ttl.pop(key, None)
        
        # Try Redis if available
        if self._use_redis and self._redis_available:
            val = await self._execute(["GET", key])
            if val:
                with self._memory_lock:
                    self._memory[key] = val
                    self._memory_ttl[key] = time.time() + self.cache_ttl
                    # Enforce size limit
                    if len(self._memory) > self.MAX_MEMORY_CACHE_SIZE:
                        self._evict_lru(int(self.MAX_MEMORY_CACHE_SIZE * self.EVICTION_RATIO))
                return val
        return None
    
    async def set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """Set a value in cache with LRU eviction. Always store in memory."""
        with self._memory_lock:
            # If key exists, move to end (most recently used)
            if key in self._memory:
                self._memory.move_to_end(key)
            self._memory[key] = value
            self._memory_ttl[key] = time.time() + ttl
            
            # Enforce size limit with LRU eviction
            if len(self._memory) > self.MAX_MEMORY_CACHE_SIZE:
                self._evict_lru(int(self.MAX_MEMORY_CACHE_SIZE * self.EVICTION_RATIO))
        
        # Try Redis if available
        if self._use_redis and self._redis_available:
            result = await self._execute(["SET", key, value, "EX", str(ttl)])
            return result == "OK"
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete a key from cache (memory + Redis)."""
        with self._memory_lock:
            self._memory.pop(key, None)
            self._memory_ttl.pop(key, None)
        if self._use_redis:
            result = await self._execute(["DEL", key])
            return result == 1
        return True
    
    def _compute_hash(self, text: str) -> str:
        """Compute a hash of the text for exact matching."""
        return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:16]
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        a_np = np.array(a)
        b_np = np.array(b)
        dot_product = np.dot(a_np, b_np)
        norm_a = np.linalg.norm(a_np)
        norm_b = np.linalg.norm(b_np)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
    
    async def get_semantic_cache(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Get cached response for a semantically similar query.

        1. First checks exact match (hash-based)
        2. Then checks semantic similarity using embeddings

        Workspace-scoped when workspace_id is provided.
        """
        query_hash = self._compute_hash(query)
        ns = f"rag:w:{workspace_id}" if workspace_id else "rag"

        exact_key = f"rag:exact:{ns}:{query_hash}"
        exact_result = await self.get(exact_key)
        if exact_result:
            try:
                self._metrics["exact_hits"] += 1
                return json.loads(exact_result)
            except json.JSONDecodeError:
                pass

        if query_embedding:
            semantic_index_key = f"rag:semantic:index:{ns}"
            index_members = await self._execute(["SMEMBERS", semantic_index_key])

            if index_members and isinstance(index_members, list):
                keys_to_check = list(index_members)[:100]

                for cache_key in keys_to_check:
                    full_key = f"rag:semantic:{ns}:{cache_key}"
                    cached_data = await self.get(full_key)
                    if cached_data:
                        try:
                            cached = json.loads(cached_data)
                            cached_embedding = cached.get("embedding")
                            if cached_embedding:
                                similarity = self._cosine_similarity(
                                    query_embedding,
                                    cached_embedding,
                                )
                                if similarity >= self.similarity_threshold:
                                    self._metrics["semantic_hits"] += 1
                                    return cached.get("response")
                        except json.JSONDecodeError:
                            pass

        return None
    
    async def set_semantic_cache(
        self,
        query: str,
        response: dict,
        query_embedding: Optional[List[float]] = None,
        workspace_id: Optional[str] = None,
    ) -> bool:
        """
        Cache a response with both exact and semantic matching support.
        Also maintains an index set for efficient semantic lookups.
        Workspace-scoped when workspace_id is provided.
        Uses adaptive TTL: time-sensitive queries cache shorter.
        """
        query_hash = self._compute_hash(query)
        ns = f"rag:w:{workspace_id}" if workspace_id else "rag"
        adaptive_ttl = _get_adaptive_cache_ttl(query, self.cache_ttl)

        exact_key = f"rag:exact:{ns}:{query_hash}"
        await self.set(exact_key, json.dumps(response), adaptive_ttl)

        if query_embedding:
            semantic_key = f"rag:semantic:{ns}:{query_hash}"
            semantic_data = {
                "query": query,
                "embedding": query_embedding,
                "response": response,
            }
            await self.set(semantic_key, json.dumps(semantic_data), adaptive_ttl)

            semantic_index_key = f"rag:semantic:index:{ns}"
            await self._execute(["SADD", semantic_index_key, query_hash])
            await self._execute(["EXPIRE", semantic_index_key, adaptive_ttl])

        return True
    
    async def invalidate_document_cache(self, document_id: str) -> int:
        """
        Invalidate all cached queries related to a document.
        Uses SCAN instead of KEYS for Redis Cluster compatibility.
        """
        deleted_count = 0
        
        # Clear memory cache first
        with self._memory_lock:
            keys_to_delete = [k for k in self._memory.keys() if k.startswith("rag:")]
            for key in keys_to_delete:
                self._memory.pop(key, None)
                self._memory_ttl.pop(key, None)
                deleted_count += 1
        
        # For Redis, we use a pattern-based approach with tracking
        # In production, consider using Redis keyspace notifications or a separate index
        cache_index_key = "rag:cache:index"
        cached_keys = await self._execute(["SMEMBERS", cache_index_key])
        
        if cached_keys and isinstance(cached_keys, list):
            for key in cached_keys:
                await self.delete(key)
                deleted_count += 1
            await self._execute(["DEL", cache_index_key])
        
        logger.info(f"Invalidated {deleted_count} cache entries for document {document_id}")
        return deleted_count
    
    async def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        with self._memory_lock:
            memory_entries = len(self._memory)
            memory_expired = sum(
                1 for key in self._memory 
                if self._memory_ttl.get(key, 0) <= time.time()
            )
        
        # Use index sets instead of KEYS
        
        exact_index = await self._execute(["SCARD", "rag:exact:index"]) or 0
        semantic_index = await self._execute(["SCARD", "rag:semantic:index"]) or 0
        
        return {
            "memory_entries": memory_entries,
            "memory_expired": memory_expired,
            "memory_active": memory_entries - memory_expired,
            "redis_exact_entries": exact_index if self._redis_available else 0,
            "redis_semantic_entries": semantic_index if self._redis_available else 0,
            "exact_cache_entries": exact_index,
            "semantic_cache_entries": semantic_index,
            "total_entries": exact_index + semantic_index + memory_entries,
            "redis_available": self._redis_available,
            "metrics": self._metrics,
        }

    def reset_metrics(self) -> None:
        """Reset in-memory cache hit counters."""
        self._metrics = {
            "exact_hits": 0,
            "semantic_hits": 0,
            "memory_evictions": 0,
            "redis_fallbacks": 0,
        }

    def get_metrics(self) -> dict:
        """Return cache metrics."""
        with self._memory_lock:
            return {
                **dict(self._metrics),
                "memory_size": len(self._memory),
                "redis_available": self._redis_available,
            }

    def clear_memory_cache(self) -> None:
        """Clear in-memory cache (useful for benchmarks)."""
        with self._memory_lock:
            self._memory.clear()
            self._memory_ttl.clear()
    
    def set_redis_available(self, available: bool) -> None:
        """Manually set Redis availability status."""
        self._redis_available = available


_STALE_QUERY_PATTERNS = [
    "latest", "current", "recent", "newest", "updated",
    "news", "announcement", "2024", "2025", "2026",
    "as of", "as of today", "now",
]
_SHORT_TTL_SECONDS = 3600  # 1 hour for time-sensitive queries
_LONG_TTL_SECONDS = 604800  # 7 days for stable factual queries


def _is_time_sensitive_query(query: str) -> bool:
    """Detect queries that are likely to change over time."""
    q = query.lower()
    return any(p in q for p in _STALE_QUERY_PATTERNS)


def _get_adaptive_cache_ttl(query: str, base_ttl: int) -> int:
    """
    Return a TTL based on query characteristics.
    Time-sensitive queries get shorter TTLs; stable factual queries get longer ones.
    """
    if _is_time_sensitive_query(query):
        return min(_SHORT_TTL_SECONDS, base_ttl)
    return base_ttl


# Singleton instance
cache_service = CacheService()
