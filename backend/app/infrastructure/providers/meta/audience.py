"""Meta audience capability reader with strict breakdown normalization."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.audience import AudienceSnapshot
from app.core.time import utc_now
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta.transport import MetaTransport, MetaTransportError

logger = logging.getLogger(__name__)

# Meta retired the `page_fans_*` family on 2025-11-15 and now answers them with
# an invalid-metric error, so every request for follower geography was refused.
# Its own reference guide still lists them as current, which is why the refusal
# read as a transient provider fault for so long; the live API is the authority
# here. The follows-based metrics are the documented successors.
FACEBOOK_AUDIENCE_METRICS = (
    "page_follows_country",
    "page_follows_city",
)
FACEBOOK_AUDIENCE_PERIODS = ("day",)
# The successor metric measures the same thing under a new name, and Meta maps
# the old series onto it. Storing it under the established key keeps one
# continuous history per Page instead of splitting it at the rename, and leaves
# the stored vocabulary and the dashboards that read it untouched.
FACEBOOK_CANONICAL_BREAKDOWN_KEYS = {
    "page_follows_country": "page_fans_country",
    "page_follows_city": "page_fans_city",
}
# What a reader of the stored snapshot sees. This is deliberately separate from
# the wire metric names above: the provider's vocabulary is free to change again
# without moving the key anything downstream is written against.
FACEBOOK_AUDIENCE_BREAKDOWN_KEYS = tuple(
    FACEBOOK_CANONICAL_BREAKDOWN_KEYS.get(metric, metric)
    for metric in FACEBOOK_AUDIENCE_METRICS
)
INSTAGRAM_AUDIENCE_PERIODS = ("lifetime",)
INSTAGRAM_AUDIENCE_METRICS = (
    "follower_demographics",
    "engaged_audience_demographics",
    "reached_audience_demographics",
)


class MetaAudienceReader:
    def __init__(
        self,
        transport: MetaTransport,
        *,
        platform: PlatformId,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if platform not in {PlatformId.FACEBOOK, PlatformId.INSTAGRAM}:
            raise ValueError("provider_family_mismatch")
        self._transport = transport
        self._platform = platform
        self._clock = clock

    def fetch_audience(self, account: ProviderAccount) -> AudienceSnapshot:
        if account.platform is not self._platform:
            raise ValueError("provider_family_mismatch")
        metrics = (
            FACEBOOK_AUDIENCE_METRICS
            if self._platform is PlatformId.FACEBOOK
            else INSTAGRAM_AUDIENCE_METRICS
        )
        periods = (
            FACEBOOK_AUDIENCE_PERIODS
            if self._platform is PlatformId.FACEBOOK
            else INSTAGRAM_AUDIENCE_PERIODS
        )
        breakdowns: dict[str, dict[str, float | int | None]] = {}
        for metric in metrics:
            for period in periods:
                try:
                    payload = self._transport.get(
                        f"{account.account_id}/insights",
                        {"metric": metric, "period": period},
                    )
                except MetaTransportError as exc:
                    # Swallowing this silently is what hid the wrong period for
                    # months: the dashboards simply showed nothing.
                    logger.warning(
                        "meta_audience_read_failed platform=%s metric=%s period=%s reason=%s",
                        self._platform.value,
                        metric,
                        period,
                        exc.code,
                    )
                    continue
                raw_rows = payload.get("data") or []
                if not isinstance(raw_rows, list):
                    raise ValueError("provider_audience_shape_invalid")
                metric_breakdowns: dict[str, dict[str, float | int | None]] = {}
                for row in raw_rows:
                    if not isinstance(row, Mapping):
                        raise ValueError("provider_audience_shape_invalid")
                    metric_name = str(row.get("name") or "").strip()
                    if metric_name != metric:
                        continue
                    canonical = FACEBOOK_CANONICAL_BREAKDOWN_KEYS.get(
                        metric_name, metric_name
                    )
                    metric_breakdowns.update(_breakdowns(canonical, row))
                if any(values for values in metric_breakdowns.values()):
                    breakdowns.update(metric_breakdowns)
                    break
        return AudienceSnapshot(
            account_id=account.account_id,
            observed_at=self._clock(),
            breakdowns=breakdowns,
        )


def _breakdowns(
    metric_name: str, row: Mapping[str, Any]
) -> dict[str, dict[str, float | int | None]]:
    values = row.get("values") or []
    if isinstance(values, list) and values:
        latest = values[-1]
        if isinstance(latest, Mapping) and isinstance(latest.get("value"), Mapping):
            return {metric_name: _numeric_map(latest["value"])}
    total = row.get("total_value") or {}
    if isinstance(total, Mapping) and isinstance(total.get("value"), Mapping):
        return {metric_name: _numeric_map(total["value"])}
    if isinstance(total, Mapping):
        grouped: dict[str, dict[str, float | int | None]] = {}
        for breakdown in total.get("breakdowns") or []:
            if not isinstance(breakdown, Mapping):
                continue
            raw_dimensions = breakdown.get("dimension_keys") or []
            dimensions = (
                tuple(str(value).lower() for value in raw_dimensions)
                if isinstance(raw_dimensions, list)
                else ()
            )
            dimension = "_".join((metric_name, *dimensions))
            for result in breakdown.get("results") or []:
                if not isinstance(result, Mapping):
                    continue
                dimension_values = result.get("dimension_values") or []
                if isinstance(dimension_values, list) and dimension_values:
                    grouped.setdefault(dimension, {})[
                        "|".join(str(value) for value in dimension_values)
                    ] = _number(
                        result.get("value")
                    )
        return grouped
    return {metric_name: {}}


def _numeric_map(payload: Mapping[str, Any]) -> dict[str, float | int | None]:
    return {str(key): _number(value) for key, value in payload.items()}


def _number(value: object) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("provider_audience_value_invalid")
    return value


__all__ = ["MetaAudienceReader"]
