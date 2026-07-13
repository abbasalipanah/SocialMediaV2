"""Provisioning projection port contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProvisioningSnapshot:
    brand_id: str
    parent_brand_id: str | None
    hidden_parent_brand_id: str | None
    payload: Mapping[str, Any]


class ProvisioningStore:
    """Port for Brand/Platform provisioning persistence."""

    def get(self, brand_id: str) -> ProvisioningSnapshot | None:
        raise NotImplementedError

    def put(self, snapshot: ProvisioningSnapshot) -> None:
        raise NotImplementedError
