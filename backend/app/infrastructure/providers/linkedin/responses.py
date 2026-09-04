"""Strict response helpers for LinkedIn Community Management payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class LinkedInResponseError(ValueError):
    """Provider response violated the allowlisted contract."""


def required_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise LinkedInResponseError("linkedin_response_field_invalid")
    return value


def required_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LinkedInResponseError("linkedin_response_field_invalid")
    return value.strip()


def optional_text(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise LinkedInResponseError("linkedin_response_field_invalid")
    return value.strip() or None


def optional_count(payload: Mapping[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise LinkedInResponseError("linkedin_response_field_invalid")
    return int(value)


def required_count(payload: Mapping[str, Any], key: str) -> int:
    value = optional_count(payload, key)
    if value is None:
        raise LinkedInResponseError("linkedin_response_field_invalid")
    return value


def elements(payload: Mapping[str, Any], *, limit: int = 100) -> tuple[Mapping[str, Any], ...]:
    value = payload.get("elements")
    if not isinstance(value, list) or len(value) > limit:
        raise LinkedInResponseError("linkedin_response_elements_invalid")
    if any(not isinstance(item, Mapping) for item in value):
        raise LinkedInResponseError("linkedin_response_elements_invalid")
    return tuple(value)


__all__ = [
    "LinkedInResponseError",
    "elements",
    "optional_count",
    "optional_text",
    "required_mapping",
    "required_count",
    "required_text",
]
