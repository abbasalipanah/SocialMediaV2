from __future__ import annotations

from types import SimpleNamespace

import app.workers.collector as collector_module
from app.domain.platforms import PlatformId
from app.infrastructure.persistence.social_v2.collection_targets import CollectionTargetRow
from app.workers.collector import StandaloneCollector


def test_standalone_collector_wires_verified_youtube_access_to_runner(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    transport = object()
    provider = SimpleNamespace(platform=PlatformId.YOUTUBE)

    monkeypatch.setattr(
        collector_module,
        "YouTubeOAuthTransport",
        lambda **kwargs: calls.append(("oauth_transport", kwargs)) or transport,
    )
    monkeypatch.setattr(
        collector_module,
        "YouTubeOAuthProvider",
        lambda **kwargs: calls.append(("oauth_provider", kwargs)) or provider,
    )

    class AccessManager:
        def __init__(self, **kwargs) -> None:
            calls.append(("access_manager", kwargs))

        def resolve(self, **kwargs):
            calls.append(("resolve", kwargs))
            return SimpleNamespace(access_token="verified-access")

    monkeypatch.setattr(collector_module, "OAuthChannelAccessManager", AccessManager)

    def readers(**kwargs):
        calls.append(("readers", kwargs))
        assert kwargs["account"].credential.access_token == "verified-access"
        return "youtube-readers"

    monkeypatch.setattr(collector_module, "create_youtube_readers", readers)

    def collect(**kwargs):
        calls.append(("collect", kwargs))
        assert kwargs["readers"] == "youtube-readers"
        assert kwargs["backfill_complete"] is False
        return SimpleNamespace(
            status="success",
            metric_count=4,
            content_count=2,
            comment_count=1,
            media_count=1,
            error_code=None,
            backfill_complete=True,
        )

    monkeypatch.setattr(collector_module, "collect_youtube_account", collect)

    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector.settings = SimpleNamespace(
        youtube=SimpleNamespace(
            token_url="https://oauth2.googleapis.com/token",
            revoke_url="https://oauth2.googleapis.com/revoke",
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
            channels_url="https://www.googleapis.com/youtube/v3/channels",
            required_scopes=("channel.read", "analytics.read"),
        ),
        youtube_activation=SimpleNamespace(provider_timeout_seconds=5),
    )
    collector.credentials = object()
    collector.metrics = object()
    collector.content = object()
    collector.comments = object()
    collector.checkpoints = object()
    collector._persist_media = lambda _target, _item: 0
    timings: dict[str, float] = {}

    result = collector._collect_youtube(
        CollectionTargetRow(
            link_id=91,
            connection_id=71,
            asset_id=81,
            brand_id=17,
            platform=PlatformId.YOUTUBE,
            external_id="UC-channel",
            display_name="Example Channel",
            credential_reference="a" * 64,
            backfill_status="pending",
        ),
        timings,
    )

    assert result.status == "success"
    assert result.metric_count == 4
    assert result.backfill_complete is True
    assert "youtube" in timings
    assert [name for name, _value in calls] == [
        "oauth_transport",
        "oauth_provider",
        "access_manager",
        "resolve",
        "readers",
        "collect",
    ]
