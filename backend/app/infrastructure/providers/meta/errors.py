"""Reading Meta's error payloads without carrying their contents."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import httpx


def _error_signature(payload: Mapping[str, Any] | None) -> str:
    """Provider error code and subcode, never the message.

    Meta's numeric codes distinguish an expired token from a missing permission
    from an unsupported field; the message can echo request content, so it is
    left out. Without the codes every refusal read the same and the cause could
    only be guessed at.
    """
    error = (payload or {}).get("error")
    if not isinstance(error, Mapping):
        return ""
    parts = [str(error.get(key)) for key in ("code", "error_subcode") if error.get(key) is not None]
    return ":".join(parts)


def _retry_after(response: httpx.Response, payload: Mapping[str, Any]) -> float | None:
    values: list[object] = [response.headers.get("retry-after")]
    error = payload.get("error")
    if isinstance(error, Mapping):
        values.extend((error.get("retry_after"), error.get("retry_after_seconds")))
    parsed: list[float] = []
    for value in values:
        try:
            if value is not None:
                parsed.append(max(0.0, float(cast(Any, value))))
        except (TypeError, ValueError):
            continue
    return max(parsed) if parsed else None


__all__ = ["_error_signature", "_retry_after"]
