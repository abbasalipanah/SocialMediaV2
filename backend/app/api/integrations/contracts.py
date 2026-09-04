"""Response contracts for self-service OAuth channel integrations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field

from app.core import RuntimeMode
from app.domain.platforms import PlatformId


@dataclass(frozen=True)
class OAuthChannelAccountItem:
    connection_id: int | None
    external_id: str
    display_name: str
    state: str


@dataclass(frozen=True)
class OAuthChannelReadinessResponse:
    brand_id: str
    platform: PlatformId
    can_manage: bool
    connection_state: str
    linked_account_count: int
    linked_accounts: tuple[OAuthChannelAccountItem, ...]
    available_accounts: tuple[OAuthChannelAccountItem, ...]
    oauth_start_available: bool
    reason: str
    runtime_mode: RuntimeMode
    writes_enabled: bool
    checked_at: datetime


@dataclass(frozen=True)
class OAuthChannelStartResponse:
    authorization_url: str
    expires_at: datetime


class OAuthChannelLinkPayload(BaseModel):
    connection_id: int = Field(gt=0)
    external_ids: list[str] = Field(min_length=1, max_length=50)


@dataclass(frozen=True)
class OAuthChannelLinkResponse:
    connection_id: int
    linked_count: int
    connection_state: str


@dataclass(frozen=True)
class OAuthChannelUnlinkResponse:
    brand_id: str
    platform: PlatformId
    external_id: str
    connection_state: str


__all__ = [
    "OAuthChannelAccountItem",
    "OAuthChannelLinkPayload",
    "OAuthChannelLinkResponse",
    "OAuthChannelReadinessResponse",
    "OAuthChannelStartResponse",
    "OAuthChannelUnlinkResponse",
]
