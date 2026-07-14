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
        refresh_expires_in=_positive_int(data, "refresh_expires_in"),
        scopes=_scopes(data.get("scope")),
    )


def parse_token_info(payload: Mapping[str, Any]) -> TikTokTokenInfo:
    data = success_data(payload)
    return TikTokTokenInfo(
        business_id=_text(data, "business_id"),
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
        raise TikTokResponseError("provider_rejected")
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
        raise TikTokResponseError("response_field_invalid")
    return value


def _positive_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise TikTokResponseError("response_field_invalid")
    return value


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
