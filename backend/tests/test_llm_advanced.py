"""Advanced tests for LLM service."""

import pytest
import json
from unittest.mock import MagicMock, patch
from app.services.llm import LLMService


class TestLLMRequestBuilding:
    """Tests for request body building."""

    def test_build_nova_request_basic(self):
        """Test Nova request body structure."""
        service = LLMService()
        service.is_nova = True
        
        body = service._build_request_body("Hello", max_tokens=100)
        
        assert "messages" in body
        assert body["messages"][0]["role"] == "user"
        assert body["inferenceConfig"]["maxTokens"] == 100

    def test_build_nova_request_with_system(self):
        """Test Nova request with system prompt."""
        service = LLMService()
        service.is_nova = True
        
        body = service._build_request_body("Hello", system_prompt="You are helpful")
        
        assert "system" in body
        assert body["system"][0]["text"] == "You are helpful"

    def test_build_claude_request_basic(self):
        """Test Claude request body structure."""
        service = LLMService()
        service.is_nova = False
        
        body = service._build_request_body("Hello", max_tokens=100)
        
        assert "anthropic_version" in body
        assert body["max_tokens"] == 100
        assert body["messages"][0]["content"] == "Hello"

    def test_build_claude_request_with_system(self):
        """Test Claude request with system prompt."""
        service = LLMService()
        service.is_nova = False
        
        body = service._build_request_body("Hello", system_prompt="Be helpful")
        
        assert body["system"] == "Be helpful"


class TestLLMResponseExtraction:
    """Tests for response extraction."""

    def test_extract_nova_response(self):
        """Test extracting text from Nova response."""
        service = LLMService()
        service.is_nova = True
        
        response = {
            "output": {
                "message": {
                    "content": [{"text": "Hello back!"}]
                }
            }
        }
        
        result = service._extract_response_text(response)
        
        assert result == "Hello back!"

    def test_extract_claude_response(self):
        """Test extracting text from Claude response."""
        service = LLMService()
        service.is_nova = False
        
        response = {
            "content": [{"text": "Hello from Claude!"}]
        }
        
        result = service._extract_response_text(response)
        
        assert result == "Hello from Claude!"


class TestQueryRouting:
    """Tests for query routing logic."""

    @pytest.mark.asyncio
    async def test_route_query_parses_semantic(self):
        """Test routing parses SEMANTIC response."""
        service = LLMService()
        service.generate = MagicMock(return_value="SEMANTIC")
        
        # Make it awaitable
        import asyncio
        async def mock_generate(*args, **kwargs):
            return "SEMANTIC"
        service.generate = mock_generate
        
        result = await service.route_query("What does this mean?")
        
        assert result == "SEMANTIC"

    @pytest.mark.asyncio
    async def test_route_query_parses_keyword(self):
        """Test routing parses KEYWORD response."""
        service = LLMService()
        
        async def mock_generate(*args, **kwargs):
            return "KEYWORD"
        service.generate = mock_generate
        
        result = await service.route_query("Find John Smith")
        
        assert result == "KEYWORD"

    @pytest.mark.asyncio
    async def test_route_query_defaults_hybrid(self):
        """Test routing defaults to HYBRID for invalid response."""
        service = LLMService()
        
        async def mock_generate(*args, **kwargs):
            return "INVALID_STRATEGY"
        service.generate = mock_generate
        
        result = await service.route_query("test")
        
        assert result == "HYBRID"

    @pytest.mark.asyncio
    async def test_route_query_handles_empty(self):
        """Test routing handles empty response."""
        service = LLMService()
        
        async def mock_generate(*args, **kwargs):
            return ""
        service.generate = mock_generate
        
        result = await service.route_query("test")
        
        assert result == "HYBRID"

    @pytest.mark.asyncio
    async def test_route_query_strips_whitespace(self):
        """Test routing strips whitespace from response."""
        service = LLMService()
        
        async def mock_generate(*args, **kwargs):
            return "  SEMANTIC  \n"
        service.generate = mock_generate
        
        result = await service.route_query("test")
        
        assert result == "SEMANTIC"


class TestModelDetection:
    """Tests for model type detection."""

    def test_is_nova_detection_true(self):
        """Test Nova model detection."""
        with patch("app.services.llm.settings") as mock_settings:
            mock_settings.AWS_REGION = "us-east-1"
            mock_settings.AWS_ACCESS_KEY_ID = "test"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test"
            mock_settings.BEDROCK_MODEL_ID = "amazon.nova-pro-v1:0"
            
            with patch("boto3.client"):
                service = LLMService()
                assert service.is_nova is True

    def test_is_nova_detection_false(self):
        """Test Claude model detection."""
        with patch("app.services.llm.settings") as mock_settings:
            mock_settings.AWS_REGION = "us-east-1"
            mock_settings.AWS_ACCESS_KEY_ID = "test"
            mock_settings.AWS_SECRET_ACCESS_KEY = "test"
            mock_settings.BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet"
            
            with patch("boto3.client"):
                service = LLMService()
                assert service.is_nova is False
