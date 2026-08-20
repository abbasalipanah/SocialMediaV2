from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta.facebook.content import FacebookContentReader
from app.infrastructure.providers.meta.facebook.content_insights import POST_VIEW_METRIC
from app.infrastructure.providers.meta.transport import MetaPage, MetaTransportError


class _Transport:
    def __init__(self, *, insight_error: MetaTransportError | None = None) -> None:
        self.insight_error = insight_error
        self.insight_requests: list[tuple[str, object]] = []

    def page(self, path, params, *, cursor=None):
        assert path == "page-1/published_posts"
        assert cursor is None
        return MetaPage(
            items=(
                {
                    "id": "page-1_post-1",
                    "created_time": "2026-08-19T12:00:00+00:00",
                    "status_type": "added_photos",
                    "message": "Summer",
                    "reactions": {"summary": {"total_count": 7}},
                    "comments": {"summary": {"total_count": 2}},
                    "shares": {"count": 1},
                },
            ),
            next_cursor=None,
            payload={},
        )

    def get(self, path, params):
        self.insight_requests.append((path, params))
        if self.insight_error is not None:
            raise self.insight_error
        return {
            "data": [
                {
                    "name": POST_VIEW_METRIC,
                    "period": "lifetime",
                    "values": [{"value": 4248}],
                }
            ]
        }


def _account() -> ProviderAccount:
    return ProviderAccount(
        platform=PlatformId.FACEBOOK,
        account_id="page-1",
        credential=ProviderCredential(access_token="opaque"),
    )


def test_current_facebook_post_views_are_collected_from_insights() -> None:
    transport = _Transport()
    reader = FacebookContentReader(
        transport,  # type: ignore[arg-type]
        insights=True,
        clock=lambda: datetime(2026, 8, 20, tzinfo=UTC),
    )

    page = reader.list_content(_account())

    assert page.items[0].fields["views_count"] == 4248.0
    assert page.items[0].fields["reach_count"] is None
    assert transport.insight_requests == [
        ("page-1_post-1/insights", {"metric": POST_VIEW_METRIC})
    ]


def test_an_ineligible_post_does_not_empty_the_whole_page() -> None:
    transport = _Transport(
        insight_error=MetaTransportError("meta_provider_rejected", status_code=400)
    )
    reader = FacebookContentReader(transport, insights=True)  # type: ignore[arg-type]

    page = reader.list_content(_account())

    assert len(page.items) == 1
    assert page.items[0].fields["views_count"] is None


def test_a_provider_outage_is_not_recorded_as_missing_post_views() -> None:
    transport = _Transport(
        insight_error=MetaTransportError(
            "meta_transient_response", status_code=503, retryable=True
        )
    )
    reader = FacebookContentReader(transport, insights=True)  # type: ignore[arg-type]

    with pytest.raises(MetaTransportError):
        reader.list_content(_account())
