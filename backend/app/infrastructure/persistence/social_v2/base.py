"""Shared safety boundary for V2 persistence adapters."""

from __future__ import annotations

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection

from app.core.write_policy import WritePolicy
from app.domain.platforms import PlatformId

from .platforms import normalize_platform


class SocialStoreBase:
    def __init__(self, engine: Engine, write_policy: WritePolicy) -> None:
        self.engine = engine
        self._write_policy = write_policy

    def _assert_mutation(self, command: str) -> None:
        self._write_policy.assert_allows_mutation(command)

    @staticmethod
    def _assert_account_scope(
        connection: Connection,
        *,
        account_id: int,
        platform: PlatformId,
        brand_id: int | None = None,
    ) -> None:
        row = connection.execute(
            text("SELECT brand_id, platform FROM assets WHERE id=:account_id"),
            {"account_id": account_id},
        ).mappings().one_or_none()
        if row is None:
            raise ValueError("account_scope_mismatch")
        stored_platform = normalize_platform(row["platform"])
        if stored_platform is not platform or (
            brand_id is not None and int(row["brand_id"]) != brand_id
        ):
            raise ValueError("account_scope_mismatch")


__all__ = ["SocialStoreBase"]
