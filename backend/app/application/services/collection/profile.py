"""Profile snapshot collection."""

from __future__ import annotations

from app.application.ports.persistence import MetricPoint, MetricStore
from app.application.ports.platforms.profile import ProfileReader

from .contracts import CollectionOutcome, CollectionStatus, CollectionTarget


def collect_profile(
    *,
    target: CollectionTarget,
    reader: ProfileReader,
    metric_store: MetricStore,
) -> CollectionOutcome:
    snapshot = reader.fetch_profile(target.account)
    if snapshot.account_id != target.account.account_id:
        raise ValueError("provider_account_mismatch")
    metric_count = 0
    missing_count = 0
    for metric_id, value in snapshot.metric_values.items():
        if value is None:
            missing_count += 1
            continue
        metric_store.upsert(
            MetricPoint(
                platform=target.account.platform,
                account_id=target.local_account_id,
                brand_id=target.brand_id,
                observed_on=snapshot.observed_at.date(),
                metric_id=metric_id,
                value=value,
            )
        )
        metric_count += 1
    return CollectionOutcome(
        status=CollectionStatus.PARTIAL if missing_count else CollectionStatus.SUCCESS,
        metric_count=metric_count,
        error_code="metric_unavailable" if missing_count else None,
    )


__all__ = ["collect_profile"]
