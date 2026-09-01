"""
Circuit Breaker pattern implementation for external service resilience.
Prevents cascading failures when services like Bedrock, Redis, or S3 are unavailable.
"""

import asyncio
import time
import logging
from enum import Enum
from typing import Optional, Callable, TypeVar
from functools import wraps
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Circuit tripped, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5          # Failures before opening circuit
    success_threshold: int = 2          # Successes before closing circuit
    timeout_seconds: float = 60.0       # Time before attempting recovery
    half_open_max_calls: int = 3        # Max calls allowed in half-open state


@dataclass
class CircuitStats:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_changes: int = 0


class CircuitOpenError(Exception):
    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker OPEN for {service_name}. Retry after {retry_after:.1f}s"
        )


class CircuitBreaker:
    """
    Circuit breaker for external service calls.
    
    States:
    - CLOSED: Normal operation. Failures are counted.
    - OPEN: Service considered down. All requests fail fast.
    - HALF_OPEN: Testing recovery. Limited requests allowed.
    """
    
    def __init__(
        self,
        service_name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        self.service_name = service_name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        self._stats = CircuitStats()
    
    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self._stats.state_changes += 1
                logger.info(f"Circuit {self.service_name} transitioning to HALF_OPEN")
        return self._state
    
    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.config.timeout_seconds
    
    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        self._stats.total_calls += 1
        
        async with self._lock:
            current_state = self.state
            
            if current_state == CircuitState.OPEN:
                self._stats.rejected_calls += 1
                retry_after = self.config.timeout_seconds - (
                    time.time() - (self._last_failure_time or 0)
                )
                raise CircuitOpenError(self.service_name, max(0, retry_after))
            
            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    self._stats.rejected_calls += 1
                    raise CircuitOpenError(self.service_name, 0)
                self._half_open_calls += 1
        
        # Execute the function (outside lock to allow concurrency)
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await self._on_success()
            return result
            
        except Exception:
            await self._on_failure()
            raise
    
    async def _on_success(self):
        async with self._lock:
            self._stats.successful_calls += 1
            self._stats.last_success_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    self._stats.state_changes += 1
                    logger.info(f"Circuit {self.service_name} CLOSED (recovered)")
            else:
                # Reset failure count on success in CLOSED state
                self._failure_count = 0
    
    async def _on_failure(self):
        async with self._lock:
            self._stats.failed_calls += 1
            self._stats.last_failure_time = time.time()
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # Immediately re-open on failure in half-open
                self._state = CircuitState.OPEN
                self._stats.state_changes += 1
                logger.warning(
                    f"Circuit {self.service_name} OPEN (recovery failed, "
                    f"timeout={self.config.timeout_seconds}s)"
                )
            else:
                self._failure_count += 1
                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._stats.state_changes += 1
                    logger.warning(
                        f"Circuit {self.service_name} OPEN "
                        f"(failures={self._failure_count}/{self.config.failure_threshold})"
                    )
    
    def get_stats(self) -> dict:
        return {
            "service_name": self.service_name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_calls": self._stats.total_calls,
            "successful_calls": self._stats.successful_calls,
            "failed_calls": self._stats.failed_calls,
            "rejected_calls": self._stats.rejected_calls,
            "last_failure_time": self._stats.last_failure_time,
            "last_success_time": self._stats.last_success_time,
            "state_changes": self._stats.state_changes,
        }
    
    def reset(self):
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time = None


def circuit_breaker(
    service_name: str,
    config: Optional[CircuitBreakerConfig] = None,
):
    breaker = CircuitBreaker(service_name, config)
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            return await breaker.call(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            return breaker.call(func, *args, **kwargs)
        
        # Attach breaker instance for inspection/testing
        wrapper = async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        wrapper.circuit_breaker = breaker
        return wrapper
    
    return decorator


# Global circuit breakers for external services
_bedrock_llm_circuit: Optional[CircuitBreaker] = None
_bedrock_embedding_circuit: Optional[CircuitBreaker] = None
_redis_circuit: Optional[CircuitBreaker] = None
_s3_circuit: Optional[CircuitBreaker] = None


def get_bedrock_llm_circuit() -> CircuitBreaker:
    global _bedrock_llm_circuit
    if _bedrock_llm_circuit is None:
        _bedrock_llm_circuit = CircuitBreaker(
            "bedrock-llm",
            CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout_seconds=30.0,
            )
        )
    return _bedrock_llm_circuit


def get_bedrock_embedding_circuit() -> CircuitBreaker:
    global _bedrock_embedding_circuit
    if _bedrock_embedding_circuit is None:
        _bedrock_embedding_circuit = CircuitBreaker(
            "bedrock-embedding",
            CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout_seconds=30.0,
            )
        )
    return _bedrock_embedding_circuit


def get_redis_circuit() -> CircuitBreaker:
    global _redis_circuit
    if _redis_circuit is None:
        _redis_circuit = CircuitBreaker(
            "redis",
            CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout_seconds=15.0,
            )
        )
    return _redis_circuit


def get_s3_circuit() -> CircuitBreaker:
    global _s3_circuit
    if _s3_circuit is None:
        _s3_circuit = CircuitBreaker(
            "s3",
            CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout_seconds=30.0,
            )
        )
    return _s3_circuit


def get_all_circuit_stats() -> dict:
    return {
        "bedrock_llm": get_bedrock_llm_circuit().get_stats(),
        "bedrock_embedding": get_bedrock_embedding_circuit().get_stats(),
        "redis": get_redis_circuit().get_stats(),
        "s3": get_s3_circuit().get_stats(),
    }


def reset_all_circuits():
    global _bedrock_llm_circuit, _bedrock_embedding_circuit, _redis_circuit, _s3_circuit
    for circuit in [_bedrock_llm_circuit, _bedrock_embedding_circuit, _redis_circuit, _s3_circuit]:
        if circuit:
            circuit.reset()