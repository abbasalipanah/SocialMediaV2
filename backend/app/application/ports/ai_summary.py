"""Ports and contracts for V2-owned AI Summary generation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.application.ports.reporting import ReportingInsight


class AiSummaryError(RuntimeError):
    """Stable error code raised across the AI Summary boundary."""

    def __init__(self, code: str, *, next_available_at: datetime | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.next_available_at = next_available_at


@dataclass(frozen=True)
class AiSummaryOutput:
    strategic_summary: str
    connector_analysis: str
    anomalies: str
    action_recommendations: str
    platform_evaluations: str
    model: str


@dataclass(frozen=True)
class AiSummaryLimitStatus:
    provider_configured: bool
    can_generate: bool
    reason: str
    weekly_limit: int
    used: int
    remaining: int
    window_days: int
    last_generated_at: datetime | None
    next_available_at: datetime | None
    generation_in_progress: bool


class AiSummaryProvider(Protocol):
    async def generate(self, snapshot: Mapping[str, object]) -> AiSummaryOutput: ...


class AiSummaryRepository(Protocol):
    def limit_status(
        self,
        *,
        brand_id: str,
        now: datetime,
        provider_configured: bool,
    ) -> AiSummaryLimitStatus: ...

    def claim(
        self,
        *,
        brand_id: str,
        date_from: date,
        date_to: date,
        created_by_user_sub: str,
        now: datetime,
    ) -> int: ...

    def complete(
        self,
        *,
        insight_id: int,
        output: AiSummaryOutput,
        completed_at: datetime,
    ) -> ReportingInsight: ...

    def fail(self, *, insight_id: int, error_code: str, failed_at: datetime) -> None: ...


class AiSummaryService(Protocol):
    @property
    def provider_configured(self) -> bool: ...

    def limit_status(self, *, brand_id: str) -> AiSummaryLimitStatus: ...

    async def generate(
        self,
        *,
        brand_id: str,
        user_sub: str,
        range_key: str,
        start_on: date | None = None,
        end_on: date | None = None,
    ) -> ReportingInsight: ...


__all__ = [
    "AiSummaryError",
    "AiSummaryLimitStatus",
    "AiSummaryOutput",
    "AiSummaryProvider",
    "AiSummaryRepository",
    "AiSummaryService",
]
