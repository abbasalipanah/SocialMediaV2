from __future__ import annotations

from datetime import UTC, date, datetime

from app.application.ports.checkpoints import CheckpointKey, ProviderCheckpoint
from app.application.ports.platforms import (
    ProviderAccount,
    ProviderCredential,
    ProviderRecord,
)
from app.application.ports.platforms.comments import CommentPage
from app.application.ports.platforms.content import ContentPage
from app.application.ports.platforms.profile import (
    DailyMetricSnapshot,
    ProfileSnapshot,
)
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.workers.youtube import YouTubeReaders, collect_youtube_account

NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)


class Metrics:
    def __init__(self) -> None:
        self.points = []

    def upsert(self, point) -> None:
        self.points.append(point)

    def replace_breakdown(self, **_kwargs) -> None:
        raise AssertionError("unexpected_breakdown")


class Records:
    def __init__(self) -> None:
        self.items = []

    def upsert(self, record) -> None:
        self.items.append(record)


class Checkpoints:
    def __init__(self) -> None:
        self.values: dict[CheckpointKey, ProviderCheckpoint] = {}

    def get(self, key):
        return self.values.get(key)

    def put(self, checkpoint, *, expected_version):
        current = self.values.get(checkpoint.key)
        current_version = current.version if current is not None else None
        if current_version != expected_version:
            return False
        self.values[checkpoint.key] = checkpoint
        return True

    def claim_once(self, key, operation_id, expires_at):
        raise AssertionError("unexpected_claim")


class Profile:
    def fetch_profile(self, account):
        return ProfileSnapshot(
            account_id=account.account_id,
            display_name="Example Channel",
            handle="@example",
            observed_at=NOW,
            metric_values={MetricId.FOLLOWERS: 100, MetricId.MEDIA_COUNT: 5},
        )


class Daily:
    def fetch_daily_metrics(self, account, *, since, until):
        assert since == date(2026, 8, 2)
        assert until == date(2026, 8, 31)
        return (
            DailyMetricSnapshot(
                account_id=account.account_id,
                observed_on=until,
                metric_values={MetricId.VIEWS: 40, MetricId.INTERACTIONS: 4},
            ),
        )


class Content:
    def list_content(self, account, *, cursor=None):
        assert cursor is None
        return ContentPage(
            items=(
                ProviderRecord(
                    external_id="video-1",
                    observed_at=NOW,
                    fields={
                        "content_type": "video",
                        "permalink": "https://www.youtube.com/watch?v=video-1",
                        "message": "Example video",
                        "media_url": "",
                        "published_at": NOW,
                        "likes_count": 3,
                        "comments_count": 1,
                        "shares_count": None,
                        "views_count": 20,
                        "interactions_count": None,
                    },
                ),
            ),
            next_cursor=None,
            observed_at=NOW,
        )


class Comments:
    def list_comments(self, account, *, content_id, cursor=None):
        assert content_id == "video-1"
        assert cursor is None
        return CommentPage(
            content_id=content_id,
            items=(
                ProviderRecord(
                    external_id="comment-1",
                    observed_at=NOW,
                    fields={
                        "author_id": "author-1",
                        "author_name": "Person",
                        "text": "Hello",
                        "like_count": 1,
                        "reply_count": 0,
                        "attachment_type": None,
                        "attachment_media_type": None,
                        "attachment_url": None,
                        "commented_at": NOW,
                    },
                ),
            ),
            next_cursor=None,
            observed_at=NOW,
        )


def test_youtube_worker_collects_supported_capabilities_without_audience() -> None:
    metrics = Metrics()
    content = Records()
    comments = Records()
    checkpoints = Checkpoints()
    media_items: list[str] = []
    account = ProviderAccount(
        platform=PlatformId.YOUTUBE,
        account_id="UC-channel",
        credential=ProviderCredential(access_token="access-value"),
    )

    result = collect_youtube_account(
        account=account,
        local_account_id=81,
        brand_id=17,
        readers=YouTubeReaders(
            profile=Profile(),
            daily=Daily(),
            content=Content(),
            comments=Comments(),
        ),
        metric_store=metrics,
        content_store=content,
        comment_store=comments,
        checkpoint_store=checkpoints,
        persist_media=lambda _target, item: media_items.append(item.external_id) or 1,
        backfill_complete=False,
        today=date(2026, 9, 1),
    )

    assert result.status == "success"
    assert result.metric_count == 4
    assert result.content_count == 1
    assert result.comment_count == 1
    assert result.media_count == 1
    assert result.backfill_complete is True
    assert [point.metric_id for point in metrics.points] == [
        MetricId.FOLLOWERS,
        MetricId.MEDIA_COUNT,
        MetricId.VIEWS,
        MetricId.INTERACTIONS,
    ]
    assert content.items[0].shares_count is None
    assert comments.items[0].external_comment_id == "comment-1"
    assert media_items == ["video-1"]


def test_youtube_daily_failure_keeps_profile_and_content_progress() -> None:
    class FailedDaily:
        def fetch_daily_metrics(self, account, *, since, until):
            raise ValueError("analytics_unavailable")

    metrics = Metrics()
    content = Records()
    comments = Records()
    checkpoints = Checkpoints()
    result = collect_youtube_account(
        account=ProviderAccount(
            platform=PlatformId.YOUTUBE,
            account_id="UC-channel",
            credential=ProviderCredential(access_token="access-value"),
        ),
        local_account_id=81,
        brand_id=17,
        readers=YouTubeReaders(
            profile=Profile(),
            daily=FailedDaily(),
            content=Content(),
            comments=Comments(),
        ),
        metric_store=metrics,
        content_store=content,
        comment_store=comments,
        checkpoint_store=checkpoints,
        persist_media=lambda _target, _item: 0,
        backfill_complete=False,
        today=date(2026, 9, 1),
    )

    assert result.status == "partial"
    assert result.error_code == "daily_unavailable"
    assert result.metric_count == 2
    assert result.content_count == 1
    assert len(checkpoints.values) == 1
