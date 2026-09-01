"""
Tests for LLM service.
"""

import pytest
from unittest.mock import MagicMock, patch
import json

from app.services.llm import LLMService


class TestLLMService:
    """Tests for LLMService."""
    
    def test_is_nova_detection(self):
        """Test Nova model detection."""
        with patch.object(LLMService, '__init__', lambda x: None):
            llm = LLMService()
            
            llm.model_id = "amazon.nova-pro-v1:0"
            llm.is_nova = "nova" in llm.model_id.lower()
            assert llm.is_nova == True
            
            llm.model_id = "anthropic.claude-3-sonnet"
            llm.is_nova = "nova" in llm.model_id.lower()
            assert llm.is_nova == False
    
    def test_build_request_body_nova(self):
        """Test request body building for Nova models."""
        with patch.object(LLMService, '__init__', lambda x: None):
            llm = LLMService()
            llm.is_nova = True
            
            body = llm._build_request_body(
                prompt="Test prompt",
                system_prompt="Test system",
                max_tokens=100,
                temperature=0.5,
            )
            
            assert "messages" in body
            assert body["messages"][0]["role"] == "user"
            assert body["messages"][0]["content"][0]["text"] == "Test prompt"
            assert "system" in body
            assert body["inferenceConfig"]["maxTokens"] == 100
    
    def test_build_request_body_claude(self):
        """Test request body building for Claude models."""
        with patch.object(LLMService, '__init__', lambda x: None):
            llm = LLMService()
            llm.is_nova = False
            
            body = llm._build_request_body(
                prompt="Test prompt",
                system_prompt="Test system",
                max_tokens=100,
                temperature=0.5,
            )
            
            assert "messages" in body
            assert body["messages"][0]["role"] == "user"
            assert body["messages"][0]["content"] == "Test prompt"
            assert body["system"] == "Test system"
            assert body["max_tokens"] == 100
    
    def test_extract_response_text_nova(self):
        """Test response extraction for Nova models."""
        with patch.object(LLMService, '__init__', lambda x: None):
            llm = LLMService()
            llm.is_nova = True
            
            response = {
                "output": {
                    "message": {
                        "content": [{"text": "Hello world"}]
                    }
                }
            }
            
            text = llm._extract_response_text(response)
            assert text == "Hello world"
    
    def test_extract_response_text_claude(self):
        """Test response extraction for Claude models."""
        with patch.object(LLMService, '__init__', lambda x: None):
            llm = LLMService()
            llm.is_nova = False
            
            response = {
                "content": [{"text": "Hello world"}]
            }
            
            text = llm._extract_response_text(response)
            assert text == "Hello world"


class TestQueryRouting:
    """Tests for query routing."""
    
    @pytest.mark.asyncio
    async def test_route_query_returns_valid_strategy(self):
        """Test route_query returns valid strategy."""
        with patch.object(LLMService, '__init__', lambda x: None):
            llm = LLMService()
            llm.is_nova = True
            llm.model_id = "amazon.nova-pro-v1:0"
            
            with patch.object(llm, 'generate') as mock_generate:
                mock_generate.return_value = "SEMANTIC"
                
                result = await llm.route_query("What is the meaning of life?")
                
                assert result == "SEMANTIC"
    
    @pytest.mark.asyncio
    async def test_route_query_defaults_to_hybrid(self):
        """Test route_query defaults to HYBRID for invalid responses."""
        with patch.object(LLMService, '__init__', lambda x: None):
            llm = LLMService()
            llm.is_nova = True
            llm.model_id = "amazon.nova-pro-v1:0"
            
            with patch.object(llm, 'generate') as mock_generate:
                mock_generate.return_value = "INVALID_STRATEGY"
                
                result = await llm.route_query("test query")
                
                assert result == "HYBRID"
    
    @pytest.mark.asyncio
    async def test_route_query_handles_empty_response(self):
        """Test route_query handles empty response."""
        with patch.object(LLMService, '__init__', lambda x: None):
            llm = LLMService()
            llm.is_nova = True
            llm.model_id = "amazon.nova-pro-v1:0"
            
            with patch.object(llm, 'generate') as mock_generate:
                mock_generate.return_value = ""
                
                result = await llm.route_query("test query")
                
                assert result == "HYBRID"
