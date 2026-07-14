"""Meta audience capability reader with strict breakdown normalization."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.audience import AudienceSnapshot
from app.core.time import utc_now
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta.transport import MetaTransport

FACEBOOK_AUDIENCE_METRICS = (
    "page_fans_gender_age",
    "page_fans_country",
    "page_fans_city",
)
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
        payload = self._transport.get(
            f"{account.account_id}/insights",
            {"metric": ",".join(metrics), "period": "lifetime"},
        )
        raw_rows = payload.get("data") or []
        if not isinstance(raw_rows, list):
            raise ValueError("provider_audience_shape_invalid")
        breakdowns: dict[str, dict[str, float | int | None]] = {}
        for row in raw_rows:
            if not isinstance(row, Mapping):
                raise ValueError("provider_audience_shape_invalid")
            metric_name = str(row.get("name") or "").strip()
            if metric_name not in metrics:
                continue
            breakdowns[metric_name] = _values(row)
        return AudienceSnapshot(
            account_id=account.account_id,
            observed_at=self._clock(),
            breakdowns=breakdowns,
        )


def _values(row: Mapping[str, Any]) -> dict[str, float | int | None]:
    values = row.get("values") or []
    if isinstance(values, list) and values:
        latest = values[-1]
        if isinstance(latest, Mapping) and isinstance(latest.get("value"), Mapping):
            return _numeric_map(latest["value"])
    total = row.get("total_value") or {}
    if isinstance(total, Mapping) and isinstance(total.get("value"), Mapping):
        return _numeric_map(total["value"])
    if isinstance(total, Mapping):
        flattened: dict[str, float | int | None] = {}
        for breakdown in total.get("breakdowns") or []:
            if not isinstance(breakdown, Mapping):
                continue
            for result in breakdown.get("results") or []:
                if not isinstance(result, Mapping):
                    continue
                dimensions = result.get("dimension_values") or []
                if isinstance(dimensions, list) and dimensions:
                    flattened["|".join(str(value) for value in dimensions)] = _number(
                        result.get("value")
                    )
        return flattened
    return {}


def _numeric_map(payload: Mapping[str, Any]) -> dict[str, float | int | None]:
    return {str(key): _number(value) for key, value in payload.items()}


def _number(value: object) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("provider_audience_value_invalid")
    return value


__all__ = ["MetaAudienceReader"]
