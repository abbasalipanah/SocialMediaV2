"""Bounded Facebook Page and linked Instagram Business account discovery."""

from __future__ import annotations

from collections.abc import Mapping

from app.application.ports import MetaActivationError, MetaProviderAccount
from app.domain.platforms import PlatformId

from .transport import MetaTransport

MAX_DISCOVERY_PAGES = 10


def discover_meta_accounts(graph: MetaTransport) -> tuple[MetaProviderAccount, ...]:
    discovered: dict[tuple[PlatformId, str], MetaProviderAccount] = {}
    cursor: str | None = None
    fields = "id,name,access_token,instagram_business_account{id,username,name}"
    for _ in range(MAX_DISCOVERY_PAGES):
        page = graph.page("me/accounts", {"fields": fields, "limit": 100}, cursor=cursor)
        for item in page.items:
            page_id = _required_identifier(item, "id")
            page_name = _required_text(item, "name")
            page_token = _required_text(item, "access_token")
            facebook = MetaProviderAccount(
                platform=PlatformId.FACEBOOK,
                external_id=page_id,
                display_name=page_name,
                access_token=page_token,
            )
            discovered[(facebook.platform, facebook.external_id)] = facebook
            instagram = item.get("instagram_business_account")
            if isinstance(instagram, Mapping):
                instagram_id = _required_identifier(instagram, "id")
                instagram_name = str(
                    instagram.get("username") or instagram.get("name") or instagram_id
                ).strip()
                profile = MetaProviderAccount(
                    platform=PlatformId.INSTAGRAM,
                    external_id=instagram_id,
                    display_name=instagram_name,
                    access_token=page_token,
                )
                discovered[(profile.platform, profile.external_id)] = profile
        cursor = page.next_cursor
        if not cursor:
            return tuple(discovered.values())
    raise MetaActivationError("meta_account_pagination_exceeded")


def _required_text(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > 4096:
        raise MetaActivationError("meta_oauth_response_invalid")
    return value.strip()


def _required_identifier(payload: Mapping[str, object], field: str) -> str:
    value = _required_text(payload, field)
    if not value.isdecimal() or len(value) > 64:
        raise MetaActivationError("meta_oauth_response_invalid")
    return value


__all__ = ["MAX_DISCOVERY_PAGES", "discover_meta_accounts"]
