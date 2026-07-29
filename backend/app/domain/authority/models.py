"""Typed authority projections exposed to application services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AccessMode = Literal["read", "write"]
BrandVisibility = Literal["active", "hidden_parent"]


@dataclass(frozen=True)
class WorkspaceBrand:
    brand_id: str
    name: str | None
    parent_brand_id: str | None
    visibility: BrandVisibility
    access_mode: AccessMode | None
    role: str | None


@dataclass(frozen=True)
class BrandFamilyProjection:
    root_brand_id: str
    brand_ids: tuple[str, ...]


@dataclass(frozen=True)
class BrandScope:
    requested_brand_id: str
    rollup: bool
    resolved_brand_ids: tuple[str, ...]


@dataclass(frozen=True)
class BrandWorkspace:
    default_brand_id: str
    brands: tuple[WorkspaceBrand, ...]
    families: tuple[BrandFamilyProjection, ...]
    scope: BrandScope
