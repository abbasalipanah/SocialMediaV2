"""Privacy-safe projection helpers for public comment reporting."""

from __future__ import annotations

import re
from dataclasses import replace

from app.domain.reporting import CommunitySummary, OverviewDashboard, PlatformDashboard

ANONYMOUS_COMMENT_AUTHOR = "Anonymous"

# A mention must not be part of an e-mail/local identifier. Usernames may contain
# Unicode letters/numbers, underscores, hyphens and internal dots; a trailing
# sentence dot is deliberately kept outside the match.
_COMMENT_MENTION = re.compile(r"(?<![\w.%+-])@(\w(?:[\w.-]*\w)?)", flags=re.UNICODE)


def mask_comment_mentions(value: str) -> str:
    """Keep only the first and final username characters in @mentions."""

    def replacement(match: re.Match[str]) -> str:
        username = match.group(1)
        return f"@{username[0]}***{username[-1]}"

    return _COMMENT_MENTION.sub(replacement, value)


def redact_community(summary: CommunitySummary) -> CommunitySummary:
    """Remove author identities and mask mentions from a community projection."""

    return replace(
        summary,
        top_commenters=tuple(
            replace(item, name=ANONYMOUS_COMMENT_AUTHOR)
            for item in summary.top_commenters
        ),
        top_liked_comments=tuple(
            replace(
                item,
                name=ANONYMOUS_COMMENT_AUTHOR,
                comment=mask_comment_mentions(item.comment),
            )
            for item in summary.top_liked_comments
        ),
    )


def redact_dashboard_comments(
    dashboard: PlatformDashboard | OverviewDashboard,
) -> PlatformDashboard | OverviewDashboard:
    """Return a dashboard safe for API, visual and workbook presentation."""

    if isinstance(dashboard, OverviewDashboard):
        return replace(
            dashboard,
            community=redact_community(dashboard.community),
            platforms=tuple(
                replace(platform, community=redact_community(platform.community))
                for platform in dashboard.platforms
            ),
        )
    return replace(dashboard, community=redact_community(dashboard.community))


__all__ = [
    "ANONYMOUS_COMMENT_AUTHOR",
    "mask_comment_mentions",
    "redact_community",
    "redact_dashboard_comments",
]
