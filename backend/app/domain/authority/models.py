"""Authority domain models for parent/child Brand projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Platform = Literal["facebook", "instagram", "tiktok"]


@dataclass(frozen=True)
class PlatformAccount:
    platform: Platform
    account_id: str
    display_name: str


@dataclass(frozen=True)
class BrandProjection:
    brand_id: str
    parent_brand_id: str | None
    hidden_parent_brand_id: str | None
    platform_accounts: list[PlatformAccount] = field(default_factory=list)


@dataclass(frozen=True)
class BrandFamilyProjection:
    root_brand_id: str
    brand_ids: tuple[str, ...]
