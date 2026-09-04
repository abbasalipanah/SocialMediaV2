from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.platforms import PlatformId
from app.workers.collector import StandaloneCollector
from app.workers.platform_registry import (
    CollectorRegistration,
    PlatformCollectorRegistry,
)


def test_registry_filters_disabled_providers_without_reordering_platforms() -> None:
    registry = PlatformCollectorRegistry[str, str](
        (
            CollectorRegistration(
                provider="meta",
                platforms=(PlatformId.FACEBOOK, PlatformId.INSTAGRAM),
                enabled=lambda: True,
                collect=lambda row, _timings: row,
            ),
            CollectorRegistration(
                provider="tiktok",
                platforms=(PlatformId.TIKTOK,),
                enabled=lambda: False,
                collect=lambda row, _timings: row,
            ),
        )
    )

    assert registry.enabled_platforms(
        (PlatformId.TIKTOK, PlatformId.INSTAGRAM, PlatformId.FACEBOOK)
    ) == (PlatformId.INSTAGRAM, PlatformId.FACEBOOK)


def test_registry_dispatches_to_the_registered_provider() -> None:
    calls: list[tuple[str, dict[str, float]]] = []

    def collect(row: str, timings: dict[str, float]) -> str:
        calls.append((row, timings))
        return "collected"

    registry = PlatformCollectorRegistry[str, str](
        (
            CollectorRegistration(
                provider="meta",
                platforms=(PlatformId.FACEBOOK, PlatformId.INSTAGRAM),
                enabled=lambda: True,
                collect=collect,
            ),
        )
    )
    timings = {"profile": 1.5}

    assert registry.collect(PlatformId.INSTAGRAM, "account-row", timings) == "collected"
    assert calls == [("account-row", timings)]


def test_registry_rejects_duplicate_platform_ownership() -> None:
    registration = CollectorRegistration[str, str](
        provider="meta",
        platforms=(PlatformId.FACEBOOK,),
        enabled=lambda: True,
        collect=lambda row, _timings: row,
    )

    with pytest.raises(ValueError, match="duplicate_platform_collector"):
        PlatformCollectorRegistry((registration, registration))


def test_registry_fails_closed_for_an_unregistered_or_disabled_platform() -> None:
    registry = PlatformCollectorRegistry[str, str](
        (
            CollectorRegistration(
                provider="meta",
                platforms=(PlatformId.FACEBOOK,),
                enabled=lambda: False,
                collect=lambda row, _timings: row,
            ),
        )
    )

    with pytest.raises(RuntimeError, match="platform_collector_disabled"):
        registry.collect(PlatformId.FACEBOOK, "account-row", {})
    with pytest.raises(LookupError, match="platform_collector_not_registered"):
        registry.collect(PlatformId.TIKTOK, "account-row", {})


def test_standalone_registry_enables_only_configured_provider_families() -> None:
    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector.settings = SimpleNamespace(
        meta=SimpleNamespace(collection_enabled=False),
        tiktok=SimpleNamespace(collection_enabled=False),
        x=SimpleNamespace(collection_enabled=False),
        linkedin=SimpleNamespace(collection_enabled=False),
        youtube=SimpleNamespace(collection_enabled=True),
    )
    collector._collect_meta = lambda row, _timings: row
    collector._collect_tiktok = lambda row, _timings: row
    collector._collect_x = lambda row, _timings: row
    collector._collect_linkedin = lambda row, _timings: row
    collector._collect_youtube = lambda row, _timings: row
    registry = PlatformCollectorRegistry(collector._collector_registrations())

    assert registry.enabled_platforms(tuple(PlatformId)) == (PlatformId.YOUTUBE,)
    assert registry.collect(PlatformId.YOUTUBE, "youtube-row", {}) == "youtube-row"
    with pytest.raises(RuntimeError, match="platform_collector_disabled"):
        registry.collect(PlatformId.TIKTOK, "tiktok-row", {})
