"""Full tests for embedding service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json


class TestEmbeddingService:
    """Tests for EmbeddingService."""
    
    def test_service_initialization(self):
        """Test service initializes correctly."""
        with patch('boto3.client'):
            from app.services.embedding import EmbeddingService
            service = EmbeddingService()
            
            assert service.embedding_dim == 1024
            assert service.max_retries == 3
            assert service.batch_size >= 5  # May be higher for throughput
    
    def test_cache_key_generation(self):
        """Test cache key is consistent."""
        with patch('boto3.client'):
            from app.services.embedding import EmbeddingService
            service = EmbeddingService()
            
            key1 = service._get_cache_key("hello world")
            key2 = service._get_cache_key("hello world")
            key3 = service._get_cache_key("different text")
            
            assert key1 == key2
            assert key1 != key3
    
    def test_get_metrics(self):
        """Test metrics retrieval."""
        with patch('boto3.client'):
            from app.services.embedding import EmbeddingService
            service = EmbeddingService()
            
            metrics = service.get_metrics()
            
            assert 'total_embeddings' in metrics
            assert 'cache_hits' in metrics
            assert 'cache_hit_rate' in metrics
            assert 'avg_embedding_time_ms' in metrics
    
    def test_clear_cache(self):
        """Test cache clearing."""
        with patch('boto3.client'):
            from app.services.embedding import EmbeddingService
            service = EmbeddingService()
            
            # Add something to cache
            service._cache["test"] = [0.1] * 1024
            assert len(service._cache) == 1
            
            service.clear_cache()
            assert len(service._cache) == 0
    
    @pytest.mark.asyncio
    async def test_embed_text_uses_cache(self):
        """Test that embed_text uses cache for repeated texts."""
        with patch('boto3.client') as mock_boto:
            from app.services.embedding import EmbeddingService
            service = EmbeddingService()
            
            # Pre-populate cache
            cached_embedding = [0.5] * 1024
            service._cache[service._get_cache_key("cached text")] = cached_embedding
            
            # Should return cached value without API call
            result = await service.embed_text("cached text")
            
            assert result == cached_embedding
            assert service.cache_hits == 1
    
    @pytest.mark.asyncio
    async def test_embed_texts_empty(self):
        """Test embed_texts with empty list."""
        with patch('boto3.client'):
            from app.services.embedding import EmbeddingService
            service = EmbeddingService()
            
            result = await service.embed_texts([])
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_embed_texts_all_cached(self):
        """Test embed_texts when all texts are cached."""
        with patch('boto3.client'):
            from app.services.embedding import EmbeddingService
            service = EmbeddingService()
            
            texts = ["text1", "text2"]
            for text in texts:
                service._cache[service._get_cache_key(text)] = [0.1] * 1024
            
            results = await service.embed_texts(texts)
            
            assert len(results) == 2
            assert service.cache_hits == 2


class TestEmbeddingFactory:
    """Tests for embedding service factory."""
    
    def test_create_embedding_service(self):
        """Test factory creates new service."""
        with patch('boto3.client'):
            from app.services.embedding import create_embedding_service
            
            service = create_embedding_service()
            
            assert service is not None
            assert hasattr(service, 'embed_text')
            assert hasattr(service, 'embed_texts')
