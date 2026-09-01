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


def optional_text(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise XResponseError("x_response_invalid")
    return value.strip() or None


def optional_count(payload: Mapping[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise XResponseError("x_response_invalid")
    return value


__all__ = [
    "XResponseError",
    "optional_count",
    "optional_text",
    "required_mapping",
    "required_text",
]
