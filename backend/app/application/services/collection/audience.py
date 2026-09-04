"""Atomic audience-breakdown collection without synthetic demographic rows."""

from __future__ import annotations

from app.application.ports.persistence import MetricStore
from app.application.ports.platforms.audience import AudienceReader

from .contracts import CollectionOutcome, CollectionStatus, CollectionTarget


def collect_audience(
    *,
    target: CollectionTarget,
    reader: AudienceReader,
    metric_store: MetricStore,
) -> CollectionOutcome:
    snapshot = reader.fetch_audience(target.account)
    if snapshot.account_id != target.account.account_id:
        raise ValueError("provider_account_mismatch")
    written = 0
    missing = 0
    for dimension, raw_values in snapshot.breakdowns.items():
        values = {key: value for key, value in raw_values.items() if value is not None}
        missing += sum(value is None for value in raw_values.values())
        metric_store.replace_breakdown(
            platform=target.account.platform,
            account_id=target.local_account_id,
            brand_id=target.brand_id,
            observed_on=snapshot.observed_at.date(),
            metric_id=snapshot.metric_id,
            breakdown_key=dimension,
            values=values,
        )
        written += len(values)
    return CollectionOutcome(
        status=(
            CollectionStatus.SUCCESS
            if written and not missing
            else CollectionStatus.PARTIAL
        ),
        metric_count=written,
        error_code=(
            None if written and not missing else "audience_partial_or_unavailable"
        ),
    )


__all__ = ["collect_audience"]
