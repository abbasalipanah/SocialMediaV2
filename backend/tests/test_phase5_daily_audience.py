from __future__ import annotations

import json
from datetime import UTC, date, datetime
from urllib.parse import parse_qs

import httpx

from app.application.ports.persistence import MetricPoint
from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.application.services.collection import (
    CollectionStatus,
    CollectionTarget,
    collect_audience,
)
from app.application.services.collection.daily_metrics import collect_daily_metrics
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta.audience import MetaAudienceReader
from app.infrastructure.providers.meta.facebook.daily_metrics import FacebookDailyMetricsReader
from app.infrastructure.providers.meta.instagram.daily_metrics import InstagramDailyMetricsReader
from app.infrastructure.providers.meta.rate_guard import MetaRateGuard
from app.infrastructure.providers.meta.transport import MetaTransport

NOW = datetime(2026, 7, 14, 13, tzinfo=UTC)
DAY = date(2026, 7, 13)


class MemoryMetricStore:
    def __init__(self) -> None:
        self.rows: list[MetricPoint] = []

    def upsert(self, point: MetricPoint) -> None:
        self.rows.append(point)

    def read(self, **kwargs: object) -> tuple[MetricPoint, ...]:
        return tuple(self.rows)

    def replace_breakdown(
        self,
        *,
        platform: PlatformId,
        account_id: int,
        brand_id: int,
        observed_on: date,
        metric_id: MetricId,
        breakdown_key: str,
        values: dict[str, float | int],
    ) -> None:
        self.rows = [
            row
            for row in self.rows
            if not (
                row.account_id == account_id
                and row.observed_on == observed_on
                and row.metric_id is metric_id
                and row.breakdown_key == breakdown_key
            )
        ]
        self.rows.extend(
            MetricPoint(
                platform=platform,
                account_id=account_id,
                brand_id=brand_id,
                observed_on=observed_on,
                metric_id=metric_id,
                value=value,
                breakdown_key=breakdown_key,
                breakdown_value=breakdown_value,
            )
            for breakdown_value, value in values.items()
        )


def _account(platform: PlatformId, account_id: str) -> ProviderAccount:
    return ProviderAccount(
        platform=platform,
        account_id=account_id,
        credential=ProviderCredential(access_token="fixture-access-value"),
    )


def _transport(handler) -> MetaTransport:
    return MetaTransport(
        credential=ProviderCredential(access_token="fixture-access-value"),
        rate_guard=MetaRateGuard(clock=lambda: NOW, sleeper=lambda _: None),
        wire=httpx.MockTransport(handler),
        egress_enabled=True,
        max_retries=0,
    )


def test_facebook_daily_metrics_preserve_request_order_and_d_plus_one() -> None:
    requests: list[dict[str, str]] = []
    values = {
        "page_media_view": 10,
        "page_posts_impressions": 20,
        "page_impressions_unique": 30,
        "page_posts_impressions_unique": 40,
        "page_views_total": 5,
        "page_post_engagements": 7,
        "page_actions_post_reactions_total": {"like": 2, "love": 3},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        query = {key: rows[-1] for key, rows in parse_qs(request.url.query.decode()).items()}
        requests.append(query)
        metric = query["metric"]
        if metric == "page_total_actions":
            return httpx.Response(
                400,
                json={"error": {"message": "unsupported fixture metric"}},
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "name": metric,
                        "values": [
                            {"value": values[metric], "end_time": "2026-07-15T00:00:00Z"}
                        ],
                    }
                ]
            },
            request=request,
        )

    account = _account(PlatformId.FACEBOOK, "page-1")
    store = MemoryMetricStore()
    outcome = collect_daily_metrics(
        target=CollectionTarget(account=account, local_account_id=11, brand_id=7),
        reader=FacebookDailyMetricsReader(_transport(handler)),
        metric_store=store,
        since=DAY,
        until=DAY,
    )
    by_metric = {row.metric_id: row.value for row in store.rows}
    assert outcome.status is CollectionStatus.SUCCESS
    assert by_metric == {
        MetricId.VIEWS: 10,
        MetricId.REACH: 30,
        MetricId.PAGE_VIEWS: 5,
        MetricId.INTERACTIONS: 7,
        MetricId.REACTIONS: 5,
    }
    assert [request["metric"] for request in requests] == [
        "page_media_view",
        "page_posts_impressions",
        "page_impressions_unique",
        "page_posts_impressions_unique",
        "page_views_total",
        "page_post_engagements",
        "page_total_actions",
        "page_actions_post_reactions_total",
    ]
    assert all(request["since"] == request["until"] == "2026-07-14" for request in requests)


