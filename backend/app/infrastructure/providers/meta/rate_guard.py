"""In-process Meta usage pressure and cooldown guard."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.time import utc_now


class MetaRateLimited(RuntimeError):
    def __init__(self, *, reason: str, wait_seconds: float, pressure_pct: float) -> None:
        super().__init__(reason)
        self.reason = reason
        self.wait_seconds = wait_seconds
        self.pressure_pct = pressure_pct


@dataclass(frozen=True)
class RateSnapshot:
    pressure_pct: float
    scope: str
    degraded_until: datetime | None
    cooldown_until: datetime | None


class MetaRateGuard:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = utc_now,
        sleeper: Callable[[float], None],
    ) -> None:
        self._clock = clock
        self._sleeper = sleeper
        self._pressure_pct = 0.0
        self._scope = ""
        self._degraded_until: datetime | None = None
        self._cooldown_until: datetime | None = None

    def snapshot(self) -> RateSnapshot:
        return RateSnapshot(
            pressure_pct=self._pressure_pct,
            scope=self._scope,
            degraded_until=self._degraded_until,
            cooldown_until=self._cooldown_until,
        )

    def preflight(self) -> None:
        now = self._clock()
        if self._cooldown_until is not None and self._cooldown_until > now:
            raise MetaRateLimited(
                reason="cooldown_active",
                wait_seconds=(self._cooldown_until - now).total_seconds(),
                pressure_pct=self._pressure_pct,
            )

    def background_available(self, *, threshold_pct: float = 70.0) -> bool:
        now = self._clock()
        return (
            self._pressure_pct < threshold_pct
            and not (self._degraded_until is not None and self._degraded_until > now)
            and not (self._cooldown_until is not None and self._cooldown_until > now)
        )

    def observe_headers(self, headers: Mapping[str, str]) -> None:
        entries = _usage_entries(headers)
        if not entries:
            return
        pressure, scope, eta_minutes = _pressure(entries)
        self._pressure_pct = pressure
        self._scope = scope
        now = self._clock()
        if pressure >= 92.0:
            wait_seconds = max(120.0, eta_minutes * 60.0 + 15.0)
            self._cooldown_until = _later(
                self._cooldown_until,
                now + timedelta(seconds=wait_seconds),
            )
            raise MetaRateLimited(
                reason="pressure_cooldown",
                wait_seconds=wait_seconds,
                pressure_pct=pressure,
            )
        if pressure >= 85.0:
            self._degraded_until = _later(
                self._degraded_until,
                now + timedelta(minutes=5),
            )
            return
        if pressure >= 70.0:
            self._sleeper(min(2.0, 0.15 + ((pressure - 70.0) / 30.0) * 1.5))

    def observe_limit_error(self, payload: Mapping[str, Any]) -> bool:
        error = payload.get("error")
        if not isinstance(error, Mapping):
            return False
        code = _number(error.get("code"))
        subcode = _number(error.get("error_subcode"))
        if code not in {4, 17, 32, 613, 80001, 80002, 80003, 80004, 80005, 80006} and (
            subcode != 2446079
        ):
            return False
        eta_minutes = max(
            5.0,
            _number(error.get("estimated_time_to_regain_access")),
            _number(error.get("retry_after")) / 60.0,
            _number(error.get("retry_after_seconds")) / 60.0,
        )
        now = self._clock()
        self._cooldown_until = _later(
            self._cooldown_until,
            now + timedelta(seconds=max(120.0, eta_minutes * 60.0)),
        )
        self._degraded_until = _later(
            self._degraded_until,
            now + timedelta(minutes=10),
        )
        return True


def _usage_entries(headers: Mapping[str, str]) -> list[dict[str, float | str]]:
    entries: list[dict[str, float | str]] = []
    app_usage = _json_object(_header(headers, "x-app-usage"))
    if app_usage is not None:
        entries.append(_entry("app", app_usage))
    business_usage = _json_object(_header(headers, "x-business-use-case-usage"))
    if business_usage is not None:
        for scope_id, rows in business_usage.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                entry = _entry(f"business:{scope_id}", row)
                entry["eta_minutes"] = _number(row.get("estimated_time_to_regain_access"))
                entries.append(entry)
    return entries


def _entry(scope: str, payload: Mapping[str, Any]) -> dict[str, float | str]:
    return {
        "scope": scope,
        "call_count": _number(payload.get("call_count")),
        "total_cputime": _number(payload.get("total_cputime")),
        "total_time": _number(payload.get("total_time")),
        "eta_minutes": 0.0,
    }


def _pressure(entries: list[dict[str, float | str]]) -> tuple[float, str, float]:
    pressure = 0.0
    scope = ""
    eta_minutes = 0.0
    for entry in entries:
        current = max(
            float(entry["call_count"]),
            float(entry["total_cputime"]),
            float(entry["total_time"]),
        )
        if current > pressure:
            pressure = current
            scope = str(entry["scope"])
            eta_minutes = float(entry["eta_minutes"])
    return pressure, scope, eta_minutes


def _json_object(value: str | None) -> Mapping[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, Mapping) else None


def _header(headers: Mapping[str, str], name: str) -> str | None:
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None


def _number(value: object) -> float:
    try:
        return max(0.0, float(value or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _later(current: datetime | None, candidate: datetime) -> datetime:
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=UTC)
    return max(current, candidate) if current is not None else candidate


__all__ = ["MetaRateGuard", "MetaRateLimited", "RateSnapshot"]
