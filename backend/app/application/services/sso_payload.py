"""Shared payload parsing helpers for SSO and webhook contracts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from ...domain.authority import PlatformAccount

Provider = Literal["accumulate"]
EventName = Literal["authorize", "brand_connected", "brand_revoked", "brand_updated"]


@dataclass(frozen=True)
class CallbackPayload:
    provider: Provider
    event: EventName
    state: str
    session_token: str
    account_bundle: list[PlatformAccount]


def _as_platform_account(item: dict[str, Any]) -> PlatformAccount:
    platform = str(item.get("platform", "")).lower()
    account_id = str(item["account_id"])
    display_name = str(item["display_name"])

    if platform not in {"facebook", "instagram", "tiktok"}:
        raise ValueError(f"Unsupported platform '{platform}'")

    return PlatformAccount(platform=platform, account_id=account_id, display_name=display_name)


def normalize_platform_accounts(
    raw_items: Iterable[dict[str, Any]] | None,
) -> list[PlatformAccount]:
    if raw_items is None:
        return []

    accounts: list[PlatformAccount] = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("platform account item must be object")
        accounts.append(_as_platform_account(item))
    return accounts


def parse_callback_payload(payload: dict[str, Any]) -> CallbackPayload:
    """Parse and validate a bootstrap callback payload."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be dict")

    provider = str(payload.get("provider", "")).strip().lower()
    event = str(payload.get("event", "")).strip().lower()
    state = str(payload.get("state", "")).strip()
    session_token = str(payload.get("session_token", "")).strip()
    account_bundle_raw = payload.get("account_bundle") or []

    if provider != "accumulate":
        raise ValueError("provider must be accumulate")
    if event != "authorize":
        raise ValueError("event must be authorize")
    if not state:
        raise ValueError("state is required")
    if not session_token:
        raise ValueError("session_token is required")

    if not isinstance(account_bundle_raw, list):
        raise ValueError("account_bundle must be list")

    return CallbackPayload(
        provider=provider,
        event=event,
        state=state,
        session_token=session_token,
        account_bundle=normalize_platform_accounts(account_bundle_raw),
    )
