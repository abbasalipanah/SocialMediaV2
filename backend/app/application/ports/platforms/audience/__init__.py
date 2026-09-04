"""Audience capability port."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.application.ports.platforms import ProviderAccount
from app.domain.metrics import MetricId


@dataclass(frozen=True)
class AudienceSnapshot:
    account_id: str
    observed_at: datetime
    breakdowns: Mapping[str, Mapping[str, float | int | None]]
    metric_id: MetricId = MetricId.FOLLOWERS


class AudienceReader(Protocol):
    def fetch_audience(self, account: ProviderAccount) -> AudienceSnapshot: ...


__all__ = ["AudienceReader", "AudienceSnapshot"]
