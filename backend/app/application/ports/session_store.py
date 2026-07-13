"""Session projection port contracts for SSO/webhook phase."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    provider: str
    payload: Mapping[str, Any]
    created_at: datetime
    expires_at: datetime | None = None


class SessionStore:
    """Port for persistent session projection."""

    def get(self, session_id: str) -> SessionRecord | None:
        raise NotImplementedError

    def save(self, record: SessionRecord) -> None:
        raise NotImplementedError

    def delete(self, session_id: str) -> None:
        raise NotImplementedError
