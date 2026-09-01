"""Advanced tests for cache service to increase coverage."""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.cache import CacheService


class TestCacheServiceExecution:
    """Tests for cache execution methods."""

    @pytest.mark.asyncio
    async def test_execute_returns_none_without_credentials(self):
        """Test _execute returns None when Redis not configured."""
        cache = CacheService()
        cache.redis_url = ""
        cache.redis_token = ""
        
        result = await cache._execute(["GET", "test"])
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_handles_timeout(self):
        """Test _execute handles timeout gracefully."""
        cache = CacheService()
        cache.redis_url = "https://fake.redis.io"
        cache.redis_token = "fake-token"
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=Exception("Timeout"))
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            result = await cache._execute(["GET", "test"])
            assert result is None

    @pytest.mark.asyncio
    async def test_execute_handles_non_200(self):
        """Test _execute handles non-200 responses."""
        cache = CacheService()
        cache.redis_url = "https://fake.redis.io"
        cache.redis_token = "fake-token"
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            result = await cache._execute(["GET", "test"])
            assert result is None

    @pytest.mark.asyncio
    async def test_get_calls_execute(self):
        """Test get method calls _execute."""
        cache = CacheService()
        cache._execute = AsyncMock(return_value="value")
        
        result = await cache.get("test-key")
        
        cache._execute.assert_called_once_with(["GET", "test-key"])
        assert result == "value"

    @pytest.mark.asyncio
    async def test_set_calls_execute_with_ttl(self):
        """Test set method calls _execute with TTL."""
        cache = CacheService()
        cache._execute = AsyncMock(return_value="OK")
        
        result = await cache.set("key", "value", ttl=3600)
        
        cache._execute.assert_called_once_with(["SET", "key", "value", "EX", "3600"])
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_calls_execute(self):
        """Test delete method calls _execute."""
        cache = CacheService()
        cache._execute = AsyncMock(return_value=1)
        
        result = await cache.delete("key")
        
        cache._execute.assert_called_once_with(["DEL", "key"])
        assert result is True


class TestSemanticCacheAdvanced:
    """Advanced semantic cache tests."""

    @pytest.mark.asyncio
    async def test_get_semantic_cache_exact_match(self):
        """Test exact match path in semantic cache."""
        cache = CacheService()
        
        # Mock exact match found
        cache.get = AsyncMock(return_value=json.dumps({"answer": "cached"}))
        
        result = await cache.get_semantic_cache("test query")
        
        assert result == {"answer": "cached"}

    @pytest.mark.asyncio
    async def test_get_semantic_cache_json_error(self):
        """Test handling of JSON decode error."""
        cache = CacheService()
        
        # Return invalid JSON
        cache.get = AsyncMock(return_value="not valid json")
        cache._execute = AsyncMock(return_value=None)
        
        result = await cache.get_semantic_cache("test query")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_set_semantic_cache_stores_both(self):
        """Test that set_semantic_cache stores exact and semantic."""
        cache = CacheService()
        cache.set = AsyncMock(return_value=True)
        
        result = await cache.set_semantic_cache(
            "test query",
            {"answer": "test"},
            query_embedding=[0.1, 0.2, 0.3]
        )
        
        assert result is True
        assert cache.set.call_count == 2  # exact + semantic

    @pytest.mark.asyncio
    async def test_invalidate_document_cache(self):
        """Test cache invalidation."""
        cache = CacheService()
        cache._execute = AsyncMock(return_value=["key1", "key2"])
        cache.delete = AsyncMock(return_value=True)
        
        count = await cache.invalidate_document_cache("doc-123")
        
        assert count == 2
        assert cache.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_get_cache_stats(self):
        """Test cache stats retrieval."""
        cache = CacheService()
        cache._execute = AsyncMock(side_effect=[
            ["exact1", "exact2"],  # exact keys
            ["sem1"],  # semantic keys
        ])
        
        stats = await cache.get_cache_stats()
        
        assert stats["exact_cache_entries"] == 2
        assert stats["semantic_cache_entries"] == 1
        assert stats["total_entries"] == 3


class TestCosineSimAdvanced:
    """Additional cosine similarity tests."""

    def test_cosine_identical_long_vectors(self):
        """Test cosine similarity with longer identical vectors."""
        cache = CacheService()
        vec = [0.1] * 100
        
        result = cache._cosine_similarity(vec, vec)
        
        assert abs(result - 1.0) < 0.0001

    def test_cosine_random_vectors(self):
        """Test cosine similarity with random-ish vectors."""
        cache = CacheService()
        
        vec1 = [0.1, 0.2, 0.3, 0.4, 0.5]
        vec2 = [0.5, 0.4, 0.3, 0.2, 0.1]
        
        result = cache._cosine_similarity(vec1, vec2)
        
        # Should be positive but less than 1
        assert 0 < result < 1

    def test_hash_consistency(self):
        """Test hash function is consistent."""
        cache = CacheService()
        
        hash1 = cache._compute_hash("test query")
        hash2 = cache._compute_hash("test query")
        hash3 = cache._compute_hash("TEST QUERY")  # Case insensitive
        
        assert hash1 == hash2
        assert hash1 == hash3
