#!/usr/bin/env python3
"""Static Revision 6 / R5 parity checks against the frozen R1 oracle."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
INVENTORY = ROOT / "docs" / "revision6" / "r1" / "canonical_frontend_inventory.json"
STORIES_OVERRIDE = ROOT / "docs" / "revision6" / "overrides" / "instagram_stories_main_2026-08-07.json"


class R5Error(RuntimeError):
    pass


def require(text: str, values: list[str], label: str) -> None:
    missing = [value for value in values if value not in text]
    if missing:
        raise R5Error(f"{label} missing: {missing}")


def forbid(text: str, values: list[str], label: str) -> None:
    present = [value for value in values if value in text]
    if present:
        raise R5Error(f"{label} contains forbidden visible items: {present}")


def main() -> int:
    try:
        inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
        stories_override = json.loads(STORIES_OVERRIDE.read_text(encoding="utf-8"))
        if inventory.get("frozen") is not True:
            raise R5Error("R1 inventory is not frozen")
        if stories_override.get("approved") is not True:
            raise R5Error("Instagram Stories visible override is not approved")

        routes = (FRONTEND / "src/routes/AppRoutes.tsx").read_text(encoding="utf-8")
        require(routes, [
            'path="/auth/sso/consume"',
            'path="/sso/consume"',
            'path="facebook"',
            'path="instagram"',
            'path="tiktok"',
            'path="settings"',
            'Route index element={<SettingsGuard><SettingsPage',
            'Route path="*" element={<SettingsGuard><SettingsPage',
        ], "routes")
        forbid(routes, ['path="overview"', 'path="integrations"'], "routes")

        sidebar = (FRONTEND / "src/layout/Sidebar.tsx").read_text(encoding="utf-8")
        require(sidebar, ["Home", "Analytics", "Social Media", "Facebook", "Instagram", "TikTok", "Settings", "SocialMedia standalone"], "sidebar")
        forbid(sidebar, ["Overview", "Integrations", "Support", "Back to Accumulate", "Sign out", "locked"], "sidebar")

        catalog = (FRONTEND / "src/features/dashboard/catalog.ts").read_text(encoding="utf-8")
        require(catalog, ["Last 7 Days", "Last 30 Days", "Last 90 Days", "Last 365 Days"], "date ranges")

        platform_page = (FRONTEND / "src/features/dashboard/PlatformPage.tsx").read_text(encoding="utf-8")
        require(platform_page, ["popstate", "document.title", "application/json", "Download dashboard data", "date_range.end_on"], "dashboard behavior")
        forbid(platform_page, ["ExportPng", "Export PNG"], "dashboard behavior")

        dashboard_files = [
            FRONTEND / "src/features/facebook/FacebookPulseDashboard.tsx",
            FRONTEND / "src/features/instagram/InstagramPulseDashboard.tsx",
            FRONTEND / "src/features/instagram/InstagramStoriesWorkspace.tsx",
            FRONTEND / "src/features/tiktok/TikTokPulseDashboard.tsx",
            FRONTEND / "src/features/dashboard/AudienceDemographicsCard.tsx",
        ]
        dashboard_text = "\n".join(path.read_text(encoding="utf-8") for path in dashboard_files)
        titles = {
            row["title"]
            for row in inventory["cards"].values()
            if isinstance(row, dict) and isinstance(row.get("title"), str)
        }
        titles.remove("Page View Type or Video View Type")
        titles.update({"Page View Type", "Video View Type"})
        titles.remove("Age & Gender")
        titles.add("Age &amp; Gender")
        titles.difference_update(stories_override["replaces_visible_story_cards"])
        titles.update(stories_override["approved_visible_story_cards"])
        require(dashboard_text, sorted(titles), "card titles")
        require(dashboard_text, [
            "Not provided by TikTok Organic API",
            "Sentiment is not inferred without a configured analysis model.",
            "No videos were collected in this period.",
            "No heatmap data in selected range.",
        ], "canonical empty/unavailable copy")
        forbid(dashboard_text, ["Content Winners by Objective", "Unanswered Comments Queue", "Answered Comments Log", "Interactions Trend"], "dashboard cards")

        settings = (FRONTEND / "src/features/settings/index.tsx").read_text(encoding="utf-8")
        require(settings, [
            "Social media setup",
            "Brands, linked accounts, backfill and nightly sync in one table.",
            "Search brands",
            "Meta Access",
            "Discovery",
            "Collector",
            "Last Sync",
            "Nightly",
            "Add brand",
        ], "Settings surface")

        snapshots = FRONTEND / "e2e/revision6-r5.spec.ts-snapshots"
        expected_snapshots = {
            f"{platform}-cover-{viewport}-chromium-linux.png"
            for platform in ("facebook", "instagram", "tiktok")
            for viewport in ("desktop", "mobile")
        }
        actual_snapshots = {path.name for path in snapshots.glob("*.png") if path.stat().st_size > 0}
        if expected_snapshots != actual_snapshots:
            raise R5Error(
                f"visual snapshot set mismatch: missing={sorted(expected_snapshots - actual_snapshots)}, "
                f"extra={sorted(actual_snapshots - expected_snapshots)}"
            )
        story_snapshot_root = FRONTEND / "e2e/instagram-stories.spec.ts-snapshots"
        expected_story_snapshots = {
            f"instagram-stories-{viewport}-chromium-linux.png"
            for viewport in ("desktop", "mobile")
        }
        actual_story_snapshots = {
            path.name for path in story_snapshot_root.glob("*.png") if path.stat().st_size > 0
        }
        if expected_story_snapshots != actual_story_snapshots:
            raise R5Error(
                "Instagram Stories visual snapshot set mismatch: "
                f"missing={sorted(expected_story_snapshots - actual_story_snapshots)}, "
                f"extra={sorted(actual_story_snapshots - expected_story_snapshots)}"
            )
    except (OSError, KeyError, TypeError, ValueError, R5Error) as exc:
        print(f"R5 FRONTEND FAIL: {exc}", file=sys.stderr)
        return 1

    print(
        "R5 FRONTEND PASS: canonical routes, navigation, date/download behavior, "
        f"{len(titles)} unique card titles, Settings copy, 6 canonical and "
        "2 approved Instagram Stories visual baselines are present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
