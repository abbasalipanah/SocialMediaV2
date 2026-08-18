"""Strict TikTok Business Accounts v1.3 response contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


class TikTokResponseError(ValueError):
    pass


@dataclass(frozen=True)
class TikTokTokenGrant:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    token_type: str
    expires_in: int
    refresh_expires_in: int
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class TikTokTokenInfo:
    business_id: str
    scopes: tuple[str, ...]


def parse_token(payload: Mapping[str, Any]) -> TikTokTokenGrant:
    data = success_data(payload)
    token_type = _text(data, "token_type")
    if token_type != "Bearer":
        raise TikTokResponseError("token_type_invalid")
    return TikTokTokenGrant(
        access_token=_text(data, "access_token"),
        refresh_token=_text(data, "refresh_token"),
        token_type=token_type,
        expires_in=_positive_int(data, "expires_in"),
        refresh_expires_in=_positive_int_alias(
            data, "refresh_token_expires_in", "refresh_expires_in"
        ),
        scopes=_scopes(data.get("scope")),
    )


def parse_token_info(payload: Mapping[str, Any]) -> TikTokTokenInfo:
    data = success_data(payload)
    return TikTokTokenInfo(
        # `tt_user/token_info/get/` returns the account identity as `creator_id`,
        # while `business/get/` takes the same opaque value as `business_id`.
        # One identifier, two provider-side names; V2 keeps the business name.
        business_id=_text(data, "creator_id"),
        scopes=_scopes(data.get("scope")),
    )


def parse_revoke(payload: Mapping[str, Any]) -> None:
    success_data(payload, allow_empty=True)


def success_data(
    payload: Mapping[str, Any], *, allow_empty: bool = False
) -> Mapping[str, Any]:
    code = payload.get("code")
    if isinstance(code, bool) or not isinstance(code, int):
        raise TikTokResponseError("response_code_invalid")
    if code != 0:
        # The numeric code is a stable, non-sensitive enum that distinguishes an
        # expired token from a malformed request. The message and body are still
        # withheld, because they can echo request content back.
        raise TikTokResponseError(f"provider_rejected:{code}")
    _text(payload, "message")
    _text(payload, "request_id")
    data = payload.get("data")
    if data is None and allow_empty:
        return {}
    if not isinstance(data, Mapping):
        raise TikTokResponseError("response_data_invalid")
    return data


def _text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        # Naming the field we expected is a contract detail, not provider data,
        # and it is what turns "the response was wrong" into an actionable fix.
        # The key names present are schema, never values, so contract drift is
        # visible without echoing any response content.
        present = ",".join(sorted(str(name) for name in payload)) or "none"
        raise TikTokResponseError(f"response_field_invalid:{key}:present={present}")
    return value


def _positive_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise TikTokResponseError("response_field_invalid")
    return value


def _positive_int_alias(payload: Mapping[str, Any], canonical: str, legacy: str) -> int:
    present = [key for key in (canonical, legacy) if key in payload]
    if len(present) != 1:
        raise TikTokResponseError("response_field_invalid")
    return _positive_int(payload, present[0])


def _scopes(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        scopes = tuple(scope.strip() for scope in value.split(",") if scope.strip())
    elif isinstance(value, list) and all(isinstance(scope, str) for scope in value):
        scopes = tuple(scope.strip() for scope in value if scope.strip())
    else:
        raise TikTokResponseError("scope_payload_invalid")
    if not scopes or len(scopes) != len(set(scopes)):
        raise TikTokResponseError("scope_payload_invalid")
    return scopes


__all__ = [
    "TikTokResponseError",
    "TikTokTokenGrant",
    "TikTokTokenInfo",
    "parse_revoke",
    "parse_token",
    "parse_token_info",
    "success_data",
]
