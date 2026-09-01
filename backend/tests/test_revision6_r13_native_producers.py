from __future__ import annotations

import json
from datetime import date

from app.application.ports.persistence import MetricPoint
from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.application.ports.reporting import ReportingMetric
from app.application.queries.dashboard_aggregation import metric_cards, metric_series
from app.application.queries.dashboards import _with_reconstructed_follower_history
from app.application.services.collection import CollectionStatus, CollectionTarget
from app.application.services.collection.daily_metrics import collect_daily_metrics
from app.core.config import (
    TIKTOK_ACCOUNT_AUTHORIZATION_URL,
    TIKTOK_ACCOUNT_COMMENT_LIST_URL,
    TIKTOK_ACCOUNT_PROFILE_URL,
    TIKTOK_ACCOUNT_REFRESH_URL,
    TIKTOK_ACCOUNT_REVOKE_URL,
    TIKTOK_ACCOUNT_TOKEN_INFO_URL,
    TIKTOK_ACCOUNT_TOKEN_URL,
    TIKTOK_ACCOUNT_VIDEO_LIST_URL,
    TIKTOK_ACTIVATION_LINK_BASE,
    TIKTOK_APP_ID,
    TIKTOK_OPTIONAL_SCOPES,
    TIKTOK_PROVIDER_PROFILE,
    TIKTOK_REDIRECT_URI,
    TIKTOK_REQUIRED_SCOPES,
    TikTokConfig,
)
from app.domain.metrics import MetricId, bootstrap_metric_catalog
from app.domain.platforms import PlatformId
from app.infrastructure.providers.tiktok.accounts import (
    TIKTOK_DAILY_FIELDS,
    TikTokAccountsWireMapper,
    TikTokDailyMetricsReader,
)


class MemoryMetricStore:
    def __init__(self) -> None:
        self.rows: list[MetricPoint] = []

    def upsert(self, point: MetricPoint) -> None:
        self.rows = [
            row
            for row in self.rows
            if not (
                row.account_id == point.account_id
                and row.observed_on == point.observed_on
                and row.metric_id is point.metric_id
                and row.breakdown_key == point.breakdown_key
                and row.breakdown_value == point.breakdown_value
            )
        ]
        self.rows.append(point)

    def read(self, **_: object) -> tuple[MetricPoint, ...]:
        return tuple(self.rows)

    def replace_breakdown(self, **_: object) -> None:
        raise AssertionError("unexpected_breakdown")


def _tiktok_config() -> TikTokConfig:
    return TikTokConfig(
        provider_profile=TIKTOK_PROVIDER_PROFILE,
        app_id=TIKTOK_APP_ID,
        app_secret="fixture-app-value",
        secret_rotated_at=None,
        account_enabled=False,
        oauth_mode="disabled",
        collection_enabled=False,
        advertiser_enabled=False,
        required_scopes=TIKTOK_REQUIRED_SCOPES,
        optional_scopes=TIKTOK_OPTIONAL_SCOPES,
        authorization_url=TIKTOK_ACCOUNT_AUTHORIZATION_URL,
        token_url=TIKTOK_ACCOUNT_TOKEN_URL,
        refresh_url=TIKTOK_ACCOUNT_REFRESH_URL,
        revoke_url=TIKTOK_ACCOUNT_REVOKE_URL,
        token_info_url=TIKTOK_ACCOUNT_TOKEN_INFO_URL,
        profile_url=TIKTOK_ACCOUNT_PROFILE_URL,
        video_list_url=TIKTOK_ACCOUNT_VIDEO_LIST_URL,
        comment_list_url=TIKTOK_ACCOUNT_COMMENT_LIST_URL,
        redirect_uri=TIKTOK_REDIRECT_URI,
        activation_link_base=TIKTOK_ACTIVATION_LINK_BASE,
    )


def _reporting(rows: list[MetricPoint]) -> tuple[ReportingMetric, ...]:
    return tuple(
        ReportingMetric(
            account_id=row.account_id,
            brand_id=str(row.brand_id),
            platform=row.platform,
            observed_on=row.observed_on,
            metric_id=row.metric_id,
            value=float(row.value),
            breakdown_key=row.breakdown_key,
            breakdown_value=row.breakdown_value,
        )
        for row in rows
    )


