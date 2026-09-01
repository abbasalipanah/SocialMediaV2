"""Signed, bound, one-time TikTok OAuth state."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.application.ports.checkpoints import CheckpointKey, CheckpointStore
from app.core.config import TIKTOK_PROVIDER_PROFILE, TIKTOK_REDIRECT_URI
from app.core.time import utc_now
from app.domain.platforms import CapabilityId, PlatformId


class TikTokStateError(ValueError):
    pass


@dataclass(frozen=True)
class TikTokStateBinding:
    nonce: str
    intent_hash: str = field(repr=False)
    user_id: str
    brand_id: int
    session_binding: str = field(repr=False)
    expires_at: datetime
    provider_profile: str = TIKTOK_PROVIDER_PROFILE
    redirect_uri: str = TIKTOK_REDIRECT_URI

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", self.nonce):
            raise TikTokStateError("state_nonce_invalid")
        if not re.fullmatch(r"[a-f0-9]{64}", self.intent_hash):
            raise TikTokStateError("state_intent_invalid")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", self.user_id):
            raise TikTokStateError("state_user_invalid")
        if self.brand_id < 1 or not re.fullmatch(r"[a-f0-9]{64}", self.session_binding):
            raise TikTokStateError("state_binding_invalid")
        if self.expires_at.tzinfo is None:
            raise TikTokStateError("state_expiry_invalid")


class TikTokStateCodec:
    def __init__(
        self,
        *,
        secret: bytes,
        replay_store: CheckpointStore,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if len(secret) < 32:
            raise TikTokStateError("state_secret_invalid")
        self._secret = secret
        self._replay_store = replay_store
        self._clock = clock

    def issue(self, binding: TikTokStateBinding) -> str:
        if binding.expires_at <= self._clock():
            raise TikTokStateError("state_expiry_invalid")
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
    ) -> TikTokStateBinding:
        binding = self.inspect(token)
        if (
            binding.user_id != expected_user_id
            or binding.brand_id != expected_brand_id
            or not hmac.compare_digest(binding.session_binding, expected_session_binding)
        ):
            raise TikTokStateError("state_binding_mismatch")
        key = CheckpointKey(
            platform=PlatformId.TIKTOK,
            capability=CapabilityId.PROFILE,
            account_id=binding.nonce,
        )
        operation_id = hashlib.sha256(token.encode()).hexdigest()
        if not self._replay_store.claim_once(key, operation_id, binding.expires_at):
            raise TikTokStateError("state_replayed")
        return binding

    def inspect(self, token: str) -> TikTokStateBinding:
        """Verify signed callback state without consuming its one-time claim."""
        body, signature = _split(token)
        expected_signature = hmac.new(self._secret, body, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            raise TikTokStateError("state_signature_invalid")
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise TikTokStateError("state_payload_invalid") from exc
        binding = _binding(payload)
        if binding.expires_at <= self._clock():
            raise TikTokStateError("state_expired")
        if (
            binding.provider_profile != TIKTOK_PROVIDER_PROFILE
            or binding.redirect_uri != TIKTOK_REDIRECT_URI
        ):
            raise TikTokStateError("state_provider_mismatch")
        return binding


CALLBACK_FIELDS = frozenset({"code", "scopes", "state"})


def validate_callback(
    query: Mapping[str, str],
    *,
    actual_redirect_uri: str,
) -> tuple[str, str]:
    if actual_redirect_uri != TIKTOK_REDIRECT_URI:
        raise TikTokStateError("callback_uri_mismatch")
    # What TikTok actually sends back. The authorization runs through Login Kit,
    # which returns `code` alongside the scopes it granted; only the token
    # endpoint, on the Business API, calls the same value `auth_code`. Requiring
    # the callback to use that name meant every authorization was rejected on
    # arrival, before the code was ever exchanged.
    if set(query) != CALLBACK_FIELDS:
        raise TikTokStateError("callback_fields_invalid")
    auth_code = query.get("code", "")
    state = query.get("state", "")
    if not auth_code or not state:
        raise TikTokStateError("callback_fields_invalid")
    return auth_code, state


def _payload(binding: TikTokStateBinding) -> dict[str, Any]:
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


def _binding(payload: object) -> TikTokStateBinding:
    expected_keys = {
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
    if not isinstance(payload, Mapping) or set(payload) != expected_keys:
        raise TikTokStateError("state_payload_invalid")
    try:
        if payload["format_version"] != 1:
            raise ValueError
        return TikTokStateBinding(
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
        raise TikTokStateError("state_payload_invalid") from exc


def _split(token: str) -> tuple[bytes, bytes]:
    try:
        body_part, signature_part = token.split(".", 1)
        return _decode(body_part), _decode(signature_part)
    except (ValueError, UnicodeError) as exc:
        raise TikTokStateError("state_format_invalid") from exc


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


__all__ = [
    "TikTokStateBinding",
    "TikTokStateCodec",
    "TikTokStateError",
    "validate_callback",
]
