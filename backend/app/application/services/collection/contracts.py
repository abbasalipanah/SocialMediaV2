"""Collector target, status, and failure contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.application.ports.platforms import ProviderAccount
from app.infrastructure.providers.meta.rate_guard import MetaRateLimited
from app.infrastructure.providers.meta.transport import MetaTransportError


class CollectionStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    RATE_LIMITED = "rate_limited"
    TOKEN_INVALID = "token_invalid"
    OBJECT_INACCESSIBLE = "object_inaccessible"
    WORKER_INTERRUPTED = "worker_interrupted"
    FAILED = "failed"


@dataclass(frozen=True)
class CollectionTarget:
    account: ProviderAccount
    local_account_id: int
    brand_id: int

    def __post_init__(self) -> None:
        if self.local_account_id < 1 or self.brand_id < 1:
            raise ValueError("collection_target_invalid")


@dataclass(frozen=True)
class CollectionOutcome:
    status: CollectionStatus
    metric_count: int = 0
    content_count: int = 0
    comment_count: int = 0
    media_count: int = 0
    page_count: int = 0
    next_cursor: str | None = None
    error_code: str | None = None
    exit_code: int = 0


def classify_failure(exc: Exception) -> CollectionOutcome:
    if isinstance(exc, MetaRateLimited):
        return CollectionOutcome(
            status=CollectionStatus.RATE_LIMITED,
            error_code="rate_limited",
            exit_code=75,
        )
    if isinstance(exc, MetaTransportError):
        if exc.status_code == 401:
            return CollectionOutcome(
                status=CollectionStatus.TOKEN_INVALID,
                error_code="token_invalid",
                exit_code=1,
            )
        if exc.status_code in {403, 404}:
            return CollectionOutcome(
                status=CollectionStatus.OBJECT_INACCESSIBLE,
                error_code="object_inaccessible",
                exit_code=1,
            )
        return CollectionOutcome(
            status=CollectionStatus.FAILED,
            error_code=exc.code,
            exit_code=1,
        )
    return CollectionOutcome(
        status=CollectionStatus.FAILED,
        error_code="collection_failed",
        exit_code=1,
    )


__all__ = [
    "CollectionOutcome",
    "CollectionStatus",
    "CollectionTarget",
    "classify_failure",
]
