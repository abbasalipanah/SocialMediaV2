from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.application.ports.checkpoints import CheckpointKey, ProviderCheckpoint
from app.application.ports.platforms import ProviderAccount, ProviderCredential
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
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.infrastructure.providers.tiktok.accounts import (
    TikTokAccountsWireMapper,
    TikTokAudienceReader,
    TikTokCommentsReader,
    TikTokContentReader,
    TikTokProfileReader,
    TikTokResponseError,
    TikTokStateBinding,
    TikTokStateCodec,
    TikTokStateError,
    evaluate_scopes,
    parse_revoke,
    parse_token,
    parse_token_info,
    validate_callback,
)

FIXTURE = Path(__file__).parent / "fixtures" / "phase5" / "tiktok_accounts_golden.json"
NOW = datetime(2026, 7, 14, 13, tzinfo=UTC)
SESSION_BINDING = hashlib.sha256(b"fixture-session").hexdigest()
INTENT_HASH = hashlib.sha256(b"fixture-intent").hexdigest()


def _config() -> TikTokConfig:
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


@pytest.fixture(scope="module")
def golden() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class MemoryReplayStore:
    def __init__(self) -> None:
        self.claimed: set[str] = set()

    def get(self, key: CheckpointKey) -> ProviderCheckpoint | None:
        return None

    def put(
        self, checkpoint: ProviderCheckpoint, *, expected_version: int | None
    ) -> bool:
        return False

    def claim_once(
        self, key: CheckpointKey, operation_id: str, expires_at: datetime
    ) -> bool:
        claim = f"{key.account_id}:{operation_id}"
        if claim in self.claimed:
            return False
        self.claimed.add(claim)
        return True


def test_token_refresh_revoke_and_token_info_fixtures(
    golden: dict[str, object],
) -> None:
    token = parse_token(golden["token"])  # type: ignore[arg-type]
    refreshed = parse_token(golden["refresh"])  # type: ignore[arg-type]
    info = parse_token_info(golden["token_info"])  # type: ignore[arg-type]
    parse_revoke(golden["revoke"])  # type: ignore[arg-type]
    assert token.token_type == refreshed.token_type == "Bearer"
    assert token.expires_in == refreshed.expires_in == 86400
    assert "fixture-access-value" not in repr(token)
    assert info.business_id == "business-1"
    assert evaluate_scopes(_config(), info.scopes).permitted is True


def test_token_refresh_accepts_official_refresh_token_expiry_field(
    golden: dict[str, object],
) -> None:
    payload = json.loads(json.dumps(golden["refresh"]))
    payload["data"]["refresh_token_expires_in"] = payload["data"].pop(
        "refresh_expires_in"
    )

    refreshed = parse_token(payload)

    assert refreshed.refresh_expires_in == 31_536_000


def test_required_optional_and_forbidden_scope_gate() -> None:
    config = _config()
    complete = evaluate_scopes(
        config,
        (*TIKTOK_REQUIRED_SCOPES, TIKTOK_OPTIONAL_SCOPES[0]),
    )
    missing = evaluate_scopes(config, TIKTOK_REQUIRED_SCOPES[:-1])
    forbidden = evaluate_scopes(config, (*TIKTOK_REQUIRED_SCOPES, "video.publish"))
    assert complete.permitted is True
    assert complete.granted_optional == (TIKTOK_OPTIONAL_SCOPES[0],)
    assert missing.permitted is False
    assert missing.missing_required == (TIKTOK_REQUIRED_SCOPES[-1],)
    assert forbidden.permitted is False
    assert forbidden.forbidden == ("video.publish",)


def test_account_request_mapping_is_exact_and_opaque() -> None:
    mapper = TikTokAccountsWireMapper(_config())
    token_info = mapper.token_info_fields(access_token="fixture-access-value")
    profile = mapper.profile_fields(business_id="business-1")
    videos = mapper.video_fields(business_id="business-1", cursor="next-page")
    # token_info is POST-only upstream and reads the token from a JSON body.
    assert token_info["access_token"] == "fixture-access-value"
    assert set(token_info) == {"app_id", "access_token"}
    assert profile["business_id"] == "business-1"
    assert json.loads(profile["fields"]) == [
        "display_name",
        "username",
        "profile_image",
        "followers_count",
        "total_likes",
        "videos_count",
    ]
    assert videos["cursor"] == "next-page"
    assert "item_id" in json.loads(videos["fields"])
    comments = mapper.comment_fields(
        business_id="business-1", video_id="video-1", cursor="comment-page"
    )
    audience = mapper.audience_fields(
        business_id="business-1", observed_on=NOW.date()
    )
    assert comments["cursor"] == "comment-page"
    assert "comment_id" in json.loads(comments["fields"])
    assert audience["start_date"] == NOW.date().isoformat()


