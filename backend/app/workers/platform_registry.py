"""Small dispatch registry for standalone platform collectors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from app.domain.platforms import PlatformId

RowT = TypeVar("RowT")
ResultT = TypeVar("ResultT")


@dataclass(frozen=True)
class CollectorRegistration(Generic[RowT, ResultT]):
    provider: str
    platforms: tuple[PlatformId, ...]
    enabled: Callable[[], bool]
    collect: Callable[[RowT, dict[str, float]], ResultT]

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("collector_provider_required")
        if not self.platforms:
            raise ValueError("collector_platform_required")


class PlatformCollectorRegistry(Generic[RowT, ResultT]):
    def __init__(
        self, registrations: tuple[CollectorRegistration[RowT, ResultT], ...]
    ) -> None:
        by_platform: dict[PlatformId, CollectorRegistration[RowT, ResultT]] = {}
        for registration in registrations:
            for platform in registration.platforms:
                if platform in by_platform:
                    raise ValueError("duplicate_platform_collector")
                by_platform[platform] = registration
        self._by_platform = by_platform

    def enabled_platforms(
        self, requested: tuple[PlatformId, ...]
    ) -> tuple[PlatformId, ...]:
        return tuple(
            platform
            for platform in requested
            if (registration := self._by_platform.get(platform)) is not None
            and registration.enabled()
        )

    def collect(
        self,
        platform: PlatformId,
        row: RowT,
        timings: dict[str, float],
    ) -> ResultT:
        registration = self._by_platform.get(platform)
        if registration is None:
            raise LookupError("platform_collector_not_registered")
        if not registration.enabled():
            raise RuntimeError("platform_collector_disabled")
        return registration.collect(row, timings)


__all__ = ["CollectorRegistration", "PlatformCollectorRegistry"]
