"""Strict response helpers for X API payloads."""

from __future__ import annotations

from collections.abc import Mapping


class XResponseError(ValueError):
    """Sanitized response-contract failure."""


def required_mapping(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise XResponseError("x_response_invalid")
    return value


def required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise XResponseError("x_response_invalid")
    return value.strip()


__all__ = ["XResponseError", "required_mapping", "required_text"]
