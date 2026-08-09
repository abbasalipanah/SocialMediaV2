#!/usr/bin/env python3
"""Validate the frozen Revision 6 / R1 frontend inventory and fixture contract."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = Path("/home/api/colab_scripts/SocialMedia")
R1_DIR = ROOT / "docs" / "revision6" / "r1"
INVENTORY_FILE = R1_DIR / "canonical_frontend_inventory.json"
FIXTURE_FILE = R1_DIR / "canonical_dashboard_fixture.json"
SOURCE_BASELINE_FILE = ROOT / "docs" / "revision6" / "r0" / "source_baseline_revision6.json"


class InventoryError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InventoryError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InventoryError(f"top-level JSON value must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise InventoryError(f"duplicate values in {label}")


def _validate_source_snapshot(inventory: dict[str, Any]) -> None:
    baseline = _load(SOURCE_BASELINE_FILE)
    expected = baseline.get("projects", {}).get("SocialMedia")
    snapshot = inventory.get("source_snapshot")
    if not isinstance(expected, dict) or not isinstance(snapshot, dict):
        raise InventoryError("SocialMedia baseline or R1 source snapshot is missing")
    field_map = {
        "root": "root",
        "branch": "branch",
        "head": "head",
        "tracked_binary_diff_sha256": "tracked_diff_sha256",
        "artifact_excluded_content_manifest_sha256": "content_manifest_sha256",
    }
    for inventory_field, baseline_field in field_map.items():
        if snapshot.get(inventory_field) != expected.get(baseline_field):
            raise InventoryError(
                f"source snapshot mismatch: {inventory_field} != baseline {baseline_field}"
            )


def _validate_source_files(inventory: dict[str, Any]) -> None:
    rows = inventory.get("source_files")
    if not isinstance(rows, list) or not rows:
        raise InventoryError("source_files must be a non-empty list")
    paths: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise InventoryError("source_files entries must be objects")
        relative_path = row.get("path")
        expected_sha256 = row.get("sha256")
        if not isinstance(relative_path, str) or not isinstance(expected_sha256, str):
            raise InventoryError("source file path/hash missing")
        paths.append(relative_path)
        source_file = SOURCE_ROOT / relative_path
        if not source_file.is_file():
            raise InventoryError(f"canonical source file missing: {source_file}")
        if _sha256(source_file) != expected_sha256:
            raise InventoryError(f"canonical source file changed: {relative_path}")
    _unique(paths, "source_files paths")


def _validate_cards(inventory: dict[str, Any], fixture: dict[str, Any]) -> None:
    cards = inventory.get("cards")
    platforms = inventory.get("platforms")
    shared = inventory.get("shared_section_sequences")
    if not isinstance(cards, dict) or not isinstance(platforms, dict) or not isinstance(shared, dict):
        raise InventoryError("cards/platforms/shared_section_sequences must be objects")

    def validate_ids(values: Any, label: str) -> None:
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise InventoryError(f"{label} must be a string list")
        _unique(values, label)
        missing = [value for value in values if value not in cards]
        if missing:
            raise InventoryError(f"unknown card IDs in {label}: {missing}")

    for section, values in shared.items():
        validate_ids(values, f"shared section {section}")
    for platform, row in platforms.items():
        if not isinstance(row, dict):
            raise InventoryError(f"invalid platform row: {platform}")
        validate_ids(row.get("audience_sequence"), f"{platform} audience_sequence")
        tabs = row.get("tabs")
        if not isinstance(tabs, list) or not tabs or tabs[0] != "Cover":
            raise InventoryError(f"{platform} tabs must start with Cover")
        _unique(tabs, f"{platform} tabs")

    for card_id, card in cards.items():
        if not isinstance(card, dict):
            raise InventoryError(f"card must be an object: {card_id}")
        reference = card.get("$ref")
        if reference is not None and reference not in cards:
            raise InventoryError(f"unknown card reference: {card_id} -> {reference}")

    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        raise InventoryError("fixture cases must be a non-empty list")
    case_ids: list[str] = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise InventoryError("invalid fixture case")
        case_ids.append(case["id"])
        for key, value in case.items():
            if key.startswith("expected_") and key.endswith("_ids"):
                validate_ids(value, f"fixture {case['id']} {key}")
    _unique(case_ids, "fixture case IDs")


def _validate_fixture(fixture: dict[str, Any]) -> None:
    if fixture.get("schema_version") != 1 or fixture.get("contains_secrets") is not False:
        raise InventoryError("fixture schema or secret declaration is invalid")
    base = fixture.get("base_payload")
    if not isinstance(base, dict):
        raise InventoryError("base_payload must be an object")
    required = {
        "platform",
        "platform_label",
        "brand_id",
        "brand_name",
        "generated_at",
        "window",
        "accounts_count",
        "has_data",
        "account",
        "kpis",
        "trend",
        "top_content",
        "audience",
    }
    missing = sorted(required - set(base))
    if missing:
        raise InventoryError(f"fixture base payload is missing fields: {missing}")
    consumers = fixture.get("consumers")
    consumer_ids = [row.get("id") for row in consumers] if isinstance(consumers, list) else []
    if consumer_ids != ["source_adapter_oracle", "v2_render_test"]:
        raise InventoryError("fixture must declare the source and V2 consumers in order")


def _validate_non_rendered_claim(inventory: dict[str, Any]) -> None:
    rows = inventory.get("non_rendered_source_files")
    if not isinstance(rows, list):
        raise InventoryError("non_rendered_source_files must be a list")
    facebook_file = "frontend/src/components/dashboard/FacebookAudienceSection.tsx"
    if not any(isinstance(row, dict) and row.get("path") == facebook_file for row in rows):
        raise InventoryError("FacebookAudienceSection non-rendered evidence is missing")
    needle = "FacebookAudienceSection"
    importers: list[str] = []
    for path in (SOURCE_ROOT / "frontend" / "src").rglob("*.tsx"):
        if path == SOURCE_ROOT / facebook_file:
            continue
        if needle in path.read_text(encoding="utf-8"):
            importers.append(str(path.relative_to(SOURCE_ROOT)))
    if importers:
        raise InventoryError(f"FacebookAudienceSection became reachable: {importers}")


def main() -> int:
    try:
        inventory = _load(INVENTORY_FILE)
        fixture = _load(FIXTURE_FILE)
        if inventory.get("schema_version") != 1 or inventory.get("frozen") is not True:
            raise InventoryError("inventory schema or frozen flag is invalid")
        _validate_source_snapshot(inventory)
        _validate_source_files(inventory)
        _validate_fixture(fixture)
        _validate_cards(inventory, fixture)
        _validate_non_rendered_claim(inventory)
    except InventoryError as exc:
        print(f"R1 INVENTORY FAIL: {exc}", file=sys.stderr)
        return 1
    print("R1 INVENTORY PASS: canonical source hashes, routes, cards and fixture contract are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
