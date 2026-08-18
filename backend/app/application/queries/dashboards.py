"""Small read-only dashboard query services."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.ports.reporting import ReportingStore
from app.application.queries.comment_privacy import redact_dashboard_comments
from app.application.queries.dashboard_aggregation import (
    audience_capabilities,
    community_summary,
    content_cards,
    content_summary,
    freshness,
    metric_breakdowns,
    metric_cards,
    metric_methodology,
    metric_series,
    source_breakdown,
    stories_contract,
    top_hashtags,
)
from app.application.queries.reporting_range import previous_reporting_range
from app.domain.metrics import MetricCatalog, MetricId
from app.domain.platforms import PlatformId
from app.domain.reporting import (
    CommunitySummary,
    DashboardMeta,
    DashboardMetric,
    DashboardTopCommenter,
    DashboardTopLikedComment,
    DataStatus,
    FreshnessStatus,
    OverviewDashboard,
    PlatformDashboard,
    ReportingRange,
)

OVERVIEW_METRIC_IDS = (
    MetricId.FOLLOWERS,
    MetricId.NEW_FOLLOWERS,
    MetricId.REACH,
    MetricId.VIEWS,
    MetricId.INTERACTIONS,
    MetricId.WEBSITE_CLICKS,
    MetricId.REACTIONS,
)


@dataclass(frozen=True)
class DashboardQuery:
    requested_brand_id: str
    resolved_brand_ids: tuple[str, ...]
    rollup: bool
    date_range: ReportingRange
    account_id: int | None = None
    content_type: str | None = None
    excluded_content_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.requested_brand_id or not self.resolved_brand_ids:
            raise ValueError("dashboard_scope_invalid")
        if self.account_id is not None and self.account_id < 1:
            raise ValueError("dashboard_account_invalid")
        if self.content_type is not None and (
            not self.content_type.replace("_", "").replace("-", "").isalnum()
            or len(self.content_type) > 32
        ):
            raise ValueError("dashboard_content_type_invalid")
        if any(
            not value
            or not value.replace("_", "").replace("-", "").isalnum()
            or len(value) > 32
            for value in self.excluded_content_types
        ):
            raise ValueError("dashboard_content_type_invalid")
        if len(set(self.excluded_content_types)) != len(self.excluded_content_types):
            raise ValueError("dashboard_content_type_invalid")
        if self.content_type in self.excluded_content_types:
            raise ValueError("dashboard_content_scope_invalid")


def _exclude_content_types(rows, excluded: tuple[str, ...]):
    if not excluded:
        return rows
    normalized = {value.strip().lower() for value in excluded}
    return tuple(row for row in rows if row.content_type.strip().lower() not in normalized)


def platform_warnings(
    *,
    has_accounts: bool,
    metric_warnings: Sequence[str],
    freshness_status: FreshnessStatus,
) -> list[str]:
    """Warnings for one platform card.

    A platform the Brand never connected reports exactly that. Every per-metric
    and freshness warning would restate the same single fact, which buried the
    real signal under a wall of noise.
    """
    if not has_accounts:
        return ["no_accounts"]
    warnings = list(metric_warnings)
    if freshness_status is not FreshnessStatus.FRESH:
        warnings.append(f"freshness:{freshness_status.value}")
    return warnings


def _build_platform_dashboard(
    *,
    store: ReportingStore,
    catalog: MetricCatalog,
    platform: PlatformId,
    query: DashboardQuery,
    now: datetime | None = None,
) -> PlatformDashboard:
    generated = (now or datetime.now(UTC)).astimezone(UTC)
    accounts = store.list_accounts(brand_ids=query.resolved_brand_ids, platform=platform)
    if query.account_id is not None:
        accounts = tuple(account for account in accounts if account.account_id == query.account_id)
        if not accounts:
            raise ValueError("dashboard_account_scope_denied")
    account_ids = tuple(account.account_id for account in accounts)
    previous_range = previous_reporting_range(query.date_range)
    current_window_samples = (
        store.list_metrics(
            account_ids=account_ids,
            start_on=query.date_range.start_on - timedelta(days=1),
            end_on=query.date_range.end_on,
        )
        if account_ids
        else ()
    )
    previous_window_samples = (
        store.list_metrics(
            account_ids=account_ids,
            start_on=previous_range.start_on - timedelta(days=1),
            end_on=previous_range.end_on,
        )
        if account_ids
        else ()
    )
    samples = tuple(
        sample
        for sample in current_window_samples
        if sample.observed_on >= query.date_range.start_on
    )
    previous_samples = tuple(
        sample
        for sample in previous_window_samples
        if sample.observed_on >= previous_range.start_on
    )
    content_rows = _exclude_content_types(
        store.list_content(
            account_ids=account_ids,
            start_on=query.date_range.start_on,
            end_on=query.date_range.end_on,
            content_type=query.content_type,
        )
        if account_ids
        else (),
        query.excluded_content_types,
    )
    previous_content_rows = _exclude_content_types(
        store.list_content(
            account_ids=account_ids,
            start_on=previous_range.start_on,
            end_on=previous_range.end_on,
            content_type=query.content_type,
        )
        if account_ids
        else (),
        query.excluded_content_types,
    )
    comment_rows = (
        store.list_comments(
            account_ids=account_ids,
            start_on=query.date_range.start_on,
            end_on=query.date_range.end_on,
        )
        if account_ids
        else ()
    )
    cards, metric_warnings = metric_cards(
        platform=platform,
        account_ids=account_ids,
        samples=samples,
        previous_samples=previous_samples,
        catalog=catalog,
        derivation_samples=current_window_samples,
        previous_derivation_samples=previous_window_samples,
    )
    available = sum(card.data_status is not DataStatus.UNAVAILABLE for card in cards)
    if not accounts or not available:
        status = DataStatus.UNAVAILABLE
    elif any(card.data_status is not DataStatus.AVAILABLE for card in cards):
        status = DataStatus.PARTIAL
    else:
        status = DataStatus.AVAILABLE
    last_sync, freshness_status = freshness(accounts, generated)
    warnings = platform_warnings(
        has_accounts=bool(accounts),
        metric_warnings=metric_warnings,
        freshness_status=freshness_status,
    )
    observed_days = len({sample.observed_on for sample in samples})
    expected_days = (query.date_range.end_on - query.date_range.start_on).days + 1
    breakdowns = metric_breakdowns(samples)
    return PlatformDashboard(
        meta=DashboardMeta(
            dashboard_id=platform.value,
            platform=platform,
            requested_brand_id=query.requested_brand_id,
            rollup=query.rollup,
            resolved_brand_ids=query.resolved_brand_ids,
            resolved_account_ids=account_ids,
            date_range=query.date_range,
            generated_at=generated,
            last_sync_at=last_sync,
            freshness=freshness_status,
            observed_days=observed_days,
            expected_days=expected_days,
            data_status=status,
            warnings=tuple(warnings),
        ),
        metrics=cards,
        series=metric_series(
            platform=platform,
            samples=samples,
            catalog=catalog,
            derivation_samples=current_window_samples,
        ),
        breakdowns=breakdowns,
        content=content_cards(content_rows),
        community=community_summary(comment_rows, accounts_available=bool(accounts)),
        top_hashtags=top_hashtags(content_rows),
        content_summary=content_summary(
            content_rows,
            breakdowns,
            accounts_available=bool(accounts),
        ),
        source_breakdown=source_breakdown(breakdowns),
        metric_methodology=metric_methodology(platform, catalog),
        audience_capabilities=audience_capabilities(
            platform,
            breakdowns,
            accounts_available=bool(accounts),
        ),
        stories=stories_contract(
            platform=platform,
            rows=content_rows,
            previous_rows=previous_content_rows,
            breakdowns=breakdowns,
            date_range=query.date_range,
        ),
    )


def build_platform_dashboard(
    *,
    store: ReportingStore,
    catalog: MetricCatalog,
    platform: PlatformId,
    query: DashboardQuery,
    now: datetime | None = None,
) -> PlatformDashboard:
    dashboard = _build_platform_dashboard(
        store=store,
        catalog=catalog,
        platform=platform,
        query=query,
        now=now,
    )
    redacted = redact_dashboard_comments(dashboard)
    assert isinstance(redacted, PlatformDashboard)
    return redacted


def build_overview_dashboard(
    *,
    store: ReportingStore,
    catalog: MetricCatalog,
    query: DashboardQuery,
    now: datetime | None = None,
) -> OverviewDashboard:
    generated = (now or datetime.now(UTC)).astimezone(UTC)
    dashboards = tuple(
        _build_platform_dashboard(
            store=store,
            catalog=catalog,
            platform=platform,
            query=query,
            now=generated,
        )
        for platform in PlatformId
    )
    metrics = tuple(
        result
        for metric_id in OVERVIEW_METRIC_IDS
        if (result := _overview_metric(metric_id, dashboards)) is not None
    )
    all_content = tuple(
        sorted(
            (item for dashboard in dashboards for item in dashboard.content),
            key=lambda item: (
                item.published_at or datetime.min.replace(tzinfo=UTC),
                item.external_content_id,
            ),
            reverse=True,
        )[:50]
    )
    communities = tuple(dashboard.community for dashboard in dashboards)
    commenter_totals: dict[str, tuple[int, int]] = {}
    for community in communities:
        for item in community.top_commenters:
            comments, likes = commenter_totals.get(item.name, (0, 0))
            commenter_totals[item.name] = (comments + item.comments, likes + item.likes)
    account_ids = tuple(
        sorted({value for dashboard in dashboards for value in dashboard.meta.resolved_account_ids})
    )
    statuses = {dashboard.meta.data_status for dashboard in dashboards}
    if statuses == {DataStatus.UNAVAILABLE}:
        data_status = DataStatus.UNAVAILABLE
    elif statuses == {DataStatus.AVAILABLE}:
        data_status = DataStatus.AVAILABLE
    else:
        data_status = DataStatus.PARTIAL
    last_sync_values = tuple(
        dashboard.meta.last_sync_at
        for dashboard in dashboards
        if dashboard.meta.last_sync_at is not None
    )
    freshness_status = _overview_freshness(dashboards)
    warnings = tuple(
        f"{dashboard.meta.dashboard_id}:{warning}"
        for dashboard in dashboards
        for warning in dashboard.meta.warnings
    )
    expected_days = (query.date_range.end_on - query.date_range.start_on).days + 1
    dashboard = OverviewDashboard(
        meta=DashboardMeta(
            dashboard_id="overview",
            platform=None,
            requested_brand_id=query.requested_brand_id,
            rollup=query.rollup,
            resolved_brand_ids=query.resolved_brand_ids,
            resolved_account_ids=account_ids,
            date_range=query.date_range,
            generated_at=generated,
            last_sync_at=max(last_sync_values) if last_sync_values else None,
            freshness=freshness_status,
            observed_days=max((item.meta.observed_days for item in dashboards), default=0),
            expected_days=expected_days,
            data_status=data_status,
            warnings=warnings,
        ),
        metrics=metrics,
        platforms=dashboards,
        content=all_content,
        community=CommunitySummary(
            total_comments=sum(item.total_comments for item in communities),
            answered_comments=sum(item.answered_comments for item in communities),
            unanswered_comments=sum(item.unanswered_comments for item in communities),
            comment_likes=sum(item.comment_likes for item in communities),
            data_status=data_status,
            top_commenters=tuple(
                DashboardTopCommenter(name=name, comments=comments, likes=likes)
                for name, (comments, likes) in sorted(
                    commenter_totals.items(),
                    key=lambda item: (-item[1][0], -item[1][1], item[0].lower()),
                )[:8]
            ),
            top_liked_comments=tuple(
                sorted(
                    (
                        DashboardTopLikedComment(
                            name=item.name,
                            comment=item.comment,
                            likes=item.likes,
                            replies=item.replies,
                        )
                        for community in communities
                        for item in community.top_liked_comments
                    ),
                    key=lambda item: (-item.likes, item.comment),
                )[:8]
            ),
        ),
    )
    redacted = redact_dashboard_comments(dashboard)
    assert isinstance(redacted, OverviewDashboard)
    return redacted


def _overview_metric(
    metric_id: MetricId, dashboards: tuple[PlatformDashboard, ...]
) -> DashboardMetric | None:
    cards = tuple(
        card
        for dashboard in dashboards
        for card in dashboard.metrics
        if card.metric_id is metric_id
    )
    if not cards:
        return None
    values = tuple(card.value for card in cards if card.value is not None)
    previous_values = tuple(
        card.previous_value for card in cards if card.previous_value is not None
    )
    value = sum(values) if values else None
    previous = sum(previous_values) if previous_values else None
    delta = None
    if value is not None and previous is not None and previous != 0:
        delta = (value - previous) / abs(previous) * 100
    if not values:
        status = DataStatus.UNAVAILABLE
    elif any(card.data_status is not DataStatus.AVAILABLE for card in cards):
        status = DataStatus.PARTIAL
    else:
        status = DataStatus.AVAILABLE
    first = cards[0]
    return DashboardMetric(
        metric_id=metric_id,
        value=value,
        previous_value=previous,
        delta_pct=delta,
        semantic_type=first.semantic_type,
        unit=first.unit,
        data_status=status,
        methodology=first.methodology,
        availability_reason=(
            "overview_metric_unavailable"
            if status is DataStatus.UNAVAILABLE
            else "overview_platform_coverage_partial"
            if status is DataStatus.PARTIAL
            else None
        ),
    )


def _overview_freshness(
    dashboards: tuple[PlatformDashboard, ...],
) -> FreshnessStatus:
    rank = {
        FreshnessStatus.FRESH: 0,
        FreshnessStatus.STALE: 1,
        FreshnessStatus.OUTDATED: 2,
        FreshnessStatus.NEVER_SYNCED: 3,
    }
    return max((item.meta.freshness for item in dashboards), key=rank.__getitem__)


__all__ = [
    "DashboardQuery",
    "OVERVIEW_METRIC_IDS",
    "build_overview_dashboard",
    "build_platform_dashboard",
]
