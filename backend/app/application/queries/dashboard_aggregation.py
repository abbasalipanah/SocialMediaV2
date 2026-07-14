"""Metric-catalog-aware dashboard aggregation helpers."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime

from app.application.ports.reporting import (
    ReportingAccount,
    ReportingComment,
    ReportingContent,
    ReportingMetric,
)
from app.domain.metrics import (
    AggregationPolicy,
    DerivationOperator,
    MetricCatalog,
    MetricDefinition,
    MetricId,
)
from app.domain.platforms import PlatformId
from app.domain.reporting import (
    CommunitySummary,
    DashboardBreakdown,
    DashboardBreakdownItem,
    DashboardContent,
    DashboardMetric,
    DashboardPoint,
    DashboardSeries,
    DataStatus,
    FreshnessStatus,
)


def aggregate_value(
    definition: MetricDefinition,
    samples: tuple[ReportingMetric, ...],
    catalog: MetricCatalog,
) -> float | None:
    direct = tuple(
        sample
        for sample in samples
        if sample.metric_id is definition.metric_id and sample.breakdown_key is None
    )
    if definition.semantic_type.value == "ratio":
        assert definition.numerator_metric_id is not None
        assert definition.denominator_metric_id is not None
        numerator = aggregate_value(
            catalog.get(definition.platform, definition.numerator_metric_id), samples, catalog
        )
        denominator = aggregate_value(
            catalog.get(definition.platform, definition.denominator_metric_id), samples, catalog
        )
        return None if numerator is None or not denominator else numerator / denominator
    if direct:
        if definition.period_aggregation is AggregationPolicy.SUM:
            return sum(sample.value for sample in direct)
        latest: dict[int, ReportingMetric] = {}
        for sample in direct:
            current = latest.get(sample.account_id)
            if current is None or sample.observed_on >= current.observed_on:
                latest[sample.account_id] = sample
        return sum(sample.value for sample in latest.values())
    if definition.derivation_operator is DerivationOperator.SUM_COMPONENTS:
        values = [
            aggregate_value(catalog.get(definition.platform, metric_id), samples, catalog)
            for metric_id in definition.derived_from_metric_ids
        ]
        return None if any(value is None for value in values) else sum(values)  # type: ignore[arg-type]
    if definition.derivation_operator is DerivationOperator.CUMULATIVE_DELTA:
        source_id = definition.derived_from_metric_ids[0]
        by_account: dict[int, list[ReportingMetric]] = defaultdict(list)
        for sample in samples:
            if sample.metric_id is source_id and sample.breakdown_key is None:
                by_account[sample.account_id].append(sample)
        deltas: list[float] = []
        for rows in by_account.values():
            ordered = sorted(rows, key=lambda row: row.observed_on)
            deltas.extend(
                current.value - previous.value
                for previous, current in zip(ordered, ordered[1:], strict=False)
                if current.value >= previous.value
            )
        return sum(deltas) if deltas else None
    return None


def metric_cards(
    *,
    platform: PlatformId,
    account_ids: tuple[int, ...],
    samples: tuple[ReportingMetric, ...],
    previous_samples: tuple[ReportingMetric, ...],
    catalog: MetricCatalog,
) -> tuple[tuple[DashboardMetric, ...], tuple[str, ...]]:
    cards: list[DashboardMetric] = []
    warnings: list[str] = []
    account_set = set(account_ids)
    for definition in catalog.definitions():
        if definition.platform is not platform:
            continue
        value = aggregate_value(definition, samples, catalog)
        previous = aggregate_value(definition, previous_samples, catalog)
        source_ids = set(definition.derived_from_metric_ids) or {definition.metric_id}
        covered = {
            sample.account_id
            for sample in samples
            if sample.metric_id in source_ids and sample.breakdown_key is None
        }
        if value is None:
            status = DataStatus.UNAVAILABLE
            warnings.append(f"metric_unavailable:{definition.metric_id.value}")
        elif covered and covered != account_set:
            status = DataStatus.PARTIAL
            warnings.append(f"partial_account_coverage:{definition.metric_id.value}")
        else:
            status = DataStatus.AVAILABLE
        delta = None
        if value is not None and previous not in {None, 0}:
            delta = (value - previous) / abs(previous) * 100
        cards.append(
            DashboardMetric(
                metric_id=definition.metric_id,
                value=value,
                previous_value=previous,
                delta_pct=delta,
                semantic_type=definition.semantic_type,
                unit=definition.unit,
                data_status=status,
            )
        )
    return tuple(cards), tuple(warnings)


def metric_series(
    *,
    platform: PlatformId,
    samples: tuple[ReportingMetric, ...],
    catalog: MetricCatalog,
) -> tuple[DashboardSeries, ...]:
    result: list[DashboardSeries] = []
    for definition in catalog.definitions():
        if definition.platform is not platform:
            continue
        by_day: dict[date, list[ReportingMetric]] = defaultdict(list)
        for sample in samples:
            if sample.metric_id is definition.metric_id and sample.breakdown_key is None:
                by_day[sample.observed_on].append(sample)
        points = tuple(
            DashboardPoint(
                observed_on=observed_on,
                value=sum(sample.value for sample in day_samples),
            )
            for observed_on, day_samples in sorted(by_day.items())
        )
        if points:
            result.append(
                DashboardSeries(
                    metric_id=definition.metric_id,
                    semantic_type=definition.semantic_type,
                    points=points,
                )
            )
    return tuple(result)


def metric_breakdowns(
    samples: tuple[ReportingMetric, ...],
) -> tuple[DashboardBreakdown, ...]:
    latest: dict[tuple[MetricId, str, str, int], ReportingMetric] = {}
    for sample in samples:
        if sample.breakdown_key is None or sample.breakdown_value is None:
            continue
        key = (
            sample.metric_id,
            sample.breakdown_key,
            sample.breakdown_value,
            sample.account_id,
        )
        current = latest.get(key)
        if current is None or sample.observed_on >= current.observed_on:
            latest[key] = sample
    grouped: dict[tuple[MetricId, str], dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    for (metric_id, dimension, value, _), sample in latest.items():
        grouped[(metric_id, dimension)][value] += sample.value
    return tuple(
        DashboardBreakdown(
            metric_id=metric_id,
            dimension=dimension,
            items=tuple(
                DashboardBreakdownItem(
                    key=key,
                    value=value,
                    percentage=(value / total * 100) if total else None,
                )
                for key, value in sorted(values.items(), key=lambda item: (-item[1], item[0]))
            ),
        )
        for (metric_id, dimension), values in sorted(
            grouped.items(), key=lambda item: (item[0][0].value, item[0][1])
        )
        if (total := sum(values.values())) >= 0
    )


def content_cards(rows: tuple[ReportingContent, ...]) -> tuple[DashboardContent, ...]:
    ordered = sorted(
        rows,
        key=lambda row: (
            row.published_at or datetime.min.replace(tzinfo=UTC),
            row.external_content_id,
        ),
        reverse=True,
    )
    return tuple(
        DashboardContent(
            account_id=row.account_id,
            external_content_id=row.external_content_id,
            content_type=row.content_type,
            permalink=row.permalink,
            message=row.message,
            media_url=row.media_url,
            published_at=row.published_at,
            likes_count=row.likes_count,
            comments_count=row.comments_count,
            shares_count=row.shares_count,
            interactions=row.likes_count + row.comments_count + row.shares_count,
        )
        for row in ordered[:50]
    )


def community_summary(
    rows: tuple[ReportingComment, ...], *, accounts_available: bool
) -> CommunitySummary:
    return CommunitySummary(
        total_comments=len(rows),
        answered_comments=sum(1 for row in rows if row.answered),
        unanswered_comments=sum(1 for row in rows if not row.answered),
        comment_likes=sum(row.like_count for row in rows),
        data_status=DataStatus.AVAILABLE if accounts_available else DataStatus.UNAVAILABLE,
    )


def freshness(
    accounts: tuple[ReportingAccount, ...], now: datetime
) -> tuple[datetime | None, FreshnessStatus]:
    observed = tuple(account.last_synced_at for account in accounts if account.last_synced_at)
    if not observed:
        return None, FreshnessStatus.NEVER_SYNCED
    latest = max(value.astimezone(UTC) for value in observed)
    lag_hours = max(0.0, (now.astimezone(UTC) - latest).total_seconds() / 3600)
    if lag_hours <= 24:
        return latest, FreshnessStatus.FRESH
    if lag_hours <= 72:
        return latest, FreshnessStatus.STALE
    return latest, FreshnessStatus.OUTDATED


__all__ = [
    "community_summary",
    "content_cards",
    "freshness",
    "metric_breakdowns",
    "metric_cards",
    "metric_series",
]
