"""Provisioning inbox and projection persistence contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class ProjectionWrite:
    projection_key: str
    payload: Mapping[str, Any]
    insert_only: bool = False


@dataclass(frozen=True)
class ProjectionReplacement:
    projection_key_prefix: str
    writes: tuple[ProjectionWrite, ...]
    version: int
    event_type: str


class ProvisioningStore(Protocol):
    def apply_event(
        self,
        *,
        nonce_hash: str,
        nonce_expires_at: datetime,
        event_id: str,
        event_type: str,
        entity_key: str,
        version: int,
        payload: Mapping[str, Any],
        projection_writes: tuple[ProjectionWrite, ...] = (),
        replacement: ProjectionReplacement | None = None,
    ) -> str: ...

    def get_projection(self, entity_key: str) -> Mapping[str, Any] | None: ...

    def list_projections(self, projection_key_prefix: str) -> list[Mapping[str, Any]]: ...
