"""Strict helpers for untrusted YouTube API response payloads."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class YouTubeResponseError(ValueError):
    """A stable response error that does not echo provider payloads."""


def single_channel(payload: Mapping[str, Any], *, channel_id: str) -> Mapping[str, Any]:
    items = payload.get("items")
    if not isinstance(items, list) or len(items) != 1:
        raise YouTubeResponseError("channel_response_invalid")
    channel = items[0]
    if not isinstance(channel, Mapping) or channel.get("id") != channel_id:
        raise YouTubeResponseError("channel_response_invalid")
    return channel


def required_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise YouTubeResponseError("response_field_invalid")
    return value


def required_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise YouTubeResponseError("response_field_invalid")
    return value.strip()


def optional_text(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise YouTubeResponseError("response_field_invalid")
    return value.strip() or None


def optional_count(payload: Mapping[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise YouTubeResponseError("response_field_invalid")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise YouTubeResponseError("response_field_invalid") from exc
    if parsed < 0 or (isinstance(value, str) and str(parsed) != value.strip()):
        raise YouTubeResponseError("response_field_invalid")
    return parsed


def required_count(payload: Mapping[str, Any], key: str) -> int:
    value = optional_count(payload, key)
    if value is None:
        raise YouTubeResponseError("response_field_invalid")
    return value


def report_rows(
    payload: Mapping[str, Any], *, required_columns: tuple[str, ...]
) -> tuple[Mapping[str, object], ...]:
    headers = payload.get("columnHeaders")
    raw_rows = payload.get("rows", [])
    if not isinstance(headers, list) or not isinstance(raw_rows, list):
        raise YouTubeResponseError("analytics_response_invalid")
    names: list[str] = []
    for header in headers:
        if not isinstance(header, Mapping):
            raise YouTubeResponseError("analytics_response_invalid")
        names.append(required_text(header, "name"))
    if len(names) != len(set(names)) or not set(required_columns).issubset(names):
        raise YouTubeResponseError("analytics_response_invalid")
    rows: list[Mapping[str, object]] = []
    for row in raw_rows:
        if (
            not isinstance(row, Sequence)
            or isinstance(row, str | bytes)
            or len(row) != len(names)
        ):
            raise YouTubeResponseError("analytics_response_invalid")
        rows.append(dict(zip(names, row, strict=True)))
    return tuple(rows)


__all__ = [
    "YouTubeResponseError",
    "optional_count",
    "optional_text",
    "report_rows",
    "required_count",
    "required_mapping",
    "required_text",
    "single_channel",
]
