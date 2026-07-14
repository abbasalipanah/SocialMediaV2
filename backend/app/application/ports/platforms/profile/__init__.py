"""Profile capability port."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
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


__all__ = ["ProfileReader", "ProfileSnapshot"]
