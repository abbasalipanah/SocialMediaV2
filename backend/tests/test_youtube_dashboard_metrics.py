from __future__ import annotations

from datetime import date

from app.application.ports.reporting import ReportingMetric
from app.application.queries.dashboard_aggregation import metric_breakdowns
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId


def test_youtube_daily_playback_breakdowns_sum_over_selected_period() -> None:
    samples = (
        ReportingMetric(
            account_id=1,
            brand_id="18",
            platform=PlatformId.YOUTUBE,
            observed_on=date(2026, 8, 1),
            metric_id=MetricId.VIEWS,
            value=40,
            breakdown_key="youtube_device_type",
            breakdown_value="MOBILE",
        ),
        ReportingMetric(
            account_id=1,
            brand_id="18",
            platform=PlatformId.YOUTUBE,
            observed_on=date(2026, 8, 2),
            metric_id=MetricId.VIEWS,
            value=60,
            breakdown_key="youtube_device_type",
            breakdown_value="MOBILE",
        ),
        ReportingMetric(
            account_id=1,
            brand_id="18",
            platform=PlatformId.YOUTUBE,
            observed_on=date(2026, 8, 2),
            metric_id=MetricId.VIEWS,
            value=25,
            breakdown_key="youtube_device_type",
            breakdown_value="TV",
        ),
    )

    breakdown = metric_breakdowns(samples)[0]

    assert breakdown.dimension == "youtube_device_type"
    assert [(item.key, item.value) for item in breakdown.items] == [
        ("MOBILE", 100),
        ("TV", 25),
    ]
    assert breakdown.items[0].percentage == 80


def test_non_youtube_breakdown_keeps_latest_snapshot_semantics() -> None:
    samples = tuple(
        ReportingMetric(
            account_id=1,
            brand_id="18",
            platform=PlatformId.INSTAGRAM,
            observed_on=observed_on,
            metric_id=MetricId.FOLLOWERS,
            value=value,
            breakdown_key="audience_countries",
            breakdown_value="TR",
        )
        for observed_on, value in (
            (date(2026, 8, 1), 40),
            (date(2026, 8, 2), 60),
        )
    )

    breakdown = metric_breakdowns(samples)[0]

    assert breakdown.items[0].value == 60


def test_youtube_demographics_keep_latest_snapshot_semantics() -> None:
    samples = tuple(
        ReportingMetric(
            account_id=1,
            brand_id="18",
            platform=PlatformId.YOUTUBE,
            observed_on=observed_on,
            metric_id=MetricId.VIEWER_PERCENTAGE,
            value=value,
            breakdown_key="youtube_viewer_gender",
            breakdown_value="female",
        )
        for observed_on, value in (
            (date(2026, 8, 1), 45),
            (date(2026, 8, 2), 55),
        )
    )

    breakdown = metric_breakdowns(samples)[0]

    assert breakdown.items[0].value == 55
