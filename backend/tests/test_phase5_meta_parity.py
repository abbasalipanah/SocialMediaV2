from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta.facebook.content import FacebookContentReader
from app.infrastructure.providers.meta.facebook.profile import FacebookProfileReader
from app.infrastructure.providers.meta.instagram.comments import InstagramCommentsReader
from app.infrastructure.providers.meta.instagram.content import InstagramContentReader
from app.infrastructure.providers.meta.instagram.profile import InstagramProfileReader
from app.infrastructure.providers.meta.rate_guard import MetaRateGuard
from app.infrastructure.providers.meta.transport import MetaTransport
from tests.parity.v2_transport_candidate import ForwardingTransport
from tests.phase5_fake_meta import FakeMetaServer, RecordedRequest

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
GOLDEN = Path(__file__).parent / "fixtures" / "phase5" / "meta_golden.json"
RETRY_GOLDEN = Path(__file__).parent / "fixtures" / "phase5" / "meta_retry_golden.json"
FIXED_NOW = datetime(2026, 7, 14, 13, tzinfo=UTC)


@pytest.fixture()
def fake_meta() -> Iterator[FakeMetaServer]:
    server = FakeMetaServer(GOLDEN)
    server.start()
    yield server
    server.close()


def _run(
    script: Path,
    server: FakeMetaServer,
    *,
    v1: bool = False,
    scenario: str | None = None,
) -> dict[str, object]:
    env = {
        **os.environ,
        "FAKE_META_ORIGIN": server.origin,
        "FIXTURE_PROVIDER_TOKEN": "fixture-token-not-secret",
    }
    if v1:
        env["V1_META_GRAPH_PATH"] = str(
            Path("/home/api/colab_scripts/Accumulate/backend/app/connectors/facebook/legacy/meta_graph.py")
        )
    if scenario:
        env["PARITY_SCENARIO"] = scenario
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def _normalized_requests(rows: list[RecordedRequest]) -> list[tuple[str, dict[str, str]]]:
    return [
        (
            row.path,
            {key: value for key, value in row.query.items() if key != "access_token"},
        )
        for row in rows
    ]


def test_v1_and_v2_transport_subprocesses_have_zero_behavior_difference() -> None:
    oracle_server = FakeMetaServer(GOLDEN)
    candidate_server = FakeMetaServer(GOLDEN)
    oracle_server.start()
    candidate_server.start()
    try:
        oracle = _run(
            Path(__file__).parent / "parity" / "v1_transport_oracle.py",
            oracle_server,
            v1=True,
        )
        candidate = _run(
            Path(__file__).parent / "parity" / "v2_transport_candidate.py",
            candidate_server,
        )
    finally:
        oracle_server.close()
        candidate_server.close()
    assert candidate == oracle == {
        "followers": 125,
        "content_ids": ["post-1", "post-2"],
    }
    assert _normalized_requests(candidate_server.requests) == _normalized_requests(
        oracle_server.requests
    )
    assert all(row.authorization_present for row in candidate_server.requests)
    assert all(not row.authorization_present for row in oracle_server.requests)


def test_v1_and_v2_retry_request_sequence_difference_is_zero() -> None:
    oracle_server = FakeMetaServer(RETRY_GOLDEN)
    candidate_server = FakeMetaServer(RETRY_GOLDEN)
    oracle_server.start()
    candidate_server.start()
    try:
        oracle = _run(
            Path(__file__).parent / "parity" / "v1_transport_oracle.py",
            oracle_server,
            v1=True,
            scenario="retry",
        )
        candidate = _run(
            Path(__file__).parent / "parity" / "v2_transport_candidate.py",
            candidate_server,
            scenario="retry",
        )
    finally:
        oracle_server.close()
        candidate_server.close()
    assert candidate == oracle == {"followers": 125}
    assert len(candidate_server.requests) == len(oracle_server.requests) == 3
    assert _normalized_requests(candidate_server.requests) == _normalized_requests(
        oracle_server.requests
    )


def _transport(server: FakeMetaServer) -> MetaTransport:
    return MetaTransport(
        credential=ProviderCredential(access_token="fixture-token-not-secret"),
        rate_guard=MetaRateGuard(sleeper=lambda _: None),
        wire=ForwardingTransport(server.origin),
        egress_enabled=True,
        max_retries=0,
    )


def test_facebook_and_instagram_golden_adapters(fake_meta: FakeMetaServer) -> None:
    transport = _transport(fake_meta)
    fb_account = ProviderAccount(
        platform=PlatformId.FACEBOOK,
        account_id="page-1",
        credential=ProviderCredential(access_token="fixture-token-not-secret"),
    )
    fb_profile = FacebookProfileReader(transport, clock=lambda: FIXED_NOW).fetch_profile(
        fb_account
    )
    fb_reader = FacebookContentReader(transport, clock=lambda: FIXED_NOW)
    fb_first = fb_reader.list_content(fb_account)
    fb_second = fb_reader.list_content(fb_account, cursor=fb_first.next_cursor)
    assert fb_profile.metric_values == {MetricId.FOLLOWERS: 125}
    assert [row.external_id for row in (*fb_first.items, *fb_second.items)] == [
        "post-1",
        "post-2",
    ]
    assert fb_first.items[0].fields["likes_count"] == 7

    ig_account = ProviderAccount(
        platform=PlatformId.INSTAGRAM,
        account_id="ig-1",
        credential=ProviderCredential(access_token="fixture-token-not-secret"),
    )
    ig_profile = InstagramProfileReader(transport, clock=lambda: FIXED_NOW).fetch_profile(
        ig_account
    )
    ig_content = InstagramContentReader(transport, clock=lambda: FIXED_NOW).list_content(
        ig_account
    )
    ig_stories = InstagramContentReader(
        transport,
        stories=True,
        clock=lambda: FIXED_NOW,
    ).list_content(ig_account)
    ig_comments = InstagramCommentsReader(
        transport,
        clock=lambda: FIXED_NOW,
    ).list_comments(ig_account, content_id="ig-post-1")
    assert ig_profile.metric_values == {MetricId.FOLLOWERS: 240}
    assert [row.external_id for row in ig_content.items] == ["ig-post-1"]
    assert [row.external_id for row in ig_stories.items] == ["story-1"]
    assert ig_stories.items[0].fields["media_url"].endswith("story-1.jpg")
    assert [row.external_id for row in ig_comments.items] == ["ig-comment-1"]
    assert ig_comments.items[0].fields["reply_count"] == 1
    transport.close()


def test_provider_family_mismatch_fails_before_request(fake_meta: FakeMetaServer) -> None:
    transport = _transport(fake_meta)
    wrong = ProviderAccount(
        platform=PlatformId.INSTAGRAM,
        account_id="page-1",
        credential=ProviderCredential(access_token="fixture-token-not-secret"),
    )
    with pytest.raises(ValueError, match="provider_family_mismatch"):
        FacebookProfileReader(transport).fetch_profile(wrong)
    assert fake_meta.requests == []
    transport.close()