def test_directional_follower_snapshot_delta_is_versioned_for_every_platform() -> None:
    catalog = bootstrap_metric_catalog()
    for platform in PlatformId:
        samples = tuple(
            ReportingMetric(
                account_id=7,
                brand_id="4",
                platform=platform,
                observed_on=observed_on,
                metric_id=MetricId.FOLLOWERS,
                value=value,
            )
            for observed_on, value in (
                (date(2026, 8, 1), 100),
                (date(2026, 8, 2), 112),
                (date(2026, 8, 3), 109),
            )
        )
        cards, _ = metric_cards(
            platform=platform,
            account_ids=(7,),
            samples=samples,
            previous_samples=(),
            catalog=catalog,
        )
        by_id = {card.metric_id: card for card in cards}
        assert by_id[MetricId.NEW_FOLLOWERS].value == 12
        assert by_id[MetricId.FOLLOWS].value == 12
        assert by_id[MetricId.UNFOLLOWS].value == 3
        assert by_id[MetricId.FOLLOWERS_NET].value == 9
        assert by_id[MetricId.FOLLOWS].methodology == (
            "derived:positive_snapshot_delta:v1:consecutive_utc_day_snapshots"
        )
        assert by_id[MetricId.UNFOLLOWS].methodology == (
            "derived:negative_snapshot_delta:v1:consecutive_utc_day_snapshots"
        )

        series = {
            item.metric_id: item
            for item in metric_series(
                platform=platform,
                samples=samples,
                catalog=catalog,
            )
        }
        assert [point.value for point in series[MetricId.FOLLOWS].points] == [12, 0]
        assert [point.value for point in series[MetricId.UNFOLLOWS].points] == [0, 3]
        assert [point.value for point in series[MetricId.FOLLOWERS_NET].points] == [12, -3]


def test_direct_provider_follower_flow_takes_precedence_and_is_labeled_provider() -> None:
    catalog = bootstrap_metric_catalog()
    samples = (
        ReportingMetric(
            account_id=7,
            brand_id="4",
            platform=PlatformId.INSTAGRAM,
            observed_on=date(2026, 8, 1),
            metric_id=MetricId.FOLLOWERS,
            value=100,
        ),
        ReportingMetric(
            account_id=7,
            brand_id="4",
            platform=PlatformId.INSTAGRAM,
            observed_on=date(2026, 8, 2),
            metric_id=MetricId.FOLLOWERS,
            value=104,
        ),
        ReportingMetric(
            account_id=7,
            brand_id="4",
            platform=PlatformId.INSTAGRAM,
            observed_on=date(2026, 8, 2),
            metric_id=MetricId.FOLLOWS,
            value=9,
        ),
    )
    cards, _ = metric_cards(
        platform=PlatformId.INSTAGRAM,
        account_ids=(7,),
        samples=samples,
        previous_samples=(),
        catalog=catalog,
    )
    follows = next(card for card in cards if card.metric_id is MetricId.FOLLOWS)
    assert follows.value == 9
    assert follows.methodology == "provider_flow"


def test_provider_flow_and_snapshot_delta_are_merged_per_day() -> None:
    catalog = bootstrap_metric_catalog()
    samples = tuple(
        ReportingMetric(
            account_id=7,
            brand_id="4",
            platform=PlatformId.INSTAGRAM,
            observed_on=observed_on,
            metric_id=metric_id,
            value=value,
        )
        for observed_on, metric_id, value in (
            (date(2026, 8, 1), MetricId.FOLLOWERS, 100),
            (date(2026, 8, 2), MetricId.FOLLOWERS, 104),
            (date(2026, 8, 2), MetricId.FOLLOWS, 9),
            (date(2026, 8, 3), MetricId.FOLLOWERS, 105),
        )
    )

    cards, _ = metric_cards(
        platform=PlatformId.INSTAGRAM,
        account_ids=(7,),
        samples=samples,
        previous_samples=(),
        catalog=catalog,
    )
    follows = next(card for card in cards if card.metric_id is MetricId.FOLLOWS)
    assert follows.value == 10
    assert follows.methodology == (
        "provider_flow_with_derived_fallback:positive_snapshot_delta:"
        "v1:consecutive_utc_day_snapshots"
    )

    series = {
        item.metric_id: item
        for item in metric_series(
            platform=PlatformId.INSTAGRAM,
            samples=samples,
            catalog=catalog,
        )
    }
    assert [(point.observed_on, point.value) for point in series[MetricId.FOLLOWS].points] == [
        (date(2026, 8, 2), 9),
        (date(2026, 8, 3), 1),
    ]
    assert series[MetricId.FOLLOWS].methodology == follows.methodology


