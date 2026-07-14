"""Explicit local model registry with no dynamic source-project loading."""

from __future__ import annotations

from sqlalchemy import MetaData, Table

from app.infrastructure.persistence.legacy_socialmedia.models import (
    REGISTERED_TABLES,
    metadata,
)


def registered_tables() -> tuple[Table, ...]:
    return REGISTERED_TABLES


def registered_metadata() -> MetaData:
    return metadata


__all__ = ["registered_metadata", "registered_tables"]
