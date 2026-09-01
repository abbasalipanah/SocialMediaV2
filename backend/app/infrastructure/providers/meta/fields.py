"""Strict field conversion shared by small Meta capability readers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any


def required_text(payload: Mapping[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise ValueError("provider_required_field_missing")
    return value


def optional_text(payload: Mapping[str, Any], field: str) -> str | None:
    value = str(payload.get(field) or "").strip()
    return value or None


def nonnegative_int(payload: Mapping[str, Any], field: str) -> int | None:
    value = payload.get(field)
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("provider_numeric_field_invalid")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("provider_numeric_field_invalid") from exc
    if parsed < 0:
        raise ValueError("provider_numeric_field_invalid")
    return parsed


def nonnegative_int_or_none(payload: Mapping[str, Any], field: str) -> int | None:
    """Treat one malformed provider counter as unavailable.

    Daily insight responses occasionally contain a transient negative or
    otherwise non-numeric value for one metric while every other metric in the
    same response is valid. Capability readers use this converter at that
    field-isolation boundary so one bad counter cannot discard the whole day.
    """
    try:
        return nonnegative_int(payload, field)
    except ValueError:
        return None


def nested_count(payload: Mapping[str, Any], field: str) -> int:
    raw = payload.get(field)
    if raw is None:
        return 0
    if not isinstance(raw, Mapping):
        raise ValueError("provider_count_field_invalid")
    summary = raw.get("summary")
    source = summary if isinstance(summary, Mapping) else raw
    value = source.get("total_count", source.get("count", 0))
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("provider_count_field_invalid") from exc
    if parsed < 0:
        raise ValueError("provider_count_field_invalid")
    return parsed


def timestamp(payload: Mapping[str, Any], field: str) -> datetime | None:
    raw = optional_text(payload, field)
    if raw is None:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("provider_timestamp_invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("provider_timestamp_invalid")
    return parsed.astimezone(UTC)


__all__ = [
    "nested_count",
    "nonnegative_int",
    "nonnegative_int_or_none",
    "optional_text",
    "required_text",
    "timestamp",
]
