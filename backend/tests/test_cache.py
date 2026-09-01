"""
Tests for cache service.
"""

import pytest
import numpy as np
from unittest.mock import AsyncMock, patch

from app.services.cache import CacheService


class TestCacheService:
    """Tests for CacheService."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.cache = CacheService()
    
    def test_compute_hash(self):
        """Test hash computation is consistent."""
        hash1 = self.cache._compute_hash("test query")
        hash2 = self.cache._compute_hash("test query")
        hash3 = self.cache._compute_hash("TEST QUERY")  # Case insensitive
        
        assert hash1 == hash2
        assert hash1 == hash3  # Case insensitive
    
    def test_compute_hash_different_inputs(self):
        """Test hash is different for different inputs."""
        hash1 = self.cache._compute_hash("query one")
        hash2 = self.cache._compute_hash("query two")
        
        assert hash1 != hash2
    
    def test_cosine_similarity_identical(self):
        """Test cosine similarity for identical vectors."""
        vec = [1.0, 2.0, 3.0, 4.0]
        similarity = self.cache._cosine_similarity(vec, vec)
        
        assert abs(similarity - 1.0) < 0.0001
    
    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity for orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = self.cache._cosine_similarity(vec1, vec2)
        
        assert abs(similarity) < 0.0001
    
    def test_cosine_similarity_opposite(self):
        """Test cosine similarity for opposite vectors."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]
        similarity = self.cache._cosine_similarity(vec1, vec2)
        
        assert abs(similarity + 1.0) < 0.0001
    
    def test_cosine_similarity_zero_vector(self):
        """Test cosine similarity with zero vector."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [0.0, 0.0, 0.0]
        similarity = self.cache._cosine_similarity(vec1, vec2)
        
        assert similarity == 0.0
    
    @pytest.mark.asyncio
    async def test_get_returns_none_without_redis(self):
        """Test get returns None when Redis is not configured."""
        cache = CacheService()
        cache.redis_url = ""
        
        result = await cache.get("test-key")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_returns_none_or_false_without_redis(self):
        """Test set returns None or False when Redis is not configured."""
        cache = CacheService()
        cache.redis_url = ""
        
        result = await cache.set("test-key", "value")
        
        # Returns None when execute returns None, or False if it returns non-OK
        assert result is None or result is False


class TestSemanticCaching:
    """Tests for semantic caching functionality."""
    
    @pytest.mark.asyncio
    async def test_semantic_cache_miss(self):
        """Test cache miss returns None."""
        cache = CacheService()
        cache.redis_url = ""  # Disable Redis
        
        result = await cache.get_semantic_cache("test query", [0.1] * 100)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_semantic_cache_threshold(self):
        """Test similarity threshold is respected."""
        cache = CacheService()
        
        # Threshold should be > 0.9
        assert cache.similarity_threshold > 0.9
