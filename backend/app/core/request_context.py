"""
Request context propagation using contextvars.

Allows request_id and other request-scoped values to be accessed
anywhere in the async call chain without threading through every function.
"""

import contextvars
import logging
from typing import Optional

# Context variable for the current request ID
_request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)

# Context variable for request-scoped logger
_request_logger_var: contextvars.ContextVar[Optional[logging.LoggerAdapter]] = contextvars.ContextVar(
    "request_logger", default=None
)


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set the current request ID in context."""
    _request_id_var.set(request_id)


def get_request_logger() -> Optional[logging.LoggerAdapter]:
    """Get the request-scoped logger from context."""
    return _request_logger_var.get()


def setup_request_context(request_id: str, logger: logging.Logger) -> None:
    """
    Set up request context with ID and a logger that auto-injects request_id.

    Call this at the start of each HTTP request.
    """
    _request_id_var.set(request_id)

    class RequestAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            return f"[{request_id}] {msg}", kwargs

    _request_logger_var.set(RequestAdapter(logger, {}))


def clear_request_context() -> None:
    """Clear request context at end of request."""
    _request_id_var.set(None)
    _request_logger_var.set(None)


def request_logger(base_logger: logging.Logger) -> logging.LoggerAdapter:
    """
    Get a logger that auto-injects the current request_id.

    Usage:
        logger = request_logger(logging.getLogger(__name__))
        logger.info("Processing query")  # -> "[abc123] Processing query"
    """
    adapter = _request_logger_var.get()
    if adapter is not None:
        return adapter
    return base_logger
