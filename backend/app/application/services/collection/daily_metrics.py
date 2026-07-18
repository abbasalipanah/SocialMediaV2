"""Daily account metric persistence."""

from __future__ import annotations

from datetime import date

from app.application.ports.persistence import MetricPoint, MetricStore
from app.application.ports.platforms.profile import DailyMetricsReader

from .contracts import CollectionOutcome, CollectionStatus, CollectionTarget


def collect_daily_metrics(
    *,
    target: CollectionTarget,
    reader: DailyMetricsReader,
    metric_store: MetricStore,
    since: date,
    until: date,
) -> CollectionOutcome:
    snapshots = reader.fetch_daily_metrics(target.account, since=since, until=until)
    metric_count = 0
    missing = 0
    for snapshot in snapshots:
        if snapshot.account_id != target.account.account_id:
            raise ValueError("provider_account_mismatch")
        for metric_id, value in snapshot.metric_values.items():
            if value is None:
                missing += 1
                continue
            metric_store.upsert(
                MetricPoint(
                    platform=target.account.platform,
                    account_id=target.local_account_id,
                    brand_id=target.brand_id,
                    observed_on=snapshot.observed_on,
                    metric_id=metric_id,
                    value=value,
                )
            )
            metric_count += 1
    return CollectionOutcome(
        status=CollectionStatus.PARTIAL if missing else CollectionStatus.SUCCESS,
        metric_count=metric_count,
        error_code="metric_unavailable" if missing else None,
    )


__all__ = ["collect_daily_metrics"]
