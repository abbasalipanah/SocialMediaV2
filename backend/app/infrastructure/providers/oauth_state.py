"""Signed, provider-bound, one-time OAuth state for channel integrations."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from collections.abc import Callable
from datetime import datetime
from urllib.parse import urlparse

from app.application.ports import ActivationContext, ActivationStateClaims
from app.application.ports.checkpoints import CheckpointKey, CheckpointStore
from app.core.time import utc_now
from app.domain.platforms import CapabilityId, PlatformId

from . import _oauth_platform
from .oauth_state_token import OAuthStateBinding, OAuthStateError, OAuthStateTokenCodec

_LOCAL_REDIRECT_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class OAuthStateCodec:
    def __init__(
        self,
        *,
        platform: PlatformId,
        provider_profile: str,
        redirect_uri: str,
        secret: bytes,
        replay_store: CheckpointStore,
        clock: Callable[[], datetime] = utc_now,
        compact: bool = False,
    ) -> None:
        _oauth_platform(platform)
        parsed = urlparse(redirect_uri)
        if (
            not re.fullmatch(r"[a-z0-9_]{3,64}", provider_profile)
            or parsed.scheme not in {"http", "https"}
            or (parsed.scheme == "http" and parsed.hostname not in _LOCAL_REDIRECT_HOSTS)
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
            or len(secret) < 32
        ):
            raise OAuthStateError("oauth_state_config_invalid")
        self._platform = platform
        self._provider_profile = provider_profile
        self._redirect_uri = redirect_uri
        self._secret = secret
        self._replay_store = replay_store
        self._clock = clock
        self._token_codec = OAuthStateTokenCodec(
            platform=platform,
            provider_profile=provider_profile,
            redirect_uri=redirect_uri,
            secret=secret,
            compact=compact,
        )

    def issue(self, binding: OAuthStateBinding) -> str:
        self._validate_binding(binding)
        if binding.expires_at <= self._clock():
            raise OAuthStateError("oauth_state_expiry_invalid")
        return self._token_codec.issue(binding)

    def inspect(self, token: str) -> OAuthStateBinding:
        binding = self._token_codec.inspect(token)
        self._validate_binding(binding)
        if binding.expires_at <= self._clock():
            raise OAuthStateError("oauth_state_expired")
        return binding

    def consume(
        self,
        token: str,
        *,
        expected_user_id: str,
        expected_brand_id: int,
        expected_session_binding: str,
    ) -> OAuthStateBinding:
        binding = self.inspect(token)
        if (
            not self._token_codec.user_matches(binding.user_id, expected_user_id)
            or binding.brand_id != expected_brand_id
            or not hmac.compare_digest(binding.session_binding, expected_session_binding)
        ):
            raise OAuthStateError("oauth_state_binding_mismatch")
        key = CheckpointKey(
            platform=self._platform,
            capability=CapabilityId.PROFILE,
            account_id=binding.nonce,
        )
        operation_id = hashlib.sha256(token.encode()).hexdigest()
        if not self._replay_store.claim_once(key, operation_id, binding.expires_at):
            raise OAuthStateError("oauth_state_replayed")
        return binding

    def _validate_binding(self, binding: OAuthStateBinding) -> None:
        if (
            not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", binding.nonce)
            or not re.fullmatch(r"[a-f0-9]{64}", binding.intent_hash)
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", binding.user_id)
            or binding.brand_id < 1
            or not re.fullmatch(r"[a-f0-9]{64}", binding.session_binding)
            or binding.expires_at.tzinfo is None
            or binding.platform is not self._platform
            or binding.provider_profile != self._provider_profile
            or binding.redirect_uri != self._redirect_uri
        ):
            raise OAuthStateError("oauth_state_binding_invalid")


class OAuthActivationStateAdapter:
    def __init__(self, codec: OAuthStateCodec) -> None:
        self._codec = codec

    def issue(
        self,
        *,
        intent_hash: str,
        context: ActivationContext,
        expires_at: datetime,
    ) -> str:
        return self._codec.issue(
            OAuthStateBinding(
                nonce=secrets.token_urlsafe(24),
                intent_hash=intent_hash,
                user_id=context.user_id,
                brand_id=context.brand_id,
                session_binding=context.session_binding,
                expires_at=expires_at,
                platform=self._codec._platform,
                provider_profile=self._codec._provider_profile,
                redirect_uri=self._codec._redirect_uri,
            )
        )

    def consume(self, token: str, *, expected_context: ActivationContext) -> ActivationStateClaims:
        binding = self._codec.consume(
            token,
            expected_user_id=expected_context.user_id,
            expected_brand_id=expected_context.brand_id,
            expected_session_binding=expected_context.session_binding,
        )
        return ActivationStateClaims(
            intent_hash=binding.intent_hash,
            context=expected_context,
            expires_at=binding.expires_at,
        )

    def verified_brand_id(self, token: str) -> int:
        return self._codec.inspect(token).brand_id
