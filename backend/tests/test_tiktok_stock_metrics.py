"""A follower total of zero is a missing day, not an observation.

TikTok returns `0` for a cumulative field on a day it has not finalised. Stored
as a real value it reads as "this account lost every follower and got them
back": the trend collapses to the axis and the dashboard's headline follower
count -- which takes the last day in range -- shows nothing at all. One such day
sat between 77 and 79 followers.
"""

from __future__ import annotations

from datetime import date

from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.infrastructure.providers.tiktok.accounts.daily_metrics import (
    TikTokDailyMetricsReader,
)

SINCE = date(2026, 8, 17)
UNTIL = date(2026, 8, 19)


def _account() -> ProviderAccount:
    return ProviderAccount(
        platform=PlatformId.TIKTOK,
        account_id="business-1",
        credential=ProviderCredential(access_token="opaque"),
    )


def _read(rows: list[dict[str, object]]):
    reader = TikTokDailyMetricsReader(
        lambda _account_id, _since, _until: {
            "code": 0,
            "message": "OK",
            "request_id": "r",
            "data": {"metrics": rows},
        }
    )
    return reader.fetch_daily_metrics(_account(), since=SINCE, until=UNTIL)


def _followers(snapshots) -> dict[date, float | int | None]:
    return {
        snapshot.observed_on: snapshot.metric_values.get(MetricId.FOLLOWERS)
        for snapshot in snapshots
    }


def test_a_zero_total_is_left_out_rather_than_stored() -> None:
    followers = _followers(
        _read(
            [
                {"date": "2026-08-17", "followers_count": 77},
                {"date": "2026-08-18", "followers_count": 0},
                {"date": "2026-08-19", "followers_count": 79},
            ]
        )
    )

    assert followers.get(date(2026, 8, 17)) == 77
    assert followers.get(date(2026, 8, 19)) == 79
    assert date(2026, 8, 18) not in followers


def test_a_day_keeps_its_other_metrics_when_the_total_is_missing() -> None:
    # The gap is in the follower total only; whatever else the day reported is
    # still a real observation.
    snapshots = _read(
        [{"date": "2026-08-18", "followers_count": 0, "video_views": 1200}]
    )

    assert len(snapshots) == 1
    values = snapshots[0].metric_values
    assert values.get(MetricId.VIEWS) == 1200
    assert MetricId.FOLLOWERS not in values


def test_a_flow_metric_may_legitimately_be_zero() -> None:
    # No views on a quiet day is a fact about that day, unlike a total of zero.
    snapshots = _read([{"date": "2026-08-18", "video_views": 0}])

    assert snapshots[0].metric_values.get(MetricId.VIEWS) == 0
