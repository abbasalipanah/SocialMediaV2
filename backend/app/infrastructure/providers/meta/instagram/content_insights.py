"""Instagram media and Story insight normalization."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.domain.metrics import MetricId
from app.infrastructure.providers.meta.transport import MetaTransport, MetaTransportError

MEDIA_INSIGHT_METRICS = (
    MetricId.VIEWS.value,
    MetricId.REACH.value,
    "total_interactions",
    "likes",
    "comments",
    "shares",
    "replies",
)
STORY_INSIGHT_METRICS = (
    *MEDIA_INSIGHT_METRICS,
    "impressions",
    "taps_forward",
    "taps_back",
    "exits",
    "navigation",
    "profile_visits",
    "follows",
    "swipe_forward",
)


def fetch_content_insights(
    transport: MetaTransport,
    content_id: str,
    *,
    story: bool,
) -> dict[str, float]:
    requested = STORY_INSIGHT_METRICS if story else MEDIA_INSIGHT_METRICS
    payloads: list[Mapping[str, Any]] = []
    try:
        payloads.append(
            transport.get(f"{content_id}/insights", {"metric": ",".join(requested)})
        )
    except MetaTransportError:
        for metric in requested:
            try:
                payloads.append(
                    transport.get(f"{content_id}/insights", {"metric": metric})
                )
            except MetaTransportError:
                continue
    values: dict[str, float] = {}
    for payload in payloads:
        values.update(_insight_values(payload))
    if story and not any(
        key in values for key in ("taps_forward", "taps_back", "exits", "swipe_forward")
    ):
        try:
            navigation = transport.get(
                f"{content_id}/insights",
                {"metric": "navigation", "breakdown": "story_navigation_action_type"},
            )
        except MetaTransportError:
            navigation = {}
        values.update(_navigation_values(navigation))
    return values


def map_content_insights(
    metrics: Mapping[str, float], *, story: bool
) -> dict[str, float | None]:
    views = metrics.get(MetricId.VIEWS.value, metrics.get("impressions"))
    components = tuple(
        metrics.get(key) for key in ("taps_forward", "taps_back", "swipe_forward", "exits")
    )
    navigation = metrics.get("navigation")
    if navigation is None and all(value is not None for value in components):
        navigation = sum(value for value in components if value is not None)
    completion = None
    if story and views is not None and views > 0 and all(
        value is not None for value in components
    ):
        navigation_total = sum(value for value in components if value is not None)
        completion = max(0.0, (1.0 - navigation_total / views) * 100.0)
    return {
        "views_count": views,
        "reach_count": metrics.get(MetricId.REACH.value),
        "interactions_count": metrics.get("total_interactions"),
        "replies_count": metrics.get("replies"),
        "profile_visits": metrics.get("profile_visits"),
        "follows_count": metrics.get("follows"),
        "taps_forward": metrics.get("taps_forward"),
        "taps_back": metrics.get("taps_back"),
        "swipe_forward": metrics.get("swipe_forward"),
        "exits": metrics.get("exits"),
        "navigation_count": navigation,
        "completion_rate": completion,
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


def _navigation_values(payload: Mapping[str, Any]) -> dict[str, float]:
    rows = payload.get("data") or []
    if not isinstance(rows, list):
        return {}
    mapped: dict[str, float] = {}
    aliases = {
        "tap_forward": "taps_forward",
        "tap_back": "taps_back",
        "tap_exit": "exits",
        "swipe_forward": "swipe_forward",
    }
    for row in rows:
        if not isinstance(row, Mapping) or str(row.get("name") or "").lower() != "navigation":
            continue
        total = row.get("total_value") or {}
        if not isinstance(total, Mapping):
            continue
        for breakdown in total.get("breakdowns") or []:
            if not isinstance(breakdown, Mapping):
                continue
            for result in breakdown.get("results") or []:
                if not isinstance(result, Mapping):
                    continue
                dimensions = result.get("dimension_values") or []
                key = (
                    str(dimensions[0]).lower()
                    if isinstance(dimensions, list) and dimensions
                    else ""
                )
                number = _number(result.get("value"))
                if number is not None and key in aliases:
                    mapped[aliases[key]] = number
    return mapped


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        return None
    return float(value)


__all__ = [
    "MEDIA_INSIGHT_METRICS",
    "STORY_INSIGHT_METRICS",
    "fetch_content_insights",
    "map_content_insights",
]
