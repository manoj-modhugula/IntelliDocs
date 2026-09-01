"""Tests for request_context module."""

import pytest
import logging

from app.core.request_context import (
    get_request_id,
    set_request_id,
    get_request_logger,
    setup_request_context,
    clear_request_context,
    request_logger,
)


class TestRequestContext:
    """Tests for request context variables."""

    def setup_method(self):
        clear_request_context()

    def teardown_method(self):
        clear_request_context()

    def test_get_request_id_returns_none_when_not_set(self):
        assert get_request_id() is None

    def test_set_and_get_request_id(self):
        set_request_id("abc12345")
        assert get_request_id() == "abc12345"

    def test_request_id_can_be_overwritten(self):
        set_request_id("first-id")
        set_request_id("second-id")
        assert get_request_id() == "second-id"

    def test_clear_request_context(self):
        set_request_id("abc12345")
        clear_request_context()
        assert get_request_id() is None


class TestSetupRequestContext:
    """Tests for request context setup."""

    def setup_method(self):
        clear_request_context()

    def teardown_method(self):
        clear_request_context()

    def test_setup_request_context_sets_id(self):
        base_logger = logging.getLogger("test")
        setup_request_context("req-999", base_logger)

        assert get_request_id() == "req-999"

    def test_setup_request_context_provides_request_logger(self):
        base_logger = logging.getLogger("test")
        setup_request_context("req-888", base_logger)

        req_log = get_request_logger()
        assert req_log is not None
        assert isinstance(req_log, logging.LoggerAdapter)


class TestRequestLogger:
    """Tests for request_logger helper."""

    def setup_method(self):
        clear_request_context()

    def teardown_method(self):
        clear_request_context()

    def test_request_logger_returns_base_when_no_context(self):
        base_logger = logging.getLogger("test_no_context")
        result = request_logger(base_logger)

        assert result is base_logger

    def test_request_logger_returns_request_adapter_when_context_set(self):
        base_logger = logging.getLogger("test_with_context")
        setup_request_context("req-777", base_logger)

        result = request_logger(base_logger)

        assert isinstance(result, logging.LoggerAdapter)
        assert result is not base_logger

    def test_request_logger_injects_request_id_in_process(self):
        base_logger = logging.getLogger("test_inject")
        setup_request_context("req-666", base_logger)

        req_log = request_logger(base_logger)

        msg, kwargs = req_log.process("hello world", {})
        assert "[req-666]" in msg
        assert "hello world" in msg