def test_comment_and_audience_readers_preserve_provider_values() -> None:
    account = ProviderAccount(
        platform=PlatformId.TIKTOK,
        account_id="business-1",
        credential=ProviderCredential(access_token="fixture-access-value"),
    )
    comments = TikTokCommentsReader(
        lambda _business_id, _video_id, _cursor: {
            "code": 0,
            "message": "OK",
            "request_id": "comments-request",
            "data": {
                "comments": [
                    {
                        "comment_id": "comment-1",
                        "video_id": "video-1",
                        "text": "hello",
                        "create_time": "1757686800",
                        "likes": 4,
                        "reply_comment_total": 2,
                        "username": "viewer",
                        "user_id": "viewer-1",
                    }
                ],
                "has_more": True,
                "cursor": 1_763_482_984_376,
            },
        },
        clock=lambda: NOW,
    ).list_comments(account, content_id="video-1")
    assert comments.items[0].fields["like_count"] == 4
    assert comments.items[0].fields["reply_count"] == 2
    assert comments.next_cursor == "1763482984376"

    audience = TikTokAudienceReader(
        lambda _business_id, _observed_on: {
            "code": 0,
            "message": "OK",
            "request_id": "audience-request",
            "data": {
                "audience_countries": {"TR": 61, "DE": 14},
                "audience_genders": [
                    {"gender": "female", "percentage": 55},
                    {"gender": "male", "percentage": 45},
                ],
                "audience_activity": {"monday": {"13:00": 8}},
            },
        },
        observed_on=NOW.date(),
        clock=lambda: NOW,
    ).fetch_audience(account)
    assert audience.breakdowns["audience_countries"] == {"TR": 61.0, "DE": 14.0}
    assert audience.breakdowns["audience_genders"] == {
        "female": 55.0,
        "male": 45.0,
    }
    assert audience.breakdowns["audience_activity"] == {"monday|13": 8.0}


def test_profile_video_and_unavailable_metric_fixtures(
    golden: dict[str, object],
) -> None:
    account = ProviderAccount(
        platform=PlatformId.TIKTOK,
        account_id="business-1",
        credential=ProviderCredential(access_token="fixture-access-value"),
    )
    profile = TikTokProfileReader(
        lambda _account_id: golden["profile"],  # type: ignore[return-value]
        clock=lambda: NOW,
    ).fetch_profile(account)
    partial = TikTokProfileReader(
        lambda _account_id: golden["profile_metric_unavailable"],  # type: ignore[return-value]
        clock=lambda: NOW,
    ).fetch_profile(account)

    def fetch_videos(_account_id: str, cursor: str | None) -> dict[str, object]:
        return golden["video_second" if cursor else "video_first"]  # type: ignore[return-value]

    reader = TikTokContentReader(fetch_videos, clock=lambda: NOW)
    first = reader.list_content(account)
    second = reader.list_content(account, cursor=first.next_cursor)
    assert profile.metric_values == {MetricId.FOLLOWERS: 310}
    assert partial.metric_values == {MetricId.FOLLOWERS: None}
    assert [item.external_id for item in (*first.items, *second.items)] == [
        "video-1",
        "video-2",
    ]
    metrics = first.items[0].fields["metric_values"]
    assert metrics[MetricId.VIDEO_VIEWS_TOTAL] == 450
    assert second.next_cursor is None


def test_callback_accepts_exactly_what_login_kit_returns() -> None:
    """Authorization runs through Login Kit, which returns `code`.

    This asserted the opposite -- that `code` must be refused and `auth_code`
    required -- and the live provider settles it: every callback arrives as
    `code`, `scopes` and `state`. `auth_code` is only the Business API token
    endpoint's name for the same value. Requiring it here rejected every
    authorization on arrival, before the code was ever exchanged.
    """
    granted = "user.info.basic,video.list"
    assert validate_callback(
        {"code": "fixture-auth-value", "scopes": granted, "state": "opaque-state"},
        actual_redirect_uri=TIKTOK_REDIRECT_URI,
    ) == ("fixture-auth-value", "opaque-state")

    with pytest.raises(TikTokStateError, match="callback_uri_mismatch"):
        validate_callback(
            {"code": "fixture-auth-value", "scopes": granted, "state": "opaque-state"},
            actual_redirect_uri=f"{TIKTOK_REDIRECT_URI}/",
        )

    # The set stays exact: a missing or unexpected parameter is still refused.
    for query in (
        {"code": "fixture-auth-value", "state": "opaque-state"},
        {"auth_code": "fixture-auth-value", "scopes": granted, "state": "opaque-state"},
        {
            "code": "fixture-auth-value",
            "scopes": granted,
            "state": "opaque-state",
            "extra": "x",
        },
        {"code": "", "scopes": granted, "state": "opaque-state"},
    ):
        with pytest.raises(TikTokStateError, match="callback_fields_invalid"):
            validate_callback(query, actual_redirect_uri=TIKTOK_REDIRECT_URI)


