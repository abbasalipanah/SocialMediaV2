"""Signed token serialization for generic and provider-sized OAuth state."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.platforms import PlatformId


class OAuthStateError(ValueError):
    pass


@dataclass(frozen=True)
class OAuthStateBinding:
    nonce: str
    intent_hash: str = field(repr=False)
    user_id: str
    brand_id: int
    session_binding: str = field(repr=False)
    expires_at: datetime
    platform: PlatformId
    provider_profile: str
    redirect_uri: str


class OAuthStateTokenCodec:
    def __init__(
        self,
        *,
        platform: PlatformId,
        provider_profile: str,
        redirect_uri: str,
        secret: bytes,
        compact: bool,
    ) -> None:
        self._platform = platform
        self._provider_profile = provider_profile
        self._redirect_uri = redirect_uri
        self._secret = secret
        self._compact = compact

    def issue(self, binding: OAuthStateBinding) -> str:
        payload = _compact_payload(binding) if self._compact else _payload(binding)
        body = _json_bytes(payload)
        signature = hmac.new(
            self._secret,
            self._signature_input(body),
            hashlib.sha256,
        ).digest()
        return f"{_encode(body)}.{_encode(signature)}"

    def inspect(self, token: str) -> OAuthStateBinding:
        body, signature = _split(token)
        expected = hmac.new(
            self._secret,
            self._signature_input(body),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature, expected):
            raise OAuthStateError("oauth_state_signature_invalid")
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise OAuthStateError("oauth_state_payload_invalid") from exc
        if self._compact:
            return _compact_binding(
                payload,
                platform=self._platform,
                provider_profile=self._provider_profile,
                redirect_uri=self._redirect_uri,
            )
        return _binding(payload)

    def user_matches(self, binding_user_id: str, expected_user_id: str) -> bool:
        expected = _user_binding(expected_user_id) if self._compact else expected_user_id
        return hmac.compare_digest(binding_user_id, expected)

    def _signature_input(self, body: bytes) -> bytes:
        if not self._compact:
            return body
        return b"\0".join(
            (
                b"oauth-state-compact-v1",
                self._platform.value.encode(),
                self._provider_profile.encode(),
                self._redirect_uri.encode(),
                body,
            )
        )


def _payload(binding: OAuthStateBinding) -> dict[str, Any]:
    return {
        "brand_id": binding.brand_id,
        "expires_at": binding.expires_at.astimezone(UTC).isoformat(),
        "format_version": 1,
        "intent_hash": binding.intent_hash,
        "nonce": binding.nonce,
        "platform": binding.platform.value,
        "provider_profile": binding.provider_profile,
        "redirect_uri": binding.redirect_uri,
        "session_binding": binding.session_binding,
        "user_id": binding.user_id,
    }


def _compact_payload(binding: OAuthStateBinding) -> dict[str, Any]:
    return {
        "b": binding.brand_id,
        "e": binding.expires_at.astimezone(UTC).isoformat(),
        "i": binding.intent_hash,
        "n": binding.nonce,
        "s": binding.session_binding,
        "u": _user_binding(binding.user_id),
        "v": 1,
    }


def _compact_binding(
    payload: object,
    *,
    platform: PlatformId,
    provider_profile: str,
    redirect_uri: str,
) -> OAuthStateBinding:
    expected = {"b", "e", "i", "n", "s", "u", "v"}
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise OAuthStateError("oauth_state_payload_invalid")
    try:
        if payload["v"] != 1:
            raise ValueError
        return OAuthStateBinding(
            nonce=str(payload["n"]),
            intent_hash=str(payload["i"]),
            user_id=str(payload["u"]),
            brand_id=int(payload["b"]),
            session_binding=str(payload["s"]),
            expires_at=datetime.fromisoformat(str(payload["e"])),
            platform=platform,
            provider_profile=provider_profile,
            redirect_uri=redirect_uri,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OAuthStateError("oauth_state_payload_invalid") from exc


def _user_binding(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()


def _binding(payload: object) -> OAuthStateBinding:
    expected = {
        "brand_id",
        "expires_at",
        "format_version",
        "intent_hash",
        "nonce",
        "platform",
        "provider_profile",
        "redirect_uri",
        "session_binding",
        "user_id",
    }
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise OAuthStateError("oauth_state_payload_invalid")
    try:
        if payload["format_version"] != 1:
            raise ValueError
        return OAuthStateBinding(
            nonce=str(payload["nonce"]),
            intent_hash=str(payload["intent_hash"]),
            user_id=str(payload["user_id"]),
            brand_id=int(payload["brand_id"]),
            session_binding=str(payload["session_binding"]),
            expires_at=datetime.fromisoformat(str(payload["expires_at"])),
            platform=PlatformId(str(payload["platform"])),
            provider_profile=str(payload["provider_profile"]),
            redirect_uri=str(payload["redirect_uri"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OAuthStateError("oauth_state_payload_invalid") from exc


def _split(token: str) -> tuple[bytes, bytes]:
    try:
        body_part, signature_part = token.split(".", 1)
        body = _decode(body_part)
    except (ValueError, UnicodeError) as exc:
        raise OAuthStateError("oauth_state_format_invalid") from exc
    try:
        return body, _decode(signature_part)
    except (ValueError, UnicodeError) as exc:
        raise OAuthStateError("oauth_state_signature_invalid") from exc


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("base64url_invalid")
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if not hmac.compare_digest(_encode(decoded), value):
        raise ValueError("base64url_noncanonical")
    return decoded


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


__all__ = ["OAuthStateBinding", "OAuthStateError", "OAuthStateTokenCodec"]
