"""Provisioning inbox and projection persistence contract."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol


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
    ) -> str: ...

    def get_projection(self, entity_key: str) -> Mapping[str, Any] | None: ...
