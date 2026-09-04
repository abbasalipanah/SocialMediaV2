from __future__ import annotations

from datetime import UTC, date, datetime

from app.application.ports.reporting import ReportingComment, ReportingContent
from app.application.queries.dashboard_aggregation import content_cards, mention_summary
from app.domain.platforms import X_MENTIONS_CONTENT_ID, PlatformId
from app.domain.reporting import DataStatus


def test_x_post_analytics_cross_the_dashboard_contract_without_renaming_clicks() -> None:
    row = ReportingContent(
        account_id=81,
        brand_id="18",
        platform=PlatformId.X,
        external_content_id="1900000000000000001",
        content_type="video",
        permalink="https://x.com/i/web/status/1900000000000000001",
        message="Owned video",
        media_url="",
        published_at=datetime(2026, 8, 31, 10, tzinfo=UTC),
        likes_count=7,
        comments_count=3,
        shares_count=3,
        views_count=100,
        interactions_count=20,
        saves_count=4,
        reposts_count=2,
        quotes_count=1,
        link_clicks=6,
        profile_clicks=5,
        video_views_count=80,
        video_playback_0_count=60,
        video_playback_25_count=50,
        video_playback_50_count=40,
        video_playback_75_count=30,
        video_playback_100_count=24,
        completion_rate=0.4,
    )

    card = content_cards((row,))[0]

    assert card.reposts_count == 2
    assert card.quotes_count == 1
    assert card.link_clicks == 6
    assert card.profile_clicks == 5
    assert card.profile_visits is None
    assert card.video_views_count == 80
    assert card.video_playback_100_count == 24
    assert card.completion_rate == 0.4


def test_x_mentions_are_counted_by_day_and_stable_author_identity() -> None:
    rows = (
        ReportingComment(
            account_id=81,
            platform=PlatformId.X,
            external_content_id=X_MENTIONS_CONTENT_ID,
            external_comment_id="1900000000000000002",
            author_name="reader",
            author_id="987654321",
            text="@example useful report",
            like_count=1,
            reply_count=0,
            answered=False,
            commented_at=datetime(2026, 8, 31, 11, tzinfo=UTC),
        ),
        ReportingComment(
            account_id=81,
            platform=PlatformId.X,
            external_content_id=X_MENTIONS_CONTENT_ID,
            external_comment_id="1900000000000000003",
            author_name="reader-renamed",
            author_id="987654321",
            text="@example second mention",
            like_count=0,
            reply_count=0,
            answered=False,
            commented_at=datetime(2026, 8, 31, 12, tzinfo=UTC),
        ),
    )

    summary = mention_summary(rows, accounts_available=True)

    assert summary.total == 2
    assert summary.unique_authors == 1
    assert summary.daily[0].observed_on == date(2026, 8, 31)
    assert summary.daily[0].value == 2
    assert summary.data_status is DataStatus.AVAILABLE


def test_empty_x_mention_result_does_not_claim_a_verified_zero() -> None:
    summary = mention_summary((), accounts_available=True)

    assert summary.total == 0
    assert summary.data_status is DataStatus.PARTIAL
