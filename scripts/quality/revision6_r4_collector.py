#!/usr/bin/env python3
"""Static Revision 6 / R4 collector and persistence contract gate."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require(path: str, fragments: tuple[str, ...]) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    missing = [fragment for fragment in fragments if fragment not in text]
    if missing:
        raise SystemExit(f"R4 contract missing in {path}: {missing}")


def main() -> None:
    require(
        "backend/app/workers/collector.py",
        (
            "collect_audience(",
            "stories=True",
            'checkpoint_account_id=f"{account.account_id}.stories"',
            '"comment.list" in scopes',
            "request_budget=500",
            "_tiktok_access_context",
        ),
    )
    require(
        "backend/app/infrastructure/providers/tiktok/accounts/transport.py",
        (
            "RETRYABLE_STATUS_CODES",
            "provider_request_budget_exhausted",
            "retry-after",
            "provider_response_too_large",
        ),
    )
    require(
        "backend/app/infrastructure/providers/tiktok/accounts/comments.py",
        ("TikTokCommentsReader", 'data.get("comments")', "reply_comment_total"),
    )
    require(
        "backend/app/infrastructure/providers/tiktok/accounts/audience.py",
        ("TikTokAudienceReader", "audience_countries", "audience_activity"),
    )
    require(
        "backend/app/infrastructure/providers/meta/instagram/content_insights.py",
        (
            "fetch_content_insights",
            "story_navigation_action_type",
            "completion_rate",
        ),
    )
    require(
        "backend/app/application/services/collection/media.py",
        ("cover_candidates", "thumbnail_candidates", "media_url_candidates"),
    )
    migration = ROOT / "backend/migrations/0002_content_story_parity.sql"
    require(
        str(migration.relative_to(ROOT)),
        (
            "views_count double precision",
            "cover_candidates jsonb",
            "full_video_watched_rate double precision",
            "navigation_count double precision",
            "completion_rate double precision",
        ),
    )
    print(
        json.dumps(
            {
                "status": "pass",
                "phase": "revision6_r4",
                "source_fallbacks": 0,
                "migration": migration.name,
                "provider_unavailable_policy": "null_or_partial",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
