"""TikTok provider-supported audience normalization."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.audience import AudienceSnapshot
from app.core.time import utc_now
from app.domain.platforms import PlatformId

from .responses import TikTokResponseError, success_data

AUDIENCE_FIELDS = (
    "audience_countries",
    "audience_genders",
    "audience_ages",
    "audience_activity",
)


class TikTokAudienceReader:
    def __init__(
        self,
        fetch: Callable[[str, date], Mapping[str, Any]],
        *,
        observed_on: date,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._fetch = fetch
        self._observed_on = observed_on
        self._clock = clock

    def fetch_audience(self, account: ProviderAccount) -> AudienceSnapshot:
        if account.platform is not PlatformId.TIKTOK:
            raise ValueError("provider_family_mismatch")
        data = success_data(self._fetch(account.account_id, self._observed_on))
        breakdowns = {
            field: _activity(data.get(field))
            if field == "audience_activity"
            else _dimension(data.get(field))
            for field in AUDIENCE_FIELDS
            if data.get(field) is not None
        }
        return AudienceSnapshot(
            account_id=account.account_id,
            observed_at=self._clock(),
            breakdowns=breakdowns,
        )


def _dimension(value: object) -> dict[str, float]:
    if isinstance(value, Mapping):
        return {
            str(key): number
            for key, raw in value.items()
            if (number := _number(raw)) is not None and str(key).strip()
        }
    if not isinstance(value, list):
        raise TikTokResponseError("audience_shape_invalid")
    mapped: dict[str, float] = {}
    for row in value:
        if not isinstance(row, Mapping):
            raise TikTokResponseError("audience_shape_invalid")
        key = next(
            (
                str(row[field]).strip()
                for field in ("country", "country_code", "gender", "age", "age_group", "name")
                if row.get(field) is not None and str(row[field]).strip()
            ),
            "",
        )
        number = next(
            (
                parsed
                for field in ("value", "percentage", "count", "audience_count")
                if (parsed := _number(row.get(field))) is not None
            ),
            None,
        )
        if key and number is not None:
            mapped[key] = number
    return mapped


def _activity(value: object) -> dict[str, float]:
    mapped: dict[str, float] = {}

    def visit(node: object, path: tuple[str, ...]) -> None:
        if isinstance(node, Mapping):
            direct = _number(node.get("value"))
            if direct is not None:
                day = str(node.get("day") or node.get("weekday") or (path[-1] if path else ""))
                hour = str(node.get("hour") or node.get("hour_of_day") or "")
                if day and hour:
                    normalized = _hour(hour)
                    if normalized is not None:
                        mapped[f"{day}|{normalized:02d}"] = direct
                return
            for key, nested in node.items():
                visit(nested, (*path, str(key)))
        elif isinstance(node, list):
            for nested in node:
                visit(nested, path)
        else:
            number = _number(node)
            if number is not None and len(path) >= 2:
                normalized = _hour(path[-1])
                if normalized is not None:
                    mapped[f"{path[-2]}|{normalized:02d}"] = number

    visit(value, ())
    return mapped


def _hour(value: str) -> int | None:
    try:
        hour = int(value.split(":", 1)[0])
    except ValueError:
        return None
    return hour if 0 <= hour <= 23 else None


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float) and value >= 0:
        return float(value)
    return None


__all__ = ["AUDIENCE_FIELDS", "TikTokAudienceReader"]
