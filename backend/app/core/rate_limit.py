"""
Rate limiting middleware for API protection.
Uses Redis for distributed rate limiting with fallback to in-memory.
"""

import time
from typing import Dict, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass
from functools import wraps
import logging

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10  # Max requests in 1 second


class RateLimiter:
    """
    Token bucket rate limiter with Redis backend and in-memory fallback.
    Provides per-user and per-IP rate limiting.
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._memory_store: Dict[str, list] = defaultdict(list)
        self._redis = None
        self._redis_available = False
        
    async def _get_redis(self):
        if self._redis is not None:
            return self._redis if self._redis_available else None
            
        try:
            from app.services.cache import cache_service
            if cache_service._redis:
                self._redis = cache_service._redis
                self._redis_available = True
                return self._redis
        except Exception as e:
            logger.debug(f"Redis not available for rate limiting: {e}")
            self._redis_available = False
        return None
    
    def _get_client_id(self, request: Request, user_id: Optional[str] = None) -> str:
        if user_id:
            return f"user:{user_id}"
        
        # Fallback to IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"
    
    async def _check_redis(self, key: str, window_seconds: int, max_requests: int) -> Tuple[bool, int]:
        redis = await self._get_redis()
        if not redis:
            return await self._check_memory(key, window_seconds, max_requests)
        
        try:
            now = time.time()
            window_start = now - window_seconds
            
            # Use sorted set for sliding window
            redis_key = f"ratelimit:{key}:{window_seconds}"
            
            # Remove old entries
            await redis.zremrangebyscore(redis_key, 0, window_start)
            
            # Count current requests
            count = await redis.zcard(redis_key)
            
            if count >= max_requests:
                return False, max_requests - count
            
            # Add current request
            await redis.zadd(redis_key, {str(now): now})
            await redis.expire(redis_key, window_seconds + 1)
            
            return True, max_requests - count - 1
            
        except Exception as e:
            logger.warning(f"Redis rate limit failed, using memory: {e}")
            return await self._check_memory(key, window_seconds, max_requests)
    
    async def _check_memory(self, key: str, window_seconds: int, max_requests: int) -> Tuple[bool, int]:
        now = time.time()
        window_start = now - window_seconds
        
        # Clean old entries
        self._memory_store[key] = [t for t in self._memory_store[key] if t > window_start]
        
        count = len(self._memory_store[key])
        
        if count >= max_requests:
            return False, 0
        
        self._memory_store[key].append(now)
        return True, max_requests - count - 1
    
    async def check_rate_limit(
        self, 
        request: Request, 
        user_id: Optional[str] = None
    ) -> Tuple[bool, Dict[str, int]]:
        """Check if request is within rate limits."""
        client_id = self._get_client_id(request, user_id)
        
        # Check per-minute limit
        allowed_minute, remaining_minute = await self._check_redis(
            f"{client_id}:minute", 
            60, 
            self.config.requests_per_minute
        )
        
        if not allowed_minute:
            return False, {
                "X-RateLimit-Limit": str(self.config.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + 60),
                "Retry-After": "60",
            }
        
        # Check per-hour limit
        allowed_hour, remaining_hour = await self._check_redis(
            f"{client_id}:hour",
            3600,
            self.config.requests_per_hour
        )
        
        if not allowed_hour:
            return False, {
                "X-RateLimit-Limit": str(self.config.requests_per_hour),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + 3600),
                "Retry-After": "3600",
            }
        
        return True, {
            "X-RateLimit-Limit": str(self.config.requests_per_minute),
            "X-RateLimit-Remaining": str(remaining_minute),
            "X-RateLimit-Reset": str(int(time.time()) + 60),
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


# Endpoint-specific limiters
chat_limiter = RateLimiter(RateLimitConfig(
    requests_per_minute=150,  # Allow benchmark (26 accuracy + 100 cache)
    requests_per_hour=500,
    burst_limit=20,
))

upload_limiter = RateLimiter(RateLimitConfig(
    requests_per_minute=10,  # Uploads are heavy
    requests_per_hour=100,
    burst_limit=3,
))


def rate_limit(limiter: RateLimiter = rate_limiter):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find request in args/kwargs
            request = kwargs.get('request')
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if request:
                user = kwargs.get('user') or kwargs.get('current_user')
                user_id = user.id if user and hasattr(user, 'id') else None
                
                allowed, headers = await limiter.check_rate_limit(request, user_id)
                
                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded. Please try again later.",
                        headers=headers,
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