def test_current_follower_snapshot_reconstructs_history_only_across_complete_flows() -> None:
    rows = (
        ReportingMetric(
            account_id=7,
            brand_id="4",
            platform=PlatformId.INSTAGRAM,
            observed_on=date(2026, 8, 3),
            metric_id=MetricId.FOLLOWERS,
            value=110,
        ),
        *(
            ReportingMetric(
                account_id=7,
                brand_id="4",
                platform=PlatformId.INSTAGRAM,
                observed_on=observed_on,
                metric_id=metric_id,
                value=value,
            )
            for observed_on, metric_id, value in (
                (date(2026, 8, 3), MetricId.FOLLOWS, 8),
                (date(2026, 8, 3), MetricId.UNFOLLOWS, 3),
                (date(2026, 8, 2), MetricId.FOLLOWS, 7),
                (date(2026, 8, 2), MetricId.UNFOLLOWS, 2),
                (date(2026, 8, 1), MetricId.FOLLOWS, 5),
            )
        ),
    )
    reconstructed = _with_reconstructed_follower_history(rows)
    follower_values = {
        row.observed_on: row.value for row in reconstructed if row.metric_id is MetricId.FOLLOWERS
    }
    assert follower_values == {
        date(2026, 8, 1): 100,
        date(2026, 8, 2): 105,
        date(2026, 8, 3): 110,
    }


def test_next_day_follower_snapshot_bridges_instagram_finalization_lag() -> None:
    rows = (
        ReportingMetric(
            account_id=7,
            brand_id="4",
            platform=PlatformId.INSTAGRAM,
            observed_on=date(2026, 8, 4),
            metric_id=MetricId.FOLLOWERS,
            value=110,
        ),
        ReportingMetric(
            account_id=7,
            brand_id="4",
            platform=PlatformId.INSTAGRAM,
            observed_on=date(2026, 8, 5),
            metric_id=MetricId.FOLLOWERS,
            value=109,
        ),
        *(
            ReportingMetric(
                account_id=7,
                brand_id="4",
                platform=PlatformId.INSTAGRAM,
                observed_on=observed_on,
                metric_id=metric_id,
                value=value,
            )
            for observed_on, metric_id, value in (
                (date(2026, 8, 3), MetricId.FOLLOWS, 8),
                (date(2026, 8, 3), MetricId.UNFOLLOWS, 3),
                (date(2026, 8, 2), MetricId.FOLLOWS, 7),
                (date(2026, 8, 2), MetricId.UNFOLLOWS, 2),
                (date(2026, 8, 1), MetricId.FOLLOWS, 5),
            )
        ),
    )

    reconstructed = _with_reconstructed_follower_history(rows)
    follower_values = {
        row.observed_on: row.value for row in reconstructed if row.metric_id is MetricId.FOLLOWERS
    }

    assert follower_values == {
        date(2026, 8, 1): 100,
        date(2026, 8, 2): 105,
        date(2026, 8, 3): 110,
        date(2026, 8, 4): 110,
        date(2026, 8, 5): 109,
    }


