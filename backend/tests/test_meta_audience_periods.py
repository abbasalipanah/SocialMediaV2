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

    def get(self, path, params=None):
        params = params or {}
        metric, period = params.get("metric", ""), params.get("period", "")
        self.calls.append((metric, period))
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
