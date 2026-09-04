from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.domain.metrics import MetricId, bootstrap_metric_catalog
from app.domain.platforms import CapabilityId, PlatformId
from app.infrastructure.providers.youtube import (
    YOUTUBE_BREAKDOWN_METRICS,
    YOUTUBE_DAILY_METRICS,
    YouTubeDailyMetricsReader,
    YouTubeProfileReader,
    YouTubeResponseError,
    channel_query,
    daily_breakdown_query,
    daily_metrics_query,
)

NOW = datetime(2026, 8, 31, 12, tzinfo=UTC)


def _account(platform: PlatformId = PlatformId.YOUTUBE) -> ProviderAccount:
    return ProviderAccount(
        platform=platform,
        account_id="UC-channel",
        credential=ProviderCredential(access_token="opaque"),
    )


def test_youtube_queries_match_read_only_provider_contracts() -> None:
    assert channel_query("UC-channel") == {
        "part": "id,snippet,statistics",
        "id": "UC-channel",
        "maxResults": "1",
    }
    assert daily_metrics_query(
        since=date(2026, 8, 1), until=date(2026, 8, 2)
    ) == {
        "ids": "channel==MINE",
        "startDate": "2026-08-01",
        "endDate": "2026-08-02",
        "metrics": ",".join(YOUTUBE_DAILY_METRICS),
        "dimensions": "day",
        "sort": "day",
    }
    assert daily_breakdown_query(
        since=date(2026, 8, 1),
        until=date(2026, 8, 2),
        dimension="deviceType",
    ) == {
        "ids": "channel==MINE",
        "startDate": "2026-08-01",
        "endDate": "2026-08-02",
        "metrics": ",".join(YOUTUBE_BREAKDOWN_METRICS),
        "dimensions": "day,deviceType",
        "sort": "day,-views",
    }


def test_youtube_profile_maps_channel_identity_and_public_counts() -> None:
    reader = YouTubeProfileReader(
        lambda account: {
            "items": [
                {
                    "id": account.account_id,
                    "snippet": {"title": "Example Channel", "customUrl": "@example"},
                    "statistics": {
                        "subscriberCount": "1200",
                        "videoCount": "48",
                        "viewCount": "99000",
                        "hiddenSubscriberCount": False,
                    },
                }
            ]
        },
        clock=lambda: NOW,
    )

    snapshot = reader.fetch_profile(_account())

    assert snapshot.account_id == "UC-channel"
    assert snapshot.display_name == "Example Channel"
    assert snapshot.handle == "@example"
    assert snapshot.observed_at == NOW
    assert snapshot.metric_values == {
        MetricId.FOLLOWERS: 1200,
        MetricId.MEDIA_COUNT: 48,
    }


def test_youtube_profile_preserves_hidden_subscriber_count_as_unavailable() -> None:
    reader = YouTubeProfileReader(
        lambda account: {
            "items": [
                {
                    "id": account.account_id,
                    "snippet": {"title": "Private Count"},
                    "statistics": {
                        "videoCount": "2",
                        "hiddenSubscriberCount": True,
                    },
                }
            ]
        }
    )

    snapshot = reader.fetch_profile(_account())

    assert snapshot.metric_values[MetricId.FOLLOWERS] is None
    assert snapshot.metric_values[MetricId.MEDIA_COUNT] == 2


def test_youtube_profile_rejects_wrong_account_and_provider_family() -> None:
    reader = YouTubeProfileReader(
        lambda account: {
            "items": [
                {
                    "id": "UC-other",
                    "snippet": {"title": "Wrong"},
                    "statistics": {"videoCount": "1"},
                }
            ]
        }
    )

    with pytest.raises(YouTubeResponseError, match="^channel_response_invalid$"):
        reader.fetch_profile(_account())
    with pytest.raises(ValueError, match="^provider_family_mismatch$"):
        reader.fetch_profile(_account(PlatformId.TIKTOK))