def test_snapshot_delta_does_not_infer_follower_flow_across_missing_days() -> None:
    catalog = bootstrap_metric_catalog()
    samples = tuple(
        ReportingMetric(
            account_id=7,
            brand_id="4",
            platform=PlatformId.FACEBOOK,
            observed_on=observed_on,
            metric_id=MetricId.FOLLOWERS,
            value=value,
        )
        for observed_on, value in (
            (date(2026, 8, 1), 100),
            (date(2026, 8, 3), 112),
        )
    )

    cards, _ = metric_cards(
        platform=PlatformId.FACEBOOK,
        account_ids=(7,),
        samples=samples,
        previous_samples=(),
        catalog=catalog,
    )
    by_id = {card.metric_id: card for card in cards}
    assert by_id[MetricId.FOLLOWS].value is None
    assert by_id[MetricId.UNFOLLOWS].value is None
    assert by_id[MetricId.FOLLOWERS_NET].value is None
    series = {
        item.metric_id: item
        for item in metric_series(
            platform=PlatformId.FACEBOOK,
            samples=samples,
            catalog=catalog,
        )
    }
    assert MetricId.FOLLOWS not in series


def test_tiktok_daily_fixture_crosses_reader_collection_and_dashboard_contract() -> None:
    fixture = {
        "code": 0,
        "message": "OK",
        "request_id": "daily-fixture",
        "data": {
            "metrics": [
                {
                    "date": "2026-08-01",
                    "followers_count": 100,
                    "video_views": 1000,
                    "unique_video_views": 800,
                    "profile_views": 30,
                    "likes": 20,
                    "comments": 4,
                    "shares": 2,
                },
                {
                    "date": "2026-08-02",
                    "followers_count": 106,
                    "video_views": 1200,
                    "unique_video_views": 900,
                    "profile_views": 40,
                    "likes": 25,
                    "comments": 5,
                    "shares": 3,
                },
            ]
        },
    }
    requested: list[tuple[str, date, date]] = []
    reader = TikTokDailyMetricsReader(
        lambda business_id, since, until: requested.append((business_id, since, until)) or fixture
    )
    account = ProviderAccount(
        platform=PlatformId.TIKTOK,
        account_id="business-1",
        credential=ProviderCredential(access_token="fixture-access-value"),
    )
    store = MemoryMetricStore()
    outcome = collect_daily_metrics(
        target=CollectionTarget(account=account, local_account_id=41, brand_id=9),
        reader=reader,
        metric_store=store,
        since=date(2026, 8, 1),
        until=date(2026, 8, 2),
    )

    assert requested == [("business-1", date(2026, 8, 1), date(2026, 8, 2))]
    assert outcome.status is CollectionStatus.SUCCESS
    assert outcome.metric_count == 16
    values = {(row.observed_on, row.metric_id): row.value for row in store.rows}
    assert values[(date(2026, 8, 2), MetricId.VIEWS)] == 1200
    assert values[(date(2026, 8, 2), MetricId.REACH)] == 900
    assert values[(date(2026, 8, 2), MetricId.PROFILE_VIEWS)] == 40
    assert values[(date(2026, 8, 2), MetricId.VIDEO_LIKES_DAILY)] == 25
    assert values[(date(2026, 8, 2), MetricId.VIDEO_COMMENTS_DAILY)] == 5
    assert values[(date(2026, 8, 2), MetricId.VIDEO_SHARES_DAILY)] == 3
    assert values[(date(2026, 8, 2), MetricId.INTERACTIONS)] == 33

    reporting = _reporting(store.rows)
    cards, _ = metric_cards(
        platform=PlatformId.TIKTOK,
        account_ids=(41,),
        samples=reporting,
        previous_samples=(),
        catalog=bootstrap_metric_catalog(),
    )
    by_id = {card.metric_id: card for card in cards}
    assert by_id[MetricId.FOLLOWS].value == 6
    assert by_id[MetricId.UNFOLLOWS].value == 0
    assert by_id[MetricId.FOLLOWERS_NET].value == 6
    assert by_id[MetricId.VIEWS].value == 2200
    assert by_id[MetricId.PROFILE_VIEWS].value == 70


def test_tiktok_daily_wire_requests_only_the_versioned_account_insight_contract() -> None:
    fields = TikTokAccountsWireMapper(_tiktok_config()).daily_metric_fields(
        business_id="business-1",
        since=date(2026, 8, 1),
        until=date(2026, 8, 30),
    )
    assert fields == {
        "business_id": "business-1",
        "fields": json.dumps(TIKTOK_DAILY_FIELDS, separators=(",", ":")),
        "start_date": "2026-08-01",
        "end_date": "2026-08-30",
    }
