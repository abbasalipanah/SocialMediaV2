"""Capability registry placeholder."""

from __future__ import annotations


def supported_capabilities() -> tuple[str, ...]:
    """Return canonical platform capabilities known at bootstrap."""
    return ()
