"""
Observability module: structured logging, metrics collection, and Prometheus export.
"""

import logging
import time
import json
from typing import Dict, Any, Optional, Callable
from functools import wraps

from app.core.utils import utc_now
from collections import defaultdict
from contextlib import contextmanager
import asyncio
import inspect

from app.core.request_context import get_request_id


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter with automatic request_id injection."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": utc_now().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        request_id = get_request_id()
        if request_id:
            log_data["request_id"] = request_id

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


def setup_logging(level: str = "INFO", structured: bool = True):
    """Configure application logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    handler = logging.StreamHandler()
    
    if structured:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        ))
    
    root_logger.addHandler(handler)
    
    # Set levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)


class MetricsCollector:
    """
    Metrics collector with Prometheus-compatible export.
    Supports counters, gauges, and histograms.
    """
    
    def __init__(self):
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, list] = defaultdict(list)
        self.timers: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    def increment(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None):
        """Increment a counter."""
        key = self._make_key(name, labels)
        self.counters[key] += value
    
    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge value."""
        key = self._make_key(name, labels)
        self.gauges[key] = value
    
    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a histogram observation."""
        key = self._make_key(name, labels)
        self.histograms[key].append(value)
        # Keep only last 1000 observations
        if len(self.histograms[key]) > 1000:
            self.histograms[key] = self.histograms[key][-1000:]
    
    def timer(self, name: str, labels: Optional[Dict[str, str]] = None):
        """Return a context manager for timing operations."""
        return _Timer(self, name, labels)
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create a metric key with optional labels."""
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary."""
        result = {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {},
            "timers": {},
        }
        
        # Calculate histogram stats
        for name, values in self.histograms.items():
            if values:
                sorted_vals = sorted(values)
                result["histograms"][name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "p50": sorted_vals[len(values) // 2],
                    "p95": sorted_vals[int(len(values) * 0.95)] if len(values) >= 20 else sorted_vals[-1],
                    "p99": sorted_vals[int(len(values) * 0.99)] if len(values) >= 100 else sorted_vals[-1],
                }
        
        # Calculate timer stats
        for name, values in self.timers.items():
            if values:
                sorted_vals = sorted(values)
                result["timers"][name] = {
                    "count": len(values),
                    "min_ms": min(values) * 1000,
                    "max_ms": max(values) * 1000,
                    "avg_ms": (sum(values) / len(values)) * 1000,
                    "p50_ms": sorted_vals[len(values) // 2] * 1000,
                    "p95_ms": sorted_vals[int(len(values) * 0.95)] * 1000 if len(values) >= 20 else sorted_vals[-1] * 1000,
                }
        
        return result
    
    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus text format.
        Compatible with /metrics endpoint scraping.
        """
        lines = []
        
        # Export counters
        for key, value in self.counters.items():
            name = key.split("{")[0]
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{key} {value}")
        
        # Export gauges
        for key, value in self.gauges.items():
            name = key.split("{")[0]
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{key} {value}")
        
        # Export histograms as summary
        for key, values in self.histograms.items():
            if not values:
                continue
            name = key.split("{")[0]
            sorted_vals = sorted(values)
            
            lines.append(f"# TYPE {name} summary")
            
            # Build quantile metric name
            if "{" in key:
                base = key.rstrip("}")
                q50_key = f'{base},quantile="0.5"}}'
                q95_key = f'{base},quantile="0.95"}}'
            else:
                q50_key = f'{key}{{quantile="0.5"}}'
                q95_key = f'{key}{{quantile="0.95"}}'
            
            lines.append(f"{q50_key} {sorted_vals[len(values) // 2]}")
            if len(values) >= 20:
                lines.append(f"{q95_key} {sorted_vals[int(len(values) * 0.95)]}")
            lines.append(f"{name}_count {len(values)}")
            lines.append(f"{name}_sum {sum(values)}")
        
        # Export timers as histograms
        for key, values in self.timers.items():
            if not values:
                continue
            name = key.split("{")[0] + "_seconds"
            
            lines.append(f"# TYPE {name} histogram")
            lines.append(f"{name}_count {len(values)}")
            lines.append(f"{name}_sum {sum(values)}")
            
            # Buckets
            buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
            for bucket in buckets:
                count = sum(1 for v in values if v <= bucket)
                lines.append(f'{name}_bucket{{le="{bucket}"}} {count}')
            lines.append(f'{name}_bucket{{le="+Inf"}} {len(values)}')
        
        return "\n".join(lines)
    
    def reset(self):
        """Reset all metrics."""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
        self.timers.clear()


class _Timer:
    """Context manager for timing operations."""
    
    def __init__(self, collector: MetricsCollector, name: str, labels: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.name = name
        self.labels = labels
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.perf_counter() - self.start_time
        key = self.collector._make_key(self.name, self.labels)
        self.collector.timers[key].append(elapsed)
        if len(self.collector.timers[key]) > 1000:
            self.collector.timers[key] = self.collector.timers[key][-1000:]


# Global metrics instance
metrics = MetricsCollector()


def track_time(name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to track function execution time."""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with metrics.timer(name, labels):
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with metrics.timer(name, labels):
                return func(*args, **kwargs)
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def track_count(name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to count function calls."""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            metrics.increment(name, labels=labels)
            try:
                return await func(*args, **kwargs)
            except Exception:
                metrics.increment(f"{name}_errors", labels=labels)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            metrics.increment(name, labels=labels)
            try:
                return func(*args, **kwargs)
            except Exception:
                metrics.increment(f"{name}_errors", labels=labels)
                raise
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


class RequestTracer:
    """Simple request tracing for debugging."""
    
    def __init__(self):
        self.traces: Dict[str, list] = {}
    
    def start_trace(self, trace_id: str, name: str) -> Dict[str, Any]:
        """Start a new trace span."""
        span = {
            "trace_id": trace_id,
            "name": name,
            "start_time": time.perf_counter(),
            "end_time": None,
            "duration_ms": None,
            "metadata": {},
        }
        
        if trace_id not in self.traces:
            self.traces[trace_id] = []
        self.traces[trace_id].append(span)
        
        return span
    
    def end_trace(self, span: Dict[str, Any]):
        """End a trace span."""
        span["end_time"] = time.perf_counter()
        span["duration_ms"] = (span["end_time"] - span["start_time"]) * 1000
    
    def get_trace(self, trace_id: str) -> Optional[list]:
        """Get all spans for a trace."""
        return self.traces.get(trace_id)
    
    @contextmanager
    def span(self, trace_id: str, name: str):
        """Context manager for tracing a span."""
        span = self.start_trace(trace_id, name)
        try:
            yield span
        finally:
            self.end_trace(span)


# Global tracer instance
tracer = RequestTracer()
