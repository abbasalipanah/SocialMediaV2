from datetime import date

import pytest

from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.infrastructure.providers.tiktok.accounts.daily_metrics import (
    TikTokDailyMetricsReader,
)
from app.infrastructure.providers.tiktok.accounts.responses import TikTokResponseError

ACCOUNT = ProviderAccount(
    platform=PlatformId.TIKTOK,
    account_id="business-1",
    credential=ProviderCredential(access_token="fixture-access-value"),
)
DAY = date(2026, 7, 19)


def _response(comments: int) -> dict[str, object]:
    return {
        "code": 0,
        "message": "OK",
        "request_id": "daily-request",
        "data": {
            "metrics": [
                {
                    "date": DAY.isoformat(),
                    "followers_count": 10,
                    "likes": 4,
                    "comments": comments,
                    "shares": 2,
                }
            ]
        },
    }


def test_minus_one_metric_sentinel_is_treated_as_unavailable() -> None:
    snapshots = TikTokDailyMetricsReader(
        lambda _account_id, _since, _until: _response(-1)
    ).fetch_daily_metrics(ACCOUNT, since=DAY, until=DAY)

    assert snapshots[0].metric_values == {
        MetricId.FOLLOWERS: 10.0,
        MetricId.VIDEO_LIKES_DAILY: 4.0,
        MetricId.VIDEO_SHARES_DAILY: 2.0,
    }


def test_values_below_minus_one_remain_invalid() -> None:
    with pytest.raises(TikTokResponseError, match="daily_metric_value_invalid"):
        TikTokDailyMetricsReader(
            lambda _account_id, _since, _until: _response(-2)
        ).fetch_daily_metrics(ACCOUNT, since=DAY, until=DAY)
