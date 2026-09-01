from __future__ import annotations

from types import SimpleNamespace

import app.workers.collector as collector_module
from app.domain.platforms import PlatformId
from app.infrastructure.persistence.social_v2.collection_targets import CollectionTargetRow
from app.workers.collector import StandaloneCollector


def test_standalone_collector_wires_verified_x_access_to_runner(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    transport = object()
    provider = SimpleNamespace(platform=PlatformId.X)
    monkeypatch.setattr(
        collector_module,
        "XOAuthTransport",
        lambda **kwargs: calls.append(("oauth_transport", kwargs)) or transport,
    )
    monkeypatch.setattr(
        collector_module,
        "XOAuthProvider",
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
        "create_x_readers",
        lambda **kwargs: calls.append(("readers", kwargs)) or "x-readers",
    )
    monkeypatch.setattr(
        collector_module,
        "collect_x_account",
        lambda **kwargs: calls.append(("collect", kwargs))
        or SimpleNamespace(
            status="success",
            metric_count=2,
            content_count=3,
            comment_count=4,
            media_count=1,
            error_code=None,
            backfill_complete=True,
        ),
    )
    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector.settings = SimpleNamespace(
        x=SimpleNamespace(
            oauth_app_id="client-id",
            oauth_app_secret="client-secret",
            token_url="https://api.x.com/2/oauth2/token",
            revoke_url="https://api.x.com/2/oauth2/revoke",
            users_me_url="https://api.x.com/2/users/me",
            required_scopes=("tweet.read", "users.read", "offline.access"),
        ),
        x_activation=SimpleNamespace(
            provider_timeout_seconds=5,
            oauth_state_secret="x" * 32,
        ),
    )
    collector.credentials = object()
    collector.metrics = object()
    collector.content = object()
    collector.comments = object()
    collector.checkpoints = object()
    collector._persist_media = lambda _target, _item: 0
    timings: dict[str, float] = {}

    result = collector._collect_x(
        CollectionTargetRow(
            link_id=91,
            connection_id=71,
            asset_id=81,
            brand_id=17,
            platform=PlatformId.X,
            external_id="123456789",
            display_name="Example (@example)",
            credential_reference="a" * 64,
            backfill_status="pending",
        ),
        timings,
    )

    assert result.status == "success"
    assert result.metric_count == 2
    assert result.comment_count == 4
    assert result.backfill_complete is True
    assert "x" in timings
    assert [name for name, _value in calls] == [
        "oauth_transport",
        "oauth_provider",
        "access_manager",
        "resolve",
        "readers",
        "collect",
    ]
