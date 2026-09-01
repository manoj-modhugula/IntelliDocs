"""Tests for LLM service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json


class TestLLMServiceInit:
    """Tests for LLM service initialization."""
    
    def test_service_initialization(self):
        """Test LLM service initializes with boto3 client."""
        with patch('boto3.client') as mock_client:
            from app.services.llm import LLMService
            service = LLMService()
            
            assert service.client is not None
            assert service.max_retries == 3
    
    def test_service_model_id(self):
        """Test LLM service uses correct model ID."""
        with patch('boto3.client'):
            from app.services.llm import LLMService
            service = LLMService()
            
            assert service.model_id is not None
    
    def test_is_nova_detection(self):
        """Test Nova model detection."""
        with patch('boto3.client'):
            with patch('app.core.config.settings') as mock_settings:
                mock_settings.BEDROCK_MODEL_ID = "amazon.nova-pro-v1:0"
                mock_settings.AWS_REGION = "us-east-1"
                mock_settings.AWS_ACCESS_KEY_ID = "test"
                mock_settings.AWS_SECRET_ACCESS_KEY = "test"
                
                from app.services.llm import LLMService
                service = LLMService()
                
                assert service.is_nova is True


class TestBuildRequestBody:
    """Tests for request body building."""
    
    def test_build_request_body_nova(self):
        """Test request body for Nova models."""
        with patch('boto3.client'):
            from app.services.llm import LLMService
            service = LLMService()
            service.is_nova = True
            
            body = service._build_request_body(
                prompt="Test prompt",
                system_prompt="System prompt",
                max_tokens=100,
                temperature=0.5
            )
            
            assert "messages" in body or "inferenceConfig" in body
    
    def test_build_request_body_claude(self):
        """Test request body for Claude models."""
        with patch('boto3.client'):
            from app.services.llm import LLMService
            service = LLMService()
            service.is_nova = False
            
            body = service._build_request_body(
                prompt="Test prompt",
                system_prompt=None,
                max_tokens=100,
                temperature=0.7
            )
            
            assert "messages" in body


class TestRouteQuery:
    """Tests for query routing."""
    
    @pytest.mark.asyncio
    async def test_route_query_returns_strategy(self):
        """Test route_query returns a valid strategy."""
        with patch('boto3.client') as mock_client:
            from app.services.llm import LLMService
            service = LLMService()
            
            # Mock the invoke response
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({
                "output": {"message": {"content": [{"text": "SEMANTIC"}]}}
            }).encode()
            service.client.invoke_model = MagicMock(return_value={
                "body": mock_response
            })
            
            strategy = await service.route_query("What is AI?")
            
            # Should return a valid strategy
            assert strategy in ["SEMANTIC", "KEYWORD", "HYBRID", "STRUCTURED"]
    
    @pytest.mark.asyncio
    async def test_route_query_default_on_error(self):
        """Test route_query returns HYBRID on error."""
        with patch('boto3.client') as mock_client:
            from app.services.llm import LLMService
            service = LLMService()
            
            # Mock an error
            service.client.invoke_model = MagicMock(side_effect=Exception("Test error"))
            
            strategy = await service.route_query("Test query")
            
            assert strategy == "HYBRID"


class TestLLMExceptions:
    """Tests for LLM custom exceptions."""
    
    def test_llm_service_error(self):
        """Test LLMServiceError exception."""
        from app.services.llm import LLMServiceError
        
        error = LLMServiceError("Test error")
        assert str(error) == "Test error"
    
    def test_llm_rate_limit_error(self):
        """Test LLMRateLimitError exception."""
        from app.services.llm import LLMRateLimitError
        
        error = LLMRateLimitError("Rate limited")
        assert str(error) == "Rate limited"


class TestLLMFactory:
    """Tests for LLM service factory."""
    
    def test_create_llm_service(self):
        """Test factory creates new service."""
        with patch('boto3.client'):
            from app.services.llm import create_llm_service
            
            service = create_llm_service()
            
            assert service is not None
            assert hasattr(service, 'generate')
            assert hasattr(service, 'route_query')
