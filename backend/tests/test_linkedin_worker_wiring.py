from __future__ import annotations

from types import SimpleNamespace

import app.workers.collector as collector_module
from app.domain.platforms import PlatformId
from app.infrastructure.persistence.social_v2.collection_targets import CollectionTargetRow
from app.workers.collector import StandaloneCollector


def test_standalone_collector_wires_verified_linkedin_access_to_runner(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    transport = object()
    provider = SimpleNamespace(platform=PlatformId.LINKEDIN)
    monkeypatch.setattr(
        collector_module,
        "LinkedInOAuthTransport",
        lambda **kwargs: calls.append(("oauth_transport", kwargs)) or transport,
    )
    monkeypatch.setattr(
        collector_module,
        "LinkedInOAuthProvider",
        lambda **kwargs: calls.append(("oauth_provider", kwargs)) or provider,
    )

    class AccessManager:
        def __init__(self, **kwargs) -> None:
            calls.append(("access_manager", kwargs))

        def resolve(self, **kwargs):
            calls.append(("resolve", kwargs))
            return SimpleNamespace(access_token="verified-access")

    monkeypatch.setattr(collector_module, "OAuthChannelAccessManager", AccessManager)
    monkeypatch.setattr(
        collector_module,
        "create_linkedin_readers",
        lambda **kwargs: calls.append(("readers", kwargs)) or "linkedin-readers",
    )
    monkeypatch.setattr(
        collector_module,
        "collect_linkedin_account",
        lambda **kwargs: (
            calls.append(("collect", kwargs))
            or SimpleNamespace(
                status="success",
                metric_count=8,
                content_count=3,
                media_count=0,
                error_code=None,
                backfill_complete=True,
            )
        ),
    )
    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector.settings = SimpleNamespace(
        linkedin=SimpleNamespace(
            oauth_app_id="client-id",
            oauth_app_secret="client-secret",
            token_url="https://www.linkedin.com/oauth/v2/accessToken",
            organization_acls_url="https://api.linkedin.com/rest/organizationAcls",
            organizations_url="https://api.linkedin.com/rest/organizations",
            api_version="202608",
            required_scopes=("rw_organization_admin", "r_organization_social"),
        ),
        linkedin_activation=SimpleNamespace(provider_timeout_seconds=5),
    )
    collector.credentials = object()
    collector.metrics = object()
    collector.content = object()
    collector.checkpoints = object()
    collector._persist_media = lambda _target, _item: 0
    timings: dict[str, float] = {}

    result = collector._collect_linkedin(
        CollectionTargetRow(
            link_id=91,
            connection_id=71,
            asset_id=81,
            brand_id=17,
            platform=PlatformId.LINKEDIN,
            external_id="1234",
            display_name="Example Company",
            credential_reference="a" * 64,
            backfill_status="pending",
        ),
        timings,
    )

    assert result.status == "success"
    assert result.metric_count == 8
    assert result.backfill_complete is True
    assert "linkedin" in timings
    assert [name for name, _value in calls] == [
        "oauth_transport",
        "oauth_provider",
        "access_manager",
        "resolve",
        "readers",
        "collect",
    ]
