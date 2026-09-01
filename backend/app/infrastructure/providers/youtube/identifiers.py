"""Validation for opaque YouTube resource identifiers."""

from __future__ import annotations

import re

from .responses import YouTubeResponseError

_RESOURCE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def resource_id(value: object, *, error_code: str) -> str:
    if not isinstance(value, str):
        raise YouTubeResponseError(error_code)
    normalized = value.strip()
    if not _RESOURCE_ID.fullmatch(normalized):
        raise YouTubeResponseError(error_code)
    return normalized


__all__ = ["resource_id"]