def test_instagram_partial_daily_metrics_preserve_null_instead_of_zero() -> None:
    values = {
        MetricId.REACH.value: 80,
        MetricId.VIEWS.value: 150,
        MetricId.PROFILE_VIEWS.value: None,
        MetricId.WEBSITE_CLICKS.value: 6,
        "total_interactions": 24,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        query = parse_qs(request.url.query.decode())
        metric = query["metric"][-1]
        total_value = {} if values[metric] is None else {"value": values[metric]}
        return httpx.Response(
            200,
            json={"data": [{"name": metric, "total_value": total_value}]},
            request=request,
        )

    account = _account(PlatformId.INSTAGRAM, "ig-1")
    store = MemoryMetricStore()
    outcome = collect_daily_metrics(
        target=CollectionTarget(account=account, local_account_id=12, brand_id=7),
        reader=InstagramDailyMetricsReader(_transport(handler)),
        metric_store=store,
        since=DAY,
        until=DAY,
    )
    by_metric = {row.metric_id: row.value for row in store.rows}
    assert outcome.status is CollectionStatus.PARTIAL
    assert outcome.error_code == "metric_unavailable"
    assert MetricId.PROFILE_VIEWS not in by_metric
    assert by_metric[MetricId.REACH] == 80
    assert by_metric[MetricId.INTERACTIONS] == 24


def test_facebook_and_instagram_audience_breakdowns_are_normalized() -> None:
    fb_payload = {
        "data": [
            {
                "name": "page_fans_country",
                "values": [{"value": {"TR": 70, "DE": 20}}],
            }
        ]
    }
    fb = MetaAudienceReader(
        _transport(lambda request: httpx.Response(200, json=fb_payload, request=request)),
        platform=PlatformId.FACEBOOK,
        clock=lambda: NOW,
    ).fetch_audience(_account(PlatformId.FACEBOOK, "page-1"))
    assert fb.breakdowns["page_fans_country"] == {"TR": 70, "DE": 20}

    ig_payload = {
        "data": [
            {
                "name": "follower_demographics",
                "total_value": {
                    "breakdowns": [
                        {
                            "dimension_keys": ["country"],
                            "results": [
                                {"dimension_values": ["TR"], "value": 75},
                                {"dimension_values": ["DE"], "value": 15},
                            ],
                        }
                    ]
                },
            }
        ]
    }
    ig = MetaAudienceReader(
        _transport(lambda request: httpx.Response(200, json=ig_payload, request=request)),
        platform=PlatformId.INSTAGRAM,
        clock=lambda: NOW,
    ).fetch_audience(_account(PlatformId.INSTAGRAM, "ig-1"))
    assert ig.breakdowns["follower_demographics_country"] == {"TR": 75, "DE": 15}


def test_audience_collection_atomically_projects_only_provider_rows() -> None:
    payload = {
        "data": [
            {
                "name": "page_fans_country",
                "values": [{"value": {"TR": 70, "DE": 20}}],
            }
        ]
    }
    account = _account(PlatformId.FACEBOOK, "page-1")
    store = MemoryMetricStore()
    outcome = collect_audience(
        target=CollectionTarget(account=account, local_account_id=11, brand_id=7),
        reader=MetaAudienceReader(
            _transport(lambda request: httpx.Response(200, json=payload, request=request)),
            platform=PlatformId.FACEBOOK,
            clock=lambda: NOW,
        ),
        metric_store=store,
    )

    assert outcome.status is CollectionStatus.SUCCESS
    assert {(row.breakdown_value, row.value) for row in store.rows} == {
        ("TR", 70),
        ("DE", 20),
    }
    assert all(row.breakdown_key == "page_fans_country" for row in store.rows)


def test_malformed_audience_payload_fails_without_synthetic_breakdown() -> None:
    payload = {"data": [{"name": "page_fans_country", "values": [{"value": {"TR": "x"}}]}]}
    reader = MetaAudienceReader(
        _transport(lambda request: httpx.Response(200, json=payload, request=request)),
        platform=PlatformId.FACEBOOK,
    )
    try:
        reader.fetch_audience(_account(PlatformId.FACEBOOK, "page-1"))
    except ValueError as exc:
        assert str(exc) == "provider_audience_value_invalid"
    else:
        raise AssertionError(json.dumps(payload))
