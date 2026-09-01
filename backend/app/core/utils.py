"""Shared utilities."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time (timezone-aware). Use instead of deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)


def utc_now_naive() -> datetime:
    """Return current UTC as naive datetime for DB columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
