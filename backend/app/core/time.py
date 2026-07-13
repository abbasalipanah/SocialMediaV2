"""Canonical time utilities placeholder."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return a timezone-aware current UTC timestamp."""
    return datetime.now(UTC)
