"""Facebook follower geography survived Meta's rename of the metric.

Meta retired the `page_fans_*` family on 2025-11-15 and answers it with an
invalid-metric error, so the reader asks for the `page_follows_*` successors
instead. It stores them under the established keys: the measurement is the same
and the dashboards and history are keyed on the old names, so renaming the
stored key would split every Page's series in two.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta.audience import MetaAudienceReader

NOW = datetime(2026, 8, 18, 12, tzinfo=UTC)


class RecordingTransport:
    def __init__(self, answers):
        self._answers = answers
        self.calls: list[tuple[str, str]] = []
        self.parameters: list[dict[str, str]] = []

    def get(self, path, params=None):
        params = params or {}
        metric, period = params.get("metric", ""), params.get("period", "")
        self.calls.append((metric, period))
        self.parameters.append(dict(params))
        return self._answers.get((metric, period), {"data": []})


def _account():
    return ProviderAccount(
        platform=PlatformId.FACEBOOK,
        account_id="page-1",
        credential=ProviderCredential(access_token="opaque"),
    )


def _row(metric, values):
    return {"data": [{"name": metric, "values": [{"value": values}]}]}


def test_facebook_geography_is_requested_under_the_current_metric_names() -> None:
    transport = RecordingTransport(
        {
            ("page_follows_country", "day"): _row(
                "page_follows_country", {"TR": 120, "DE": 30}
            ),
            ("page_follows_city", "day"): _row("page_follows_city", {"Istanbul": 90}),
        }
    )

    MetaAudienceReader(
        transport, platform=PlatformId.FACEBOOK, clock=lambda: NOW
    ).fetch_audience(_account())

    # The retired names are never sent; sending them cost a refused round trip
    # per Page on every run.
    assert transport.calls == [
        ("page_follows_country", "day"),
        ("page_follows_city", "day"),
    ]


def test_renamed_metric_is_stored_under_the_established_key() -> None:
    transport = RecordingTransport(
        {
            ("page_follows_country", "day"): _row(
                "page_follows_country", {"TR": 120, "DE": 30}
            ),
            ("page_follows_city", "day"): _row("page_follows_city", {"Istanbul": 90}),
        }
    )

    snapshot = MetaAudienceReader(
        transport, platform=PlatformId.FACEBOOK, clock=lambda: NOW
    ).fetch_audience(_account())

    assert snapshot.breakdowns["page_fans_country"] == {"TR": 120, "DE": 30}
    assert snapshot.breakdowns["page_fans_city"] == {"Istanbul": 90}
    assert "page_follows_country" not in snapshot.breakdowns


def test_instagram_keeps_the_lifetime_period() -> None:
    transport = RecordingTransport({})

    MetaAudienceReader(
        transport, platform=PlatformId.INSTAGRAM, clock=lambda: NOW
    ).fetch_audience(
        ProviderAccount(
            platform=PlatformId.INSTAGRAM,
            account_id="ig-1",
            credential=ProviderCredential(access_token="opaque"),
        )
    )

    assert {period for _metric, period in transport.calls} == {"lifetime"}


def test_instagram_demographics_are_asked_for_one_breakdown_at_a_time() -> None:
    """Instagram refuses a demographic read that does not name its breakdown.

    Sending only metric and period returned `400:100` for all three metrics, so
    V2 had never written an audience row and the dashboards were still showing
    the snapshot imported from V1.
    """
    transport = RecordingTransport({})

    MetaAudienceReader(
        transport, platform=PlatformId.INSTAGRAM, clock=lambda: NOW
    ).fetch_audience(
        ProviderAccount(
            platform=PlatformId.INSTAGRAM,
            account_id="ig-1",
            credential=ProviderCredential(access_token="opaque"),
        )
    )

    assert transport.parameters, "no request was made"
    for params in transport.parameters:
        assert params["period"] == "lifetime"
        assert params["metric_type"] == "total_value"
        assert params["timeframe"] == (
            "last_90_days"
            if params["metric"] == "follower_demographics"
            # Meta withdrew the rolling timeframes from these two.
            else "this_month"
        )
        assert params["breakdown"] in {"country", "city", "age", "gender"}

    asked = {(p["metric"], p["breakdown"]) for p in transport.parameters}
    # Follower demographics carry the age and gender panels; the engaged and
    # reached metrics only ever fed the geography ones.
    assert ("follower_demographics", "age") in asked
    assert ("follower_demographics", "gender") in asked
    assert ("engaged_audience_demographics", "country") in asked
    assert ("reached_audience_demographics", "city") in asked
    assert ("engaged_audience_demographics", "age") not in asked


def test_instagram_breakdowns_are_stored_under_the_declared_contract_keys() -> None:
    payload = {
        "data": [
            {
                "name": "follower_demographics",
                "total_value": {
                    "breakdowns": [
                        {
                            "dimension_keys": ["country"],
                            "results": [
                                {"dimension_values": ["TR"], "value": 400},
                                {"dimension_values": ["DE"], "value": 25},
                            ],
                        }
                    ]
                },
            }
        ]
    }
    transport = RecordingTransport(
        {("follower_demographics", "lifetime"): payload}
    )

    snapshot = MetaAudienceReader(
        transport, platform=PlatformId.INSTAGRAM, clock=lambda: NOW
    ).fetch_audience(
        ProviderAccount(
            platform=PlatformId.INSTAGRAM,
            account_id="ig-1",
            credential=ProviderCredential(access_token="opaque"),
        )
    )

    # The frontend data matrix declares this exact key for the country panel.
    assert snapshot.breakdowns["follower_demographics_country"] == {
        "TR": 400,
        "DE": 25,
    }