def test_youtube_daily_metrics_map_flows_and_sum_interactions() -> None:
    observed_args: list[tuple[date, date]] = []

    def fetch(
        account: ProviderAccount, since: date, until: date
    ) -> dict[str, object]:
        assert account.account_id == "UC-channel"
        observed_args.append((since, until))
        return {
            "columnHeaders": [
                {"name": name, "columnType": "METRIC", "dataType": "INTEGER"}
                for name in _columns()
            ],
            "rows": [
                ["2026-08-02", 110, 95, 420, 8, 3, 2, 5, 1, 4, 1],
                ["2026-08-01", 100, 85, 360, 7, 2, 1, 4, 0, 3, 0],
            ],
        }

    snapshots = YouTubeDailyMetricsReader(fetch).fetch_daily_metrics(
        _account(), since=date(2026, 8, 1), until=date(2026, 8, 2)
    )

    assert observed_args == [(date(2026, 8, 1), date(2026, 8, 2))]
    assert [snapshot.observed_on for snapshot in snapshots] == [
        date(2026, 8, 1),
        date(2026, 8, 2),
    ]
    assert snapshots[0].metric_values == {
        MetricId.VIEWS: 100,
        MetricId.ENGAGED_VIEWS: 85,
        MetricId.WATCH_TIME_MINUTES: 360,
        MetricId.VIDEO_LIKES_DAILY: 7,
        MetricId.VIDEO_COMMENTS_DAILY: 2,
        MetricId.VIDEO_SHARES_DAILY: 1,
        MetricId.FOLLOWS: 4,
        MetricId.UNFOLLOWS: 0,
        MetricId.PLAYLIST_ADDITIONS: 3,
        MetricId.PLAYLIST_REMOVALS: 0,
        MetricId.INTERACTIONS: 10,
    }
    assert snapshots[1].metric_values[MetricId.INTERACTIONS] == 13
    catalog = bootstrap_metric_catalog()
    for snapshot in snapshots:
        catalog.validate_values(
            platform=PlatformId.YOUTUBE,
            capability=CapabilityId.PROFILE,
            values=snapshot.metric_values,
        )


def test_youtube_daily_metrics_fail_closed_on_schema_drift_and_bad_days() -> None:
    missing_column = {
        "columnHeaders": [{"name": "day"}, {"name": "views"}],
        "rows": [["2026-08-01", 10]],
    }
    reader = YouTubeDailyMetricsReader(lambda account, since, until: missing_column)
    with pytest.raises(YouTubeResponseError, match="^analytics_response_invalid$"):
        reader.fetch_daily_metrics(
            _account(), since=date(2026, 8, 1), until=date(2026, 8, 1)
        )

    duplicate_day = {
        "columnHeaders": [{"name": name} for name in _columns()],
        "rows": [
            ["2026-08-01", 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            ["2026-08-01", 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
        ],
    }
    reader = YouTubeDailyMetricsReader(lambda account, since, until: duplicate_day)
    with pytest.raises(YouTubeResponseError, match="^analytics_day_invalid$"):
        reader.fetch_daily_metrics(
            _account(), since=date(2026, 8, 1), until=date(2026, 8, 1)
        )


def test_youtube_daily_metrics_reject_invalid_ranges() -> None:
    reader = YouTubeDailyMetricsReader(lambda account, since, until: {})

    with pytest.raises(ValueError, match="^metric_range_invalid$"):
        reader.fetch_daily_metrics(
            _account(), since=date(2026, 8, 2), until=date(2026, 8, 1)
        )
    with pytest.raises(ValueError, match="^metric_range_invalid$"):
        reader.fetch_daily_metrics(
            _account(), since=date(2026, 7, 1), until=date(2026, 8, 1)
        )


def test_youtube_daily_metrics_map_supported_playback_breakdowns() -> None:
    dimensions: list[str] = []

    def fetch_breakdown(
        account: ProviderAccount,
        since: date,
        until: date,
        dimension: str,
    ) -> dict[str, object]:
        dimensions.append(dimension)
        return {
            "columnHeaders": [
                {"name": "day"},
                {"name": dimension},
                {"name": "views"},
                {"name": "estimatedMinutesWatched"},
            ],
            "rows": [
                ["2026-08-01", f"{dimension}-a", 60, 120],
                ["2026-08-01", f"{dimension}-b", 40, 80],
            ],
        }

    reader = YouTubeDailyMetricsReader(
        lambda account, since, until: {
            "columnHeaders": [{"name": name} for name in _columns()],
            "rows": [["2026-08-01", 100, 80, 200, 7, 2, 1, 4, 0, 3, 0]],
        },
        fetch_breakdown,
    )

    snapshots = reader.fetch_daily_metrics(
        _account(), since=date(2026, 8, 1), until=date(2026, 8, 1)
    )

    assert dimensions == [
        "country",
        "deviceType",
        "insightTrafficSourceType",
        "subscribedStatus",
        "creatorContentType",
    ]
    assert snapshots[0].metric_breakdowns[MetricId.VIEWS]["youtube_country"] == {
        "country-a": 60,
        "country-b": 40,
    }
    assert snapshots[0].metric_breakdowns[MetricId.WATCH_TIME_MINUTES][
        "youtube_device_type"
    ] == {"deviceType-a": 120, "deviceType-b": 80}


def test_youtube_breakdown_query_rejects_unapproved_dimensions() -> None:
    with pytest.raises(ValueError, match="^metric_breakdown_invalid$"):
        daily_breakdown_query(
            since=date(2026, 8, 1),
            until=date(2026, 8, 2),
            dimension="gender",
        )


def _columns() -> tuple[str, ...]:
    return ("day", *YOUTUBE_DAILY_METRICS)
