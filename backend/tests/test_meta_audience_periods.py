"""Facebook follower geography is served on day/week, not lifetime.

Asking for the wrong period returned nothing, and the empty result was read as
the provider having withdrawn the data. It had not: the same account answers on
the day period, which is how V1's canary kept collecting it throughout.
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


def test_facebook_geography_is_read_from_the_day_period() -> None:
    transport = RecordingTransport(
        {
            ("page_fans_country", "day"): _row("page_fans_country", {"TR": 120, "DE": 30}),
            ("page_fans_city", "day"): _row("page_fans_city", {"Istanbul": 90}),
        }
    )

    snapshot = MetaAudienceReader(
        transport, platform=PlatformId.FACEBOOK, clock=lambda: NOW
    ).fetch_audience(_account())

    assert snapshot.breakdowns["page_fans_country"] == {"TR": 120, "DE": 30}
    assert snapshot.breakdowns["page_fans_city"] == {"Istanbul": 90}
    # Never asked for lifetime, and stopped as soon as a period answered.
    assert [period for _metric, period in transport.calls] == ["day", "day"]


def test_facebook_falls_back_to_the_week_period() -> None:
    transport = RecordingTransport(
        {("page_fans_country", "week"): _row("page_fans_country", {"TR": 7})}
    )

    snapshot = MetaAudienceReader(
        transport, platform=PlatformId.FACEBOOK, clock=lambda: NOW
    ).fetch_audience(_account())

    assert snapshot.breakdowns["page_fans_country"] == {"TR": 7}
    assert ("page_fans_country", "day") in transport.calls
    assert ("page_fans_country", "week") in transport.calls


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
