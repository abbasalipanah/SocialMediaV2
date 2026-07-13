"""Session persistence contract."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol


class SessionStore(Protocol):
    def create_from_jti(
        self,
        *,
        jti_hash: str,
        session_hash: str,
        payload: Mapping[str, Any],
        expires_at: datetime,
    ) -> bool: ...

    def get_session(self, session_hash: str) -> Mapping[str, Any] | None: ...

    def revoke_session(self, session_hash: str) -> None: ...

    def revoke_authority_sessions(self, *, user_id: str | None, brand_id: str | None) -> int: ...
