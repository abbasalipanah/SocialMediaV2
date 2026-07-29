"""Signed, Brand/session-bound and one-time Meta OAuth state."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.application.ports import (
    ActivationContext,
    ActivationStateClaims,
)
from app.application.ports.checkpoints import CheckpointKey, CheckpointStore
from app.core.config import META_REDIRECT_URI
from app.core.time import utc_now
from app.domain.platforms import CapabilityId, PlatformId

META_PROVIDER_PROFILE = "meta_graph_v23"


class MetaStateError(ValueError):
    pass


@dataclass(frozen=True)
class MetaStateBinding:
    nonce: str
    intent_hash: str = field(repr=False)
    user_id: str
    brand_id: int
    session_binding: str = field(repr=False)
    expires_at: datetime
    provider_profile: str = META_PROVIDER_PROFILE
    redirect_uri: str = META_REDIRECT_URI

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", self.nonce):
            raise MetaStateError("meta_state_nonce_invalid")
        if not re.fullmatch(r"[a-f0-9]{64}", self.intent_hash):
            raise MetaStateError("meta_state_intent_invalid")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", self.user_id):
            raise MetaStateError("meta_state_user_invalid")
        if self.brand_id < 1 or not re.fullmatch(r"[a-f0-9]{64}", self.session_binding):
            raise MetaStateError("meta_state_binding_invalid")
        if self.expires_at.tzinfo is None:
            raise MetaStateError("meta_state_expiry_invalid")


class MetaStateCodec:
    def __init__(
        self,
        *,
        secret: bytes,
        replay_store: CheckpointStore,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if len(secret) < 32:
            raise MetaStateError("meta_state_secret_invalid")
        self._secret = secret
        self._replay_store = replay_store
        self._clock = clock

    def issue(self, binding: MetaStateBinding) -> str:
        if binding.expires_at <= self._clock():
            raise MetaStateError("meta_state_expiry_invalid")
        body = _json_bytes(_payload(binding))
        signature = hmac.new(self._secret, body, hashlib.sha256).digest()
        return f"{_encode(body)}.{_encode(signature)}"

    def consume(
        self,
        token: str,
        *,
        expected_user_id: str,
        expected_brand_id: int,
        expected_session_binding: str,
    ) -> MetaStateBinding:
        body, signature = _split(token)
        expected_signature = hmac.new(self._secret, body, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            raise MetaStateError("meta_state_signature_invalid")
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise MetaStateError("meta_state_payload_invalid") from exc
        binding = _binding(payload)
        if binding.expires_at <= self._clock():
            raise MetaStateError("meta_state_expired")
        if (
            binding.provider_profile != META_PROVIDER_PROFILE
            or binding.redirect_uri != META_REDIRECT_URI
        ):
            raise MetaStateError("meta_state_provider_mismatch")
        if (
            binding.user_id != expected_user_id
            or binding.brand_id != expected_brand_id
            or not hmac.compare_digest(binding.session_binding, expected_session_binding)
        ):
            raise MetaStateError("meta_state_binding_mismatch")
        key = CheckpointKey(
            platform=PlatformId.FACEBOOK,
            capability=CapabilityId.PROFILE,
            account_id=binding.nonce,
        )
        operation_id = hashlib.sha256(token.encode()).hexdigest()
        if not self._replay_store.claim_once(key, operation_id, binding.expires_at):
            raise MetaStateError("meta_state_replayed")
        return binding


class MetaActivationStateAdapter:
    def __init__(self, codec: MetaStateCodec) -> None:
        self._codec = codec

    def issue(
        self,
        *,
        intent_hash: str,
        context: ActivationContext,
        expires_at: datetime,
    ) -> str:
        return self._codec.issue(
            MetaStateBinding(
                nonce=secrets.token_urlsafe(24),
                intent_hash=intent_hash,
                user_id=context.user_id,
                brand_id=context.brand_id,
                session_binding=context.session_binding,
                expires_at=expires_at,
            )
        )

    def consume(
        self,
        token: str,
        *,
        expected_context: ActivationContext,
    ) -> ActivationStateClaims:
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


def _payload(binding: MetaStateBinding) -> dict[str, Any]:
    return {
        "brand_id": binding.brand_id,
        "expires_at": binding.expires_at.astimezone(UTC).isoformat(),
        "format_version": 1,
        "intent_hash": binding.intent_hash,
        "nonce": binding.nonce,
        "provider_profile": binding.provider_profile,
        "redirect_uri": binding.redirect_uri,
        "session_binding": binding.session_binding,
        "user_id": binding.user_id,
    }


def _binding(payload: object) -> MetaStateBinding:
    expected = {
        "brand_id",
        "expires_at",
        "format_version",
        "intent_hash",
        "nonce",
        "provider_profile",
        "redirect_uri",
        "session_binding",
        "user_id",
    }
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise MetaStateError("meta_state_payload_invalid")
    try:
        if payload["format_version"] != 1:
            raise ValueError
        return MetaStateBinding(
            nonce=str(payload["nonce"]),
            intent_hash=str(payload["intent_hash"]),
            user_id=str(payload["user_id"]),
            brand_id=int(payload["brand_id"]),
            session_binding=str(payload["session_binding"]),
            expires_at=datetime.fromisoformat(str(payload["expires_at"])),
            provider_profile=str(payload["provider_profile"]),
            redirect_uri=str(payload["redirect_uri"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MetaStateError("meta_state_payload_invalid") from exc


def _split(token: str) -> tuple[bytes, bytes]:
    try:
        body_part, signature_part = token.split(".", 1)
        return _decode(body_part), _decode(signature_part)
    except (ValueError, UnicodeError) as exc:
        raise MetaStateError("meta_state_format_invalid") from exc


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


__all__ = [
    "META_PROVIDER_PROFILE",
    "MetaActivationStateAdapter",
    "MetaStateBinding",
    "MetaStateCodec",
    "MetaStateError",
]