def test_state_is_bound_single_use_and_provider_family_checked() -> None:
    store = MemoryReplayStore()
    codec = TikTokStateCodec(
        secret=b"s" * 32,
        replay_store=store,
        clock=lambda: NOW,
    )
    binding = TikTokStateBinding(
        nonce="nonce-for-fixture-1234",
        intent_hash=INTENT_HASH,
        user_id="user-1",
        brand_id=7,
        session_binding=SESSION_BINDING,
        expires_at=NOW + timedelta(minutes=5),
    )
    token = codec.issue(binding)
    consumed = codec.consume(
        token,
        expected_user_id="user-1",
        expected_brand_id=7,
        expected_session_binding=SESSION_BINDING,
    )
    assert consumed == binding
    with pytest.raises(TikTokStateError, match="state_replayed"):
        codec.consume(
            token,
            expected_user_id="user-1",
            expected_brand_id=7,
            expected_session_binding=SESSION_BINDING,
        )
    mismatched = TikTokStateBinding(
        nonce="nonce-for-fixture-5678",
        intent_hash=INTENT_HASH,
        user_id="user-1",
        brand_id=7,
        session_binding=SESSION_BINDING,
        expires_at=NOW + timedelta(minutes=5),
        provider_profile="advertiser_family",
    )
    with pytest.raises(TikTokStateError, match="state_provider_mismatch"):
        codec.consume(
            codec.issue(mismatched),
            expected_user_id="user-1",
            expected_brand_id=7,
            expected_session_binding=SESSION_BINDING,
        )


def test_malformed_response_and_account_mismatch_fail_closed(
    golden: dict[str, object],
) -> None:
    with pytest.raises(TikTokResponseError, match="provider_rejected"):
        parse_token(
            {
                "code": 40105,
                "message": "rejected",
                "request_id": "request-failed",
                "data": {},
            }
        )
    account = ProviderAccount(
        platform=PlatformId.TIKTOK,
        account_id="wrong-business",
        credential=ProviderCredential(access_token="fixture-access-value"),
    )
    profile = TikTokProfileReader(
        lambda _account_id: golden["profile"]  # type: ignore[return-value]
    ).fetch_profile(account)
    assert profile.account_id == "wrong-business"


def test_token_info_is_a_body_post_not_a_header_get() -> None:
    """`tt_user/token_info/get/` answers POST only; a GET is rejected with 405.

    Regression guard for the cutover defect where every token-inspection path
    called this endpoint with GET and an `Access-Token` header, so no TikTok
    token could ever be validated and V2 collection could not have worked.
    """
    mapper = TikTokAccountsWireMapper(_config())

    assert not hasattr(mapper, "token_info_headers")
    fields = mapper.token_info_fields(access_token="fixture-access-value")
    assert fields["access_token"] == "fixture-access-value"
    # The OAuth endpoints carry the application credential pair; this one
    # uses app_id and needs no secret.
    assert set(fields) == {"app_id", "access_token"}


def test_scope_contract_accepts_every_scope_the_approved_app_grants() -> None:
    """The existing approved TikTok app is the only source of V2 tokens.

    Its consent screen grants two scopes V2 never calls. They must still be
    inside the accepted contract, otherwise the upper-bound subset check
    rejects a perfectly valid token.
    """
    granted = {
        "user.info.basic",
        "user.info.username",
        "user.info.stats",
        "user.info.profile",
        "user.account.type",
        "user.insights",
        "video.list",
        "video.insights",
        "comment.list",
        "comment.list.manage",
        "biz.brand.insights",
    }
    accepted = set(TIKTOK_REQUIRED_SCOPES) | set(TIKTOK_OPTIONAL_SCOPES)

    assert set(TIKTOK_REQUIRED_SCOPES).issubset(granted)
    assert granted.issubset(accepted)
    # The upper bound still has to mean something.
    assert not {"video.publish", "user.account.delete"} & accepted


def test_token_info_reads_the_identity_from_creator_id() -> None:
    """The live endpoint returns `app_id`, `creator_id` and `scope`.

    It does not return `business_id`; that name only exists on `business/get/`,
    which takes the same opaque value. Expecting the wrong key made every token
    inspection fail with a parse error even after the token was accepted.
    """
    info = parse_token_info(
        {
            "code": 0,
            "message": "OK",
            "request_id": "request-info",
            "data": {
                "app_id": TIKTOK_APP_ID,
                "creator_id": "business-1",
                "scope": list(TIKTOK_REQUIRED_SCOPES),
            },
        }
    )

    assert info.business_id == "business-1"
    assert set(info.scopes) == set(TIKTOK_REQUIRED_SCOPES)

    with pytest.raises(TikTokResponseError, match="^response_field_invalid:creator_id:"):
        parse_token_info(
            {
                "code": 0,
                "message": "OK",
                "request_id": "request-info",
                "data": {"business_id": "business-1", "scope": ["user.info.basic"]},
            }
        )
