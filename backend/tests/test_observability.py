"""Tests for observability module."""

import pytest
import logging
import json
from datetime import datetime

from app.core.observability import MetricsCollector, RequestTracer, track_time, track_count, StructuredFormatter
from app.core.request_context import setup_request_context, clear_request_context


class TestStructuredFormatter:
    """Tests for StructuredFormatter with request_id injection."""

    def setup_method(self):
        clear_request_context()

    def teardown_method(self):
        clear_request_context()

    def _format_log(self, record: logging.LogRecord) -> str:
        formatter = StructuredFormatter()
        return formatter.format(record)

    def test_formatter_includes_timestamp_level_logger_module(self, caplog):
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )
        output = self._format_log(record)
        parsed = json.loads(output)

        assert "timestamp" in parsed
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "test message"

    def test_formatter_injects_request_id_from_context(self):
        setup_request_context("req-xyz789", logging.getLogger("ctx"))
        record = logging.LogRecord(
            name="test.rag",
            level=logging.INFO,
            pathname="rag.py",
            lineno=42,
            msg="Processing query",
            args=(),
            exc_info=None,
        )

        output = self._format_log(record)
        parsed = json.loads(output)

        assert parsed["request_id"] == "req-xyz789"

    def test_formatter_no_request_id_when_context_cleared(self):
        clear_request_context()
        record = logging.LogRecord(
            name="test.rag",
            level=logging.INFO,
            pathname="rag.py",
            lineno=42,
            msg="Processing query",
            args=(),
            exc_info=None,
        )

        output = self._format_log(record)
        parsed = json.loads(output)

        assert "request_id" not in parsed

    def test_formatter_includes_exception_on_error(self):
        setup_request_context("req-exc", logging.getLogger("exc"))
        record = logging.LogRecord(
            name="test.exc",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="error occurred",
            args=(),
            exc_info=(ValueError, ValueError("boom"), None),
        )

        output = self._format_log(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    def test_increment_counter(self):
        """Test incrementing a counter."""
        metrics = MetricsCollector()
        
        metrics.increment("test_counter")
        metrics.increment("test_counter")
        metrics.increment("test_counter", value=3)
        
        assert metrics.counters["test_counter"] == 5
    
    def test_increment_with_labels(self):
        """Test incrementing a counter with labels."""
        metrics = MetricsCollector()
        
        metrics.increment("http_requests", labels={"method": "GET", "status": "200"})
        metrics.increment("http_requests", labels={"method": "POST", "status": "201"})
        
        assert 'http_requests{method="GET",status="200"}' in metrics.counters
        assert 'http_requests{method="POST",status="201"}' in metrics.counters
    
    def test_set_gauge(self):
        """Test setting a gauge value."""
        metrics = MetricsCollector()
        
        metrics.gauge("active_connections", 42)
        
        assert metrics.gauges["active_connections"] == 42
        
        # Update gauge
        metrics.gauge("active_connections", 100)
        assert metrics.gauges["active_connections"] == 100
    
    def test_record_histogram(self):
        """Test recording histogram observations."""
        metrics = MetricsCollector()
        
        metrics.histogram("response_time", 0.1)
        metrics.histogram("response_time", 0.2)
        metrics.histogram("response_time", 0.15)
        
        assert len(metrics.histograms["response_time"]) == 3
    
    def test_timer_context_manager(self):
        """Test timer context manager."""
        metrics = MetricsCollector()
        
        with metrics.timer("operation_time"):
            # Simulate work
            _ = sum(range(1000))
        
        assert len(metrics.timers["operation_time"]) == 1
        assert metrics.timers["operation_time"][0] > 0
    
    def test_get_metrics(self):
        """Test getting all metrics."""
        metrics = MetricsCollector()
        
        metrics.increment("counter1")
        metrics.gauge("gauge1", 10)
        metrics.histogram("hist1", 5)
        
        result = metrics.get_metrics()
        
        assert "counters" in result
        assert "gauges" in result
        assert "histograms" in result
        assert "timers" in result
        
        assert result["counters"]["counter1"] == 1
        assert result["gauges"]["gauge1"] == 10
    
    def test_histogram_stats(self):
        """Test histogram statistics calculation."""
        metrics = MetricsCollector()
        
        for i in range(100):
            metrics.histogram("latency", i * 0.01)
        
        result = metrics.get_metrics()
        stats = result["histograms"]["latency"]
        
        assert stats["count"] == 100
        assert stats["min"] == 0.0
        assert stats["max"] == 0.99
        assert "p50" in stats
        assert "p95" in stats
    
    def test_export_prometheus(self):
        """Test Prometheus format export."""
        metrics = MetricsCollector()
        
        metrics.increment("http_requests_total")
        metrics.gauge("active_users", 42)
        
        output = metrics.export_prometheus()
        
        assert "http_requests_total" in output
        assert "active_users 42" in output
    
    def test_reset(self):
        """Test resetting metrics."""
        metrics = MetricsCollector()
        
        metrics.increment("counter1")
        metrics.gauge("gauge1", 10)
        
        metrics.reset()
        
        assert len(metrics.counters) == 0
        assert len(metrics.gauges) == 0


class TestRequestTracer:
    """Tests for RequestTracer."""
    
    def test_start_and_end_trace(self):
        """Test starting and ending a trace."""
        tracer = RequestTracer()
        
        span = tracer.start_trace("trace-123", "database_query")
        assert span["name"] == "database_query"
        assert span["trace_id"] == "trace-123"
        assert span["end_time"] is None
        
        tracer.end_trace(span)
        assert span["end_time"] is not None
        assert span["duration_ms"] is not None
        assert span["duration_ms"] > 0
    
    def test_span_context_manager(self):
        """Test span context manager."""
        tracer = RequestTracer()
        
        with tracer.span("trace-456", "processing") as span:
            # Simulate work
            _ = sum(range(1000))
        
        assert span["duration_ms"] is not None
    
    def test_get_trace(self):
        """Test getting a trace."""
        tracer = RequestTracer()
        
        tracer.start_trace("trace-789", "span1")
        tracer.start_trace("trace-789", "span2")
        
        trace = tracer.get_trace("trace-789")
        
        assert trace is not None
        assert len(trace) == 2


class TestDecorators:
    """Tests for metric decorators."""
    
    def test_track_time_sync(self):
        """Test track_time decorator on sync function."""
        from app.core.observability import metrics
        metrics.reset()
        
        @track_time("test_function")
        def slow_function():
            return sum(range(10000))
        
        result = slow_function()
        
        assert result == sum(range(10000))
        assert len(metrics.timers["test_function"]) == 1
    
    @pytest.mark.asyncio
    async def test_track_time_async(self):
        """Test track_time decorator on async function."""
        from app.core.observability import metrics
        metrics.reset()
        
        @track_time("async_function")
        async def async_slow_function():
            return sum(range(10000))
        
        result = await async_slow_function()
        
        assert result == sum(range(10000))
        assert len(metrics.timers["async_function"]) == 1
    
    def test_track_count_sync(self):
        """Test track_count decorator on sync function."""
        from app.core.observability import metrics
        metrics.reset()
        
        @track_count("function_calls")
        def counted_function():
            return "done"
        
        counted_function()
        counted_function()
        counted_function()
        
        assert metrics.counters["function_calls"] == 3
