"""Tests for rate limiting middleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time


class TestRateLimitConfig:
    """Test RateLimitConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        from app.core.rate_limit import RateLimitConfig
        
        config = RateLimitConfig()
        
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_limit == 10
    
    def test_custom_config(self):
        """Test custom configuration."""
        from app.core.rate_limit import RateLimitConfig
        
        config = RateLimitConfig(
            requests_per_minute=30,
            requests_per_hour=500,
            burst_limit=5,
        )
        
        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 500
        assert config.burst_limit == 5


class TestRateLimiter:
    """Test RateLimiter class."""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes correctly."""
        from app.core.rate_limit import RateLimiter, RateLimitConfig
        
        limiter = RateLimiter()
        assert limiter.config is not None
        
        custom_config = RateLimitConfig(requests_per_minute=10)
        limiter2 = RateLimiter(config=custom_config)
        assert limiter2.config.requests_per_minute == 10
    
    def test_get_client_id_with_user(self):
        """Test client ID extraction with user."""
        from app.core.rate_limit import RateLimiter
        
        limiter = RateLimiter()
        mock_request = MagicMock()
        
        client_id = limiter._get_client_id(mock_request, user_id="user-123")
        
        assert client_id == "user:user-123"
    
    def test_get_client_id_with_ip(self):
        """Test client ID extraction from IP."""
        from app.core.rate_limit import RateLimiter
        
        limiter = RateLimiter()
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "192.168.1.1"
        
        client_id = limiter._get_client_id(mock_request, user_id=None)
        
        assert client_id == "ip:192.168.1.1"
    
    def test_get_client_id_with_forwarded(self):
        """Test client ID extraction from X-Forwarded-For."""
        from app.core.rate_limit import RateLimiter
        
        limiter = RateLimiter()
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "10.0.0.1, 10.0.0.2"
        
        client_id = limiter._get_client_id(mock_request, user_id=None)
        
        assert client_id == "ip:10.0.0.1"
    
    @pytest.mark.asyncio
    async def test_check_memory_allows_requests(self):
        """Test memory-based rate limiting allows requests."""
        from app.core.rate_limit import RateLimiter
        
        limiter = RateLimiter()
        
        allowed, remaining = await limiter._check_memory("test-key", 60, 10)
        
        assert allowed is True
        assert remaining == 9
    
    @pytest.mark.asyncio
    async def test_check_memory_blocks_excess(self):
        """Test memory-based rate limiting blocks excess requests."""
        from app.core.rate_limit import RateLimiter
        
        limiter = RateLimiter()
        
        # Make 10 requests
        for _ in range(10):
            await limiter._check_memory("block-test", 60, 10)
        
        # 11th should be blocked
        allowed, remaining = await limiter._check_memory("block-test", 60, 10)
        
        assert allowed is False
        assert remaining == 0
    
    @pytest.mark.asyncio
    async def test_check_rate_limit(self):
        """Test full rate limit check."""
        from app.core.rate_limit import RateLimiter
        
        limiter = RateLimiter()
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.client.host = "test-ip"
        
        allowed, headers = await limiter.check_rate_limit(mock_request)
        
        assert allowed is True
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers


class TestRateLimitInstances:
    """Test rate limiter instances."""
    
    def test_global_limiter_exists(self):
        """Test global rate limiter exists."""
        from app.core.rate_limit import rate_limiter
        
        assert rate_limiter is not None
    
    def test_chat_limiter_exists(self):
        """Test chat-specific limiter exists."""
        from app.core.rate_limit import chat_limiter
        
        assert chat_limiter is not None
        assert chat_limiter.config.requests_per_minute >= 20  # 150 for benchmark
    
    def test_upload_limiter_exists(self):
        """Test upload-specific limiter exists."""
        from app.core.rate_limit import upload_limiter
        
        assert upload_limiter is not None
        assert upload_limiter.config.requests_per_minute == 10


class TestRateLimitDecorator:
    """Test rate limit decorator."""
    
    def test_decorator_exists(self):
        """Test rate_limit decorator exists."""
        from app.core.rate_limit import rate_limit
        
        assert callable(rate_limit)
    
    def test_decorator_returns_function(self):
        """Test decorator returns a function."""
        from app.core.rate_limit import rate_limit, rate_limiter
        
        @rate_limit(rate_limiter)
        async def dummy_endpoint():
            return "OK"
        
        assert callable(dummy_endpoint)
