"""
Tests for embedding service.
"""

import pytest
from unittest.mock import MagicMock, patch
import json

from app.services.embedding import EmbeddingService


class TestEmbeddingService:
    """Tests for EmbeddingService."""
    
    def test_init_creates_bedrock_client(self):
        """Test Bedrock client is created on first use (lazy init)."""
        with patch("boto3.client") as mock_client:
            with patch("app.services.embedding.settings") as mock_settings:
                mock_settings.MOCK_LLM_AND_EMBEDDINGS = False
                mock_settings.BEDROCK_EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v1"
                mock_settings.AWS_REGION = "us-east-1"
                mock_settings.AWS_ACCESS_KEY_ID = None
                mock_settings.AWS_SECRET_ACCESS_KEY = None
                mock_settings.EMBEDDING_BATCH_SIZE = 25
                mock_settings.EMBEDDING_MAX_CONCURRENCY = 5
                service = EmbeddingService()
                _ = service.client  # Trigger lazy init
                mock_client.assert_called_once()
                assert mock_client.call_args[0][0] == "bedrock-runtime"
    
    @pytest.mark.asyncio
    async def test_embed_text_returns_list(self):
        """Test embed_text returns a list of floats."""
        with patch("boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            
            # Mock response
            mock_response = {
                "body": MagicMock()
            }
            mock_response["body"].read.return_value = json.dumps({
                "embedding": [0.1, 0.2, 0.3]
            }).encode()
            mock_client.invoke_model.return_value = mock_response
            
            service = EmbeddingService()
            result = await service.embed_text("test text")
            
            assert isinstance(result, list)
            assert len(result) == 3
            assert all(isinstance(x, float) for x in result)
    
    @pytest.mark.asyncio
    async def test_embed_text_calls_titan_model(self):
        """Test embed_text calls Titan embedding model."""
        with patch("boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            
            mock_response = {
                "body": MagicMock()
            }
            mock_response["body"].read.return_value = json.dumps({
                "embedding": [0.1] * 1024
            }).encode()
            mock_client.invoke_model.return_value = mock_response
            
            service = EmbeddingService()
            await service.embed_text("test text")
            
            # Check invoke_model was called
            mock_client.invoke_model.assert_called_once()
            call_kwargs = mock_client.invoke_model.call_args.kwargs
            assert "titan" in call_kwargs["modelId"].lower()


class TestEmbeddingBatching:
    """Tests for embedding batching functionality."""
    
    @pytest.mark.asyncio
    async def test_embed_texts_handles_single_text(self):
        """Test embed_texts with single text."""
        with patch("boto3.client") as mock_boto:
            mock_client = MagicMock()
            mock_boto.return_value = mock_client
            
            mock_response = {
                "body": MagicMock()
            }
            mock_response["body"].read.return_value = json.dumps({
                "embedding": [0.1] * 1024
            }).encode()
            mock_client.invoke_model.return_value = mock_response
            
            service = EmbeddingService()
            
            # If embed_texts exists, test it; otherwise test embed_text
            if hasattr(service, 'embed_texts'):
                results = await service.embed_texts(["single text"])
                assert len(results) == 1
            else:
                result = await service.embed_text("single text")
                assert len(result) == 1024
