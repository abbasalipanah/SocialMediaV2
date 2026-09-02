from __future__ import annotations

from datetime import UTC, date, datetime

from app.application.ports.checkpoints import CheckpointKey, ProviderCheckpoint
from app.application.ports.platforms import (
    ProviderAccount,
    ProviderCredential,
    ProviderRecord,
)
from app.application.ports.platforms.audience import AudienceSnapshot
from app.application.ports.platforms.content import ContentPage
from app.application.ports.platforms.profile import DailyMetricSnapshot, ProfileSnapshot
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.workers.linkedin import LinkedInReaders, collect_linkedin_account

NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)


class Metrics:
    def __init__(self) -> None:
        self.points = []
        self.breakdowns = []

    def upsert(self, point) -> None:
        self.points.append(point)

    def replace_breakdown(self, **kwargs) -> None:
        self.breakdowns.append(kwargs)


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


class Profile:
    def fetch_profile(self, account):
        return ProfileSnapshot(
            account_id=account.account_id,
            display_name="Example Company",
            handle="example-company",
            observed_at=NOW,
            metric_values={MetricId.FOLLOWERS: 500},
        )


class Daily:
    def fetch_daily_metrics(self, account, *, since, until):
        assert since == date(2026, 8, 2)
        assert until == date(2026, 8, 31)
        return (
            DailyMetricSnapshot(
                account_id=account.account_id,
                observed_on=until,
                metric_values={
                    MetricId.VIEWS: 100,
                    MetricId.REACH: 80,
                    MetricId.INTERACTIONS: 10,
                    MetricId.CLICKS: 3,
                    MetricId.FOLLOWER_GAINS: 2,
                    MetricId.PAGE_VIEWS: 8,
                },
            ),
        )


class Audience:
    def fetch_audience(self, account):
        return AudienceSnapshot(
            account_id=account.account_id,
            observed_at=NOW,
            breakdowns={"staff_count": {"SIZE_11_TO_50": 20}},
        )


class Content:
    def list_content(self, account, *, cursor=None):
        assert cursor is None
        return ContentPage(
            items=(
                ProviderRecord(
                    external_id="urn:li:share:1",
                    observed_at=NOW,
                    fields={
                        "content_type": "text",
                        "permalink": ("https://www.linkedin.com/feed/update/urn:li:share:1/"),
                        "message": "Company update",
                        "media_url": "",
                        "published_at": NOW,
                        "likes_count": 4,
                        "comments_count": 2,
                        "shares_count": 1,
                        "views_count": 100,
                        "reach_count": 80,
                        "interactions_count": 10,
                        "clicks_count": 3,
                    },
                ),
            ),
            next_cursor=None,
            observed_at=NOW,
        )


def test_linkedin_worker_collects_company_page_metrics_content_and_audience() -> None:
    metrics = Metrics()
    content = Records()
    checkpoints = Checkpoints()
    media_items: list[str] = []
    account = ProviderAccount(
        platform=PlatformId.LINKEDIN,
        account_id="1234",
        credential=ProviderCredential(access_token="access-value"),
    )

    result = collect_linkedin_account(
        account=account,
        local_account_id=81,
        brand_id=17,
        readers=LinkedInReaders(
            profile=Profile(),
            daily=Daily(),
            content=Content(),
            audience=Audience(),
        ),
        metric_store=metrics,
        content_store=content,
        checkpoint_store=checkpoints,
        persist_media=lambda _target, item: media_items.append(item.external_id) or 0,
        backfill_complete=False,
        today=date(2026, 9, 1),
    )

    assert result.status == "success"
    assert result.metric_count == 8
    assert result.content_count == 1
    assert result.media_count == 0
    assert result.backfill_complete is True
    assert [point.metric_id for point in metrics.points] == [
        MetricId.FOLLOWERS,
        MetricId.VIEWS,
        MetricId.REACH,
        MetricId.INTERACTIONS,
        MetricId.CLICKS,
        MetricId.FOLLOWER_GAINS,
        MetricId.PAGE_VIEWS,
    ]
    assert metrics.breakdowns[0]["breakdown_key"] == "staff_count"
    assert content.items[0].clicks_count == 3
    assert media_items == ["urn:li:share:1"]
    assert len(checkpoints.values) == 2


def test_linkedin_worker_keeps_other_progress_when_daily_is_unavailable() -> None:
    class FailedDaily:
        def fetch_daily_metrics(self, account, *, since, until):
            raise PermissionError("reporting_scope_unavailable")

    result = collect_linkedin_account(
        account=ProviderAccount(
            platform=PlatformId.LINKEDIN,
            account_id="1234",
            credential=ProviderCredential(access_token="access-value"),
        ),
        local_account_id=81,
        brand_id=17,
        readers=LinkedInReaders(
            profile=Profile(),
            daily=FailedDaily(),
            content=Content(),
            audience=Audience(),
        ),
        metric_store=Metrics(),
        content_store=Records(),
        checkpoint_store=Checkpoints(),
        persist_media=lambda _target, _item: 0,
        backfill_complete=False,
        today=date(2026, 9, 1),
    )

    assert result.status == "partial"
    assert result.error_code == "daily_unavailable"
    assert result.metric_count == 2
    assert result.content_count == 1
