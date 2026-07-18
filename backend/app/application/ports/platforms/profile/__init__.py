"""Profile capability port."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.application.ports.platforms import ProviderAccount
from app.domain.metrics import MetricId


@dataclass(frozen=True)
class ProfileSnapshot:
    account_id: str
    display_name: str
    handle: str | None
    observed_at: datetime
    metric_values: Mapping[MetricId, float | int | None]


class ProfileReader(Protocol):
    def fetch_profile(self, account: ProviderAccount) -> ProfileSnapshot: ...


@dataclass(frozen=True)
class DailyMetricSnapshot:
    account_id: str
    observed_on: date
    metric_values: Mapping[MetricId, float | int | None]


class DailyMetricsReader(Protocol):
    def fetch_daily_metrics(
        self,
        account: ProviderAccount,
        *,
        since: date,
        until: date,
    ) -> tuple[DailyMetricSnapshot, ...]: ...


__all__ = [
    "DailyMetricSnapshot",
    "DailyMetricsReader",
    "ProfileReader",
    "ProfileSnapshot",
]
