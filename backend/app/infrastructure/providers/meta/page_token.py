"""Resolve the Page access token a Facebook Page read requires.

Page-scoped edges — published posts and Page insights among them — are refused
when called with the connected user's token. The user token still answers the
Page profile, which is why a credential can look healthy while every content and
audience read is rejected.

The connected user token is kept as the final fallback: a user granted the Page
insight permissions may itself be accepted, and failing the read outright would
be worse than trying.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Protocol

logger = logging.getLogger(__name__)

MAX_ACCOUNT_PAGES = 100


class _Transport(Protocol):
    def get(
        self, path: str, params: Mapping[str, str | int | float] | None = None
    ) -> Mapping[str, Any]: ...


def resolve_page_access_token(
    transport: _Transport, *, page_id: str, fallback_token: str
) -> str:
    """The Page's own token, or the caller's token when it cannot be read."""
    if not page_id:
        return fallback_token

    try:
        profile = transport.get(page_id, {"fields": "id,access_token"})
    except Exception as exc:
        logger.warning(
            "facebook_page_token_lookup_failed page_id=%s reason=%s",
            page_id,
            exc,
        )
    else:
        token = str(profile.get("access_token") or "").strip()
        if token:
            return token

    try:
        accounts = transport.get(
            "me/accounts", {"fields": "id,access_token", "limit": MAX_ACCOUNT_PAGES}
        )
    except Exception as exc:
        logger.warning(
            "facebook_page_accounts_lookup_failed page_id=%s reason=%s",
            page_id,
            exc,
        )
        return fallback_token

    rows = accounts.get("data")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, Mapping) or str(row.get("id") or "") != str(page_id):
                continue
            token = str(row.get("access_token") or "").strip()
            if token:
                return token

    logger.warning("facebook_page_token_unavailable page_id=%s", page_id)
    return fallback_token
