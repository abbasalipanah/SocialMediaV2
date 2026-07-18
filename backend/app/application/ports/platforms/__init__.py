"""Shared values for small platform capability ports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.platforms import PlatformId


@dataclass(frozen=True)
class ProviderCredential:
    access_token: str = field(repr=False)


@dataclass(frozen=True)
class ProviderAccount:
    platform: PlatformId
    account_id: str
    credential: ProviderCredential


@dataclass(frozen=True)
class ProviderRecord:
    external_id: str
    observed_at: datetime
    fields: dict[str, Any]


__all__ = ["ProviderAccount", "ProviderCredential", "ProviderRecord"]
