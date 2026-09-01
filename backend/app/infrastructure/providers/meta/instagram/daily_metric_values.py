"""Parsers for Instagram daily total-value insight payloads."""

from __future__ import annotations

from collections.abc import Mapping

from app.infrastructure.providers.meta.fields import nonnegative_int_or_none


def total_value(payload: Mapping[str, object], source_field: str) -> int | None:
    raw_data = payload.get("data") or []
    if not isinstance(raw_data, list):
        raise ValueError("provider_daily_metric_shape_invalid")
    for item in raw_data:
        if not isinstance(item, Mapping) or item.get("name") != source_field:
            continue
        total = item.get("total_value")
        if not isinstance(total, Mapping):
            return None
        return nonnegative_int_or_none({"value": total.get("value")}, "value")
    return None


def follow_type_values(payload: Mapping[str, object]) -> dict[str, int]:
    values = breakdown_values(
        payload,
        source_field="follows_and_unfollows",
        breakdown_key="follow_type",
    )
    if not _breakdown_dimension_reported(
        payload,
        source_field="follows_and_unfollows",
        breakdown_key="follow_type",
    ):
        return values
    # Meta represents a completed day with no follower events as a valid
    # follow_type breakdown without a results array. It can likewise omit the
    # zero-valued side of a sparse breakdown. These are real zeroes, not an
    # unavailable metric; leaving them as None breaks the exact follower-total
    # reconstruction at that day.
    return {
        "FOLLOWER": values.get("FOLLOWER", 0),
        "NON_FOLLOWER": values.get("NON_FOLLOWER", 0),
    }


def _breakdown_dimension_reported(
    payload: Mapping[str, object],
    *,
    source_field: str,
    breakdown_key: str,
) -> bool:
    raw_data = payload.get("data") or []
    if not isinstance(raw_data, list):
        raise ValueError("provider_daily_metric_shape_invalid")
    for item in raw_data:
        if not isinstance(item, Mapping) or item.get("name") != source_field:
            continue
        total = item.get("total_value")
        if not isinstance(total, Mapping):
            return False
        breakdowns = total.get("breakdowns") or []
        if not isinstance(breakdowns, list):
            raise ValueError("provider_daily_metric_shape_invalid")
        return any(
            isinstance(breakdown, Mapping)
            and breakdown.get("dimension_keys") == [breakdown_key]
            for breakdown in breakdowns
        )
    return False


def breakdown_values(
    payload: Mapping[str, object],
    *,
    source_field: str,
    breakdown_key: str,
) -> dict[str, int]:
    raw_data = payload.get("data") or []
    if not isinstance(raw_data, list):
        raise ValueError("provider_daily_metric_shape_invalid")
    for item in raw_data:
        if not isinstance(item, Mapping) or item.get("name") != source_field:
            continue
        total = item.get("total_value")
        if not isinstance(total, Mapping):
            return {}
        breakdowns = total.get("breakdowns") or []
        if not isinstance(breakdowns, list):
            raise ValueError("provider_daily_metric_shape_invalid")
        for breakdown in breakdowns:
            if not isinstance(breakdown, Mapping):
                continue
            if breakdown.get("dimension_keys") != [breakdown_key]:
                continue
            results = breakdown.get("results") or []
            if not isinstance(results, list):
                raise ValueError("provider_daily_metric_shape_invalid")
            values: dict[str, int] = {}
            for result in results:
                if not isinstance(result, Mapping):
                    continue
                dimensions = result.get("dimension_values") or []
                if not isinstance(dimensions, list) or not dimensions:
                    continue
                parsed = nonnegative_int_or_none(
                    {"value": result.get("value")}, "value"
                )
                if parsed is not None:
                    values[str(dimensions[0])] = parsed
            return values
    return {}


__all__ = ["breakdown_values", "follow_type_values", "total_value"]
