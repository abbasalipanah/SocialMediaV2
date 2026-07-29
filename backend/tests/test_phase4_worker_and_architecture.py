from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.capabilities.registry import (
    CapabilityRecord,
    CapabilityStatus,
    PlatformCapabilityRegistry,
    bootstrap_registry,
)
from app.core.config import ConfigurationError, RuntimeMode, load_settings
from app.core.write_policy import WritePolicy
from app.domain.metrics import MetricId
from app.domain.platforms import CapabilityId, PlatformId
from app.infrastructure.persistence.social_v2.platforms import (
    normalize_platform,
)
from app.workers import (
    ManualWorkerSelection,
    WorkerRuntimeConfig,
    assert_manual_worker_allowed,
    dormant_worker_config,
    local_fixture_worker_config,
)

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"


def test_worker_runtime_is_fail_closed_until_a_v2_collector_is_enabled() -> None:
    config = dormant_worker_config(load_settings())
    assert config.provider_egress_enabled is False
    assert config.automated_schedule_enabled is False

    with pytest.raises(ConfigurationError, match="worker_schedule_requires_provider_egress"):
        WorkerRuntimeConfig(
            runtime_mode=RuntimeMode.ACTIVE,
            writes_enabled=True,
            provider_egress_enabled=False,
            automated_schedule_enabled=True,
        )
    with pytest.raises(
        ConfigurationError, match="worker_egress_requires_writable_v2_runtime"
    ):
        WorkerRuntimeConfig(
            runtime_mode=RuntimeMode.DORMANT,
            writes_enabled=False,
            provider_egress_enabled=True,
        )


def test_manual_worker_requires_local_write_policy_and_available_capability() -> None:
    selection = ManualWorkerSelection(
        platform=PlatformId.INSTAGRAM,
        capability=CapabilityId.PROFILE,
        account_ids=("account-1",),
    )
    local = local_fixture_worker_config(
        WritePolicy(runtime_mode=RuntimeMode.DEVELOPMENT, writes_enabled=True)
    )
    with pytest.raises(PermissionError, match="worker_capability_unavailable"):
        assert_manual_worker_allowed(local, bootstrap_registry(), selection)

    registry = PlatformCapabilityRegistry(
        (
            CapabilityRecord(
                platform=PlatformId.INSTAGRAM,
                capability=CapabilityId.PROFILE,
                status=CapabilityStatus.AVAILABLE,
                reason="local_fixture_ready",
            ),
        )
    )
    assert_manual_worker_allowed(local, registry, selection)

    dormant = WorkerRuntimeConfig(
        runtime_mode=RuntimeMode.DORMANT,
        writes_enabled=False,
        provider_egress_enabled=False,
    )
    with pytest.raises(PermissionError, match="worker_provider_egress_disabled"):
        assert_manual_worker_allowed(dormant, registry, selection)


def test_provider_adapters_remain_small_and_capability_specific() -> None:
    provider_root = APP / "infrastructure" / "providers"
    oversized = {
        str(path.relative_to(APP)): len(path.read_text(encoding="utf-8").splitlines())
        for path in provider_root.rglob("*.py")
        if len(path.read_text(encoding="utf-8").splitlines()) > 250
    }
    assert oversized == {}

    platform_ports = APP / "application" / "ports" / "platforms"
    assert {
        path.parent.name for path in platform_ports.glob("*/__init__.py")
    } == {"profile", "content", "comments", "audience"}
    assert "PlatformAdapter" not in "".join(
        path.read_text(encoding="utf-8") for path in platform_ports.rglob("*.py")
    )


def test_metric_ids_are_not_reintroduced_as_free_literals() -> None:
    catalog_path = APP / "domain" / "metrics" / "__init__.py"
    metric_literals = {metric_id.value for metric_id in MetricId}
    violations: list[str] = []
    for path in APP.rglob("*.py"):
        if path == catalog_path:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in metric_literals:
                    violations.append(f"{path.relative_to(APP)}:{node.lineno}:{node.value}")
    assert violations == []


def test_schema_identifiers_are_isolated_to_compatibility_adapter() -> None:
    compatibility_root = APP / "infrastructure" / "persistence" / "social_v2"
    schema_identifiers = {"metrics_daily", "content_items", "content_comments", "media_assets"}
    violations: list[str] = []
    for path in APP.rglob("*.py"):
        if compatibility_root in path.parents:
            continue
        text = path.read_text(encoding="utf-8")
        for identifier in schema_identifiers:
            if identifier in text:
                violations.append(f"{path.relative_to(APP)}:{identifier}")
    assert violations == []


def test_legacy_platform_values_normalize_without_raw_error_echo() -> None:
    assert normalize_platform("facebook_organic") is PlatformId.FACEBOOK
    assert normalize_platform("instagram_organic") is PlatformId.INSTAGRAM
    assert normalize_platform("tiktok_organic") is PlatformId.TIKTOK
    assert normalize_platform("facebook") is PlatformId.FACEBOOK
    with pytest.raises(ValueError, match="^unsupported_platform$") as raised:
        normalize_platform("unknown_raw_platform")
    assert "unknown_raw_platform" not in str(raised.value)


def test_query_package_has_no_mutation_calls() -> None:
    forbidden_calls = {"commit", "delete", "flush", "put", "revoke", "save", "upsert"}
    violations: list[str] = []
    for path in (APP / "application" / "queries").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in forbidden_calls:
                    violations.append(f"{path.relative_to(APP)}:{node.lineno}:{node.func.attr}")
    assert violations == []
