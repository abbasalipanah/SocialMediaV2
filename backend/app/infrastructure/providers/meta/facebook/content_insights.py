"""Facebook post insight normalization for the current Graph API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.infrastructure.providers.meta.transport import MetaTransport, MetaTransportError

# The historical post_impressions* metrics were removed from recent Graph API
# versions. post_media_view is the current Page-post delivery metric and works
# for both photo and video posts.
POST_VIEW_METRIC = "post_media_view"


def fetch_content_insights(
    transport: MetaTransport, content_id: str
) -> dict[str, float]:
    try:
        payload = transport.get(
            f"{content_id}/insights",
            {"metric": POST_VIEW_METRIC},
        )
    except MetaTransportError as exc:
        # A deleted/ineligible post must not prevent the other posts on the Page
        # from refreshing. Rate limits and provider faults remain fatal so the
        # run is retried instead of being recorded as an empty success.
        if exc.retryable or (exc.status_code is not None and exc.status_code >= 500):
            raise
        return {}
    return _insight_values(payload)


def map_content_insights(metrics: Mapping[str, float]) -> dict[str, float | None]:
    return {
        "views_count": metrics.get(POST_VIEW_METRIC),
        # Meta no longer exposes a unique post reach metric in the current API.
        # Keep this unavailable instead of presenting views as reach.
        "reach_count": None,
    }


def _insight_values(payload: Mapping[str, Any]) -> dict[str, float]:
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        return {}
    values: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or "").strip().lower()
        if not name:
            continue
        raw: object = row.get("value")
        samples = row.get("values") or []
        if isinstance(samples, list) and samples and isinstance(samples[0], Mapping):
            raw = samples[0].get("value")
        total = row.get("total_value")
        if isinstance(total, Mapping) and total.get("value") is not None:
            raw = total.get("value")
        number = _number(raw)
        if number is not None:
            values[name] = number
    return values


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        return None
    return float(value)


__all__ = ["POST_VIEW_METRIC", "fetch_content_insights", "map_content_insights"]
