from __future__ import annotations

from datetime import UTC, datetime

from app.application.ports.checkpoints import CheckpointKey, ProviderCheckpoint
from app.application.ports.platforms import (
    ProviderAccount,
    ProviderCredential,
    ProviderRecord,
)
from app.application.ports.platforms.content import ContentPage
from app.application.ports.platforms.profile import ProfileSnapshot
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.workers.x import XReaders, collect_x_account

NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)


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
        if (current.version if current else None) != expected_version:
            return False
        self.values[checkpoint.key] = checkpoint
        return True


class Profile:
    def fetch_profile(self, account):
        return ProfileSnapshot(
            account_id=account.account_id,
            display_name="Example",
            handle="@example",
            observed_at=NOW,
            metric_values={MetricId.FOLLOWERS: 100, MetricId.MEDIA_COUNT: 5},
        )


class Content:
    def list_content(self, account, *, cursor=None):
        return ContentPage(
            items=(
                ProviderRecord(
                    external_id="1900000000000000001",
                    observed_at=NOW,
                    fields={
                        "content_type": "post",
                        "permalink": "https://x.com/i/web/status/1900000000000000001",
                        "message": "Example post",
                        "media_url": "",
                        "published_at": NOW,
                        "likes_count": 3,
                        "comments_count": 1,
                        "shares_count": 2,
                        "views_count": 20,
                        "interactions_count": 6,
                    },
                ),
            ),
            next_cursor=None,
            observed_at=NOW,
        )


class PagingContent:
    def __init__(self) -> None:
        self.cursors: list[str | None] = []

    def list_content(self, account, *, cursor=None):
        del account
        self.cursors.append(cursor)
        suffix = "1" if cursor is None else "2"
        return ContentPage(
            items=(
                ProviderRecord(
                    external_id=f"190000000000000000{suffix}",
                    observed_at=NOW,
                    fields={
                        "content_type": "post",
                        "permalink": f"https://x.com/i/web/status/190000000000000000{suffix}",
                        "message": f"Example post {suffix}",
                        "media_url": "",
                        "published_at": NOW,
                        "likes_count": 3,
                        "comments_count": 1,
                        "shares_count": 2,
                        "views_count": 20,
                        "interactions_count": 6,
                    },
                ),
            ),
            next_cursor="page-2" if cursor is None else None,
            observed_at=NOW,
        )


def test_x_worker_collects_profile_and_content_without_comments_or_audience() -> None:
    metrics = Records()
    content = Records()
    checkpoints = Checkpoints()
    account = ProviderAccount(
        platform=PlatformId.X,
        account_id="123456789",
        credential=ProviderCredential(access_token="access-value"),
    )

    result = collect_x_account(
        account=account,
        local_account_id=81,
        brand_id=17,
        readers=XReaders(profile=Profile(), content=Content()),
        metric_store=metrics,
        content_store=content,
        checkpoint_store=checkpoints,
        persist_media=lambda _target, _item: 0,
        backfill_complete=False,
    )

    assert result.status == "success"
    assert result.metric_count == 2
    assert result.content_count == 1
    assert result.backfill_complete is True
    assert [point.metric_id for point in metrics.items] == [
        MetricId.FOLLOWERS,
        MetricId.MEDIA_COUNT,
    ]
    assert content.items[0].external_content_id == "1900000000000000001"


def test_x_worker_resumes_bounded_backfill_from_durable_cursor() -> None:
    metrics = Records()
    content = Records()
    checkpoints = Checkpoints()
    reader = PagingContent()
    account = ProviderAccount(
        platform=PlatformId.X,
        account_id="123456789",
        credential=ProviderCredential(access_token="access-value"),
    )
    kwargs = {
        "account": account,
        "local_account_id": 81,
        "brand_id": 17,
        "readers": XReaders(profile=Profile(), content=reader),
        "metric_store": metrics,
        "content_store": content,
        "checkpoint_store": checkpoints,
        "persist_media": lambda _target, _item: 0,
        "backfill_complete": False,
    }

    first = collect_x_account(**kwargs)
    second = collect_x_account(**kwargs)

    assert first.status == "partial"
    assert first.error_code == "content_partial"
    assert first.backfill_complete is False
    assert second.status == "success"
    assert second.backfill_complete is True
    assert reader.cursors == [None, "page-2"]
    assert [item.external_content_id for item in content.items] == [
        "1900000000000000001",
        "1900000000000000002",
    ]
