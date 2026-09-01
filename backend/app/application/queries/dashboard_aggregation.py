"""Metric-catalog-aware dashboard aggregation helpers."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

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
    MetricCatalogError,
    MetricDefinition,
    MetricId,
)
from app.domain.platforms import PlatformId
from app.domain.platforms.catalog import platform_definition
from app.domain.reporting import (
    AvailabilityStatus,
    CommunitySummary,
    DashboardAudienceCapabilities,
    DashboardBreakdown,
    DashboardBreakdownItem,
    DashboardComparison,
    DashboardContent,
    DashboardContentMetrics,
    DashboardContentSummary,
    DashboardHashtag,
    DashboardMetric,
    DashboardMetricMethodology,
    DashboardNamedValue,
    DashboardPoint,
    DashboardSeries,
    DashboardSourceBreakdown,
    DashboardSourceValues,
    DashboardStories,
    DashboardStoryActions,
    DashboardStoryItem,
    DashboardStoryNavigation,
    DashboardStorySummary,
    DashboardStoryTrend,
    DashboardTopCommenter,
    DashboardTopLikedComment,
    DataStatus,
    FreshnessStatus,
    ReportingRange,
)


def methodology_for_definition(
    definition: MetricDefinition,
    *,
    direct_provider_value: bool = False,
    derived_fallback_value: bool = False,
) -> str:
    if direct_provider_value and derived_fallback_value:
        assert definition.derivation_operator is not None
        return ":".join(
            (
                "provider_flow_with_derived_fallback",
                definition.derivation_operator.value,
                f"v{definition.derivation_version}",
                definition.derivation_window or "unspecified_window",
            )
        )
    if direct_provider_value and definition.semantic_type.value == "flow":
        return "provider_flow"
    if definition.derivation_operator is not None:
        return ":".join(
            (
                "derived",
                definition.derivation_operator.value,
                f"v{definition.derivation_version}",
                definition.derivation_window or "unspecified_window",
            )
        )
    if definition.semantic_type.value == "flow":
        return "provider_flow"
    return "provider_reported"


_SNAPSHOT_DELTA_OPERATORS = frozenset(
    {
        DerivationOperator.POSITIVE_SNAPSHOT_DELTA,
        DerivationOperator.NEGATIVE_SNAPSHOT_DELTA,
        DerivationOperator.SIGNED_SNAPSHOT_DELTA,
    }
)


def _snapshot_delta_value(
    previous: float,
    current: float,
    operator: DerivationOperator,
) -> float:
    delta = current - previous
    if operator is DerivationOperator.POSITIVE_SNAPSHOT_DELTA:
        return max(delta, 0.0)
    if operator is DerivationOperator.NEGATIVE_SNAPSHOT_DELTA:
        return max(-delta, 0.0)
    if operator is DerivationOperator.SIGNED_SNAPSHOT_DELTA:
        return delta
    raise ValueError("snapshot_delta_operator_invalid")


def _with_snapshot_delta_fallback(
    definition: MetricDefinition,
    *,
    samples: tuple[ReportingMetric, ...],
    derivation_samples: tuple[ReportingMetric, ...] | None,
) -> tuple[tuple[ReportingMetric, ...], bool]:
    """Merge provider flow rows with exact consecutive-snapshot fallbacks.

    Meta can expose follows/unfollows for only part of a selected range. A
    single provider row previously disabled the snapshot-delta derivation for
    the whole range, so follower-flow charts stopped on the last provider day.
    Provider rows remain authoritative per account/day; only missing cells are
    derived, and never across a missing snapshot day.
    """
    if definition.derivation_operator not in _SNAPSHOT_DELTA_OPERATORS:
        return samples, False

    direct = tuple(
        sample
        for sample in samples
        if sample.metric_id is definition.metric_id and sample.breakdown_key is None
    )
    direct_keys = {(sample.account_id, sample.observed_on) for sample in direct}
    included_dates = {sample.observed_on for sample in samples}
    source_id = definition.derived_from_metric_ids[0]
    by_account: dict[int, list[ReportingMetric]] = defaultdict(list)
    for sample in derivation_samples or samples:
        if sample.metric_id is source_id and sample.breakdown_key is None:
            by_account[sample.account_id].append(sample)

    derived: list[ReportingMetric] = []
    for rows in by_account.values():
        ordered = sorted(rows, key=lambda row: row.observed_on)
        for previous, current in zip(ordered, ordered[1:], strict=False):
            key = (current.account_id, current.observed_on)
            if (
                current.observed_on not in included_dates
                or key in direct_keys
                or current.observed_on - previous.observed_on != timedelta(days=1)
            ):
                continue
            derived.append(
                ReportingMetric(
                    account_id=current.account_id,
                    brand_id=current.brand_id,
                    platform=current.platform,
                    observed_on=current.observed_on,
                    metric_id=definition.metric_id,
                    value=_snapshot_delta_value(
                        previous.value,
                        current.value,
                        definition.derivation_operator,
                    ),
                )
            )
    return direct + tuple(derived), bool(derived)


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
        snapshot_by_account: dict[int, list[ReportingMetric]] = defaultdict(list)
        for sample in samples:
            if sample.metric_id is source_id and sample.breakdown_key is None:
                snapshot_by_account[sample.account_id].append(sample)
        snapshot_deltas: list[float] = []
        for rows in snapshot_by_account.values():
            ordered = sorted(rows, key=lambda row: row.observed_on)
            snapshot_deltas.extend(
                current.value - previous.value
                for previous, current in zip(ordered, ordered[1:], strict=False)
                if current.value >= previous.value
            )
        return sum(snapshot_deltas) if snapshot_deltas else None
    if definition.derivation_operator in _SNAPSHOT_DELTA_OPERATORS:
        source_id = definition.derived_from_metric_ids[0]
        by_account: dict[int, list[ReportingMetric]] = defaultdict(list)
        for sample in samples:
            if sample.metric_id is source_id and sample.breakdown_key is None:
                by_account[sample.account_id].append(sample)
        deltas: list[float] = []
        for rows in by_account.values():
            ordered = sorted(rows, key=lambda row: row.observed_on)
            deltas.extend(
                _snapshot_delta_value(
                    previous.value,
                    current.value,
                    definition.derivation_operator,
                )
                for previous, current in zip(ordered, ordered[1:], strict=False)
                if current.observed_on - previous.observed_on == timedelta(days=1)
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
    derivation_samples: tuple[ReportingMetric, ...] | None = None,
    previous_derivation_samples: tuple[ReportingMetric, ...] | None = None,
) -> tuple[tuple[DashboardMetric, ...], tuple[str, ...]]:
    cards: list[DashboardMetric] = []
    warnings: list[str] = []
    account_set = set(account_ids)
    for definition in catalog.definitions():
        if definition.platform is not platform:
            continue
        direct_samples = tuple(
            sample
            for sample in samples
            if sample.metric_id is definition.metric_id and sample.breakdown_key is None
        )
        effective_samples, has_derived_fallback = _with_snapshot_delta_fallback(
            definition,
            samples=samples,
            derivation_samples=derivation_samples,
        )
        effective_previous_samples, has_previous_derived_fallback = _with_snapshot_delta_fallback(
            definition,
            samples=previous_samples,
            derivation_samples=previous_derivation_samples,
        )
        value = aggregate_value(
            definition,
            (
                effective_samples
                if definition.derivation_operator in _SNAPSHOT_DELTA_OPERATORS
                else samples
            ),
            catalog,
        )
        previous = aggregate_value(
            definition,
            (
                effective_previous_samples
                if definition.derivation_operator in _SNAPSHOT_DELTA_OPERATORS
                else previous_samples
            ),
            catalog,
        )
        source_ids = (
            {definition.metric_id}
            if direct_samples or definition.derivation_operator in _SNAPSHOT_DELTA_OPERATORS
            else set(definition.derived_from_metric_ids) or {definition.metric_id}
        )
        covered = {
            sample.account_id
            for sample in (
                effective_samples
                if definition.derivation_operator in _SNAPSHOT_DELTA_OPERATORS
                else samples
            )
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
        if value is not None and previous is not None and previous != 0:
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
                methodology=methodology_for_definition(
                    definition,
                    direct_provider_value=bool(direct_samples),
                    derived_fallback_value=(has_derived_fallback or has_previous_derived_fallback),
                ),
                availability_reason=(
                    f"metric_unavailable:{definition.metric_id.value}"
                    if status is DataStatus.UNAVAILABLE
                    else f"partial_account_coverage:{definition.metric_id.value}"
                    if status is DataStatus.PARTIAL
                    else None
                ),
            )
        )
    return tuple(cards), tuple(warnings)


def metric_series(
    *,
    platform: PlatformId,
    samples: tuple[ReportingMetric, ...],
    catalog: MetricCatalog,
    derivation_samples: tuple[ReportingMetric, ...] | None = None,
) -> tuple[DashboardSeries, ...]:
    result: list[DashboardSeries] = []
    registered: dict[MetricId, DashboardSeries] = {}
    for definition in catalog.definitions():
        if definition.platform is not platform:
            continue
        series_samples, has_derived_fallback = _with_snapshot_delta_fallback(
            definition,
            samples=samples,
            derivation_samples=derivation_samples,
        )
        by_day: dict[date, list[ReportingMetric]] = defaultdict(list)
        for sample in (
            series_samples
            if definition.derivation_operator in _SNAPSHOT_DELTA_OPERATORS
            else samples
        ):
            if sample.metric_id is definition.metric_id and sample.breakdown_key is None:
                by_day[sample.observed_on].append(sample)
        points: tuple[DashboardPoint, ...] = tuple(
            DashboardPoint(
                observed_on=observed_on,
                value=sum(sample.value for sample in day_samples),
            )
            for observed_on, day_samples in sorted(by_day.items())
        )
        if not points and definition.derivation_operator is DerivationOperator.CUMULATIVE_DELTA:
            source = registered.get(definition.derived_from_metric_ids[0])
            if source is not None:
                points = tuple(
                    DashboardPoint(
                        observed_on=current.observed_on,
                        value=current.value - previous.value,
                    )
                    for previous, current in zip(source.points, source.points[1:], strict=False)
                    if current.value >= previous.value
                )
        elif not points and definition.derivation_operator is DerivationOperator.SUM_COMPONENTS:
            sources = tuple(
                registered.get(metric_id) for metric_id in definition.derived_from_metric_ids
            )
            if all(source is not None for source in sources):
                source_maps = tuple(
                    {point.observed_on: point.value for point in source.points}
                    for source in sources
                    if source is not None
                )
                common_dates = set.intersection(*(set(source_map) for source_map in source_maps))
                points = tuple(
                    DashboardPoint(
                        observed_on=observed_on,
                        value=sum(source_map[observed_on] for source_map in source_maps),
                    )
                    for observed_on in sorted(common_dates)
                )
        elif (
            not points
            and definition.derivation_operator is DerivationOperator.RATIO_FROM_COMPONENTS
        ):
            numerator = registered.get(definition.numerator_metric_id)  # type: ignore[arg-type]
            denominator = registered.get(definition.denominator_metric_id)  # type: ignore[arg-type]
            if numerator is not None and denominator is not None:
                numerator_map = {point.observed_on: point.value for point in numerator.points}
                denominator_map = {point.observed_on: point.value for point in denominator.points}
                points = tuple(
                    DashboardPoint(
                        observed_on=observed_on,
                        value=numerator_map[observed_on] / denominator_map[observed_on],
                    )
                    for observed_on in sorted(set(numerator_map) & set(denominator_map))
                    if denominator_map[observed_on] != 0
                )
        if points:
            dashboard_series = DashboardSeries(
                metric_id=definition.metric_id,
                semantic_type=definition.semantic_type,
                points=points,
                methodology=methodology_for_definition(
                    definition,
                    direct_provider_value=any(
                        sample.metric_id is definition.metric_id and sample.breakdown_key is None
                        for sample in samples
                    ),
                    derived_fallback_value=has_derived_fallback,
                ),
            )
            result.append(dashboard_series)
            registered[definition.metric_id] = dashboard_series
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
    grouped: dict[tuple[MetricId, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
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


_ENGAGEMENT_TIME_ZONE = ZoneInfo("Europe/Istanbul")
_WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _optional_float(value: int | float | None) -> float | None:
    return float(value) if value is not None else None


def _content_interactions(row: ReportingContent) -> float | None:
    if row.interactions_count is not None:
        return float(row.interactions_count)
    counters = (row.likes_count, row.comments_count, row.shares_count)
    if any(value is None for value in counters):
        return None
    return float(sum(value for value in counters if value is not None))


def best_time_to_engage_breakdown(
    platform: PlatformId,
    rows: tuple[ReportingContent, ...],
) -> DashboardBreakdown | None:
    """Average content engagement by local publish weekday and two-hour slot.

    Imported provider heatmaps can be complete zero grids, and TikTok can omit
    audience activity for otherwise healthy small accounts. They say nothing
    about the selected Brand. Published content is an observed, Brand-scoped
    source: grouping its engagement by publish time produces the actionable
    chart the label promises. Stories are excluded because their short lifecycle
    and separate metrics would otherwise overwhelm the post/reel/video publishing
    recommendation.
    """

    buckets: dict[tuple[int, int], list[float]] = defaultdict(list)
    for row in rows:
        if row.published_at is None or "story" in row.content_type.strip().lower():
            continue
        published_at = row.published_at
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)
        local = published_at.astimezone(_ENGAGEMENT_TIME_ZONE)
        engagement = _content_interactions(row)
        if engagement is None:
            continue
        buckets[(local.weekday(), (local.hour // 2) * 2)].append(float(engagement))
    if not buckets:
        return None
    return DashboardBreakdown(
        metric_id=MetricId.INTERACTIONS,
        dimension="best_time_to_engage",
        items=tuple(
            DashboardBreakdownItem(
                key=f"{_WEEKDAY_LABELS[weekday]}|{hour}",
                value=sum(values) / len(values),
                percentage=None,
            )
            for (weekday, hour), values in sorted(buckets.items())
        ),
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
            interactions=(
                int(interactions)
                if (interactions := _content_interactions(row)) is not None
                else None
            ),
            views=row.views_count,
            reach=row.reach_count,
            cover_url=row.cover_url or row.media_url or None,
            thumbnail_url=row.thumbnail_url,
            cover_candidates=(
                row.cover_candidates
                or ((row.cover_url or row.media_url,) if row.cover_url or row.media_url else ())
            ),
            thumbnail_candidates=row.thumbnail_candidates,
            media_url_candidates=(
                row.media_url_candidates or ((row.media_url,) if row.media_url else ())
            ),
            full_video_watched_rate=row.full_video_watched_rate,
            total_time_watched=row.total_time_watched,
            average_time_watched=row.average_time_watched,
            data_status=(
                DataStatus.AVAILABLE
                if row.views_count is not None and row.reach_count is not None
                else DataStatus.PARTIAL
            ),
        )
        for row in ordered[:50]
    )


def _comparison(value: float | None, previous: float | None) -> DashboardComparison:
    delta = None
    if value is not None and previous is not None and previous != 0:
        delta = (value - previous) / abs(previous) * 100
    return DashboardComparison(
        value=value,
        previous_value=previous,
        delta_pct=delta,
    )


@dataclass(frozen=True)
class _ContentTotals:
    views: float | None
    reach: float | None
    likes: float | None
    comments: float | None
    shares: float | None
    interactions: float | None
    engagement_rate: float | None


def content_metric_comparisons(
    rows: tuple[ReportingContent, ...],
    previous_rows: tuple[ReportingContent, ...],
) -> DashboardContentMetrics:
    """Compare content published in adjacent, equally sized date windows."""

    def optional_sum(values: tuple[float | None, ...]) -> float | None:
        available = tuple(value for value in values if value is not None)
        return sum(available) if available else None

    def totals(source: tuple[ReportingContent, ...]) -> _ContentTotals:
        views = optional_sum(tuple(row.views_count for row in source))
        reach = optional_sum(tuple(row.reach_count for row in source))
        likes = optional_sum(tuple(_optional_float(row.likes_count) for row in source))
        comments = optional_sum(tuple(_optional_float(row.comments_count) for row in source))
        shares = optional_sum(tuple(_optional_float(row.shares_count) for row in source))
        interactions = optional_sum(tuple(_content_interactions(row) for row in source))
        return _ContentTotals(
            views=views,
            reach=reach,
            likes=likes,
            comments=comments,
            shares=shares,
            interactions=interactions,
            engagement_rate=(
                interactions / views
                if interactions is not None and views is not None and views > 0
                else None
            ),
        )

    current = totals(rows)
    previous = totals(previous_rows)
    return DashboardContentMetrics(
        views=_comparison(current.views, previous.views),
        reach=_comparison(current.reach, previous.reach),
        likes=_comparison(current.likes, previous.likes),
        comments=_comparison(current.comments, previous.comments),
        shares=_comparison(current.shares, previous.shares),
        interactions=_comparison(current.interactions, previous.interactions),
        engagement_rate=_comparison(
            current.engagement_rate, previous.engagement_rate
        ),
    )


def community_summary(
    rows: tuple[ReportingComment, ...], *, accounts_available: bool
) -> CommunitySummary:
    commenters: dict[str, tuple[int, int]] = {}
    for row in rows:
        name = (row.author_name or "Anonymous").strip() or "Anonymous"
        comments, likes = commenters.get(name, (0, 0))
        commenters[name] = (comments + 1, likes + row.like_count)
    return CommunitySummary(
        total_comments=len(rows),
        answered_comments=sum(1 for row in rows if row.answered),
        unanswered_comments=sum(1 for row in rows if not row.answered),
        comment_likes=sum(row.like_count for row in rows),
        data_status=DataStatus.AVAILABLE if accounts_available else DataStatus.UNAVAILABLE,
        top_commenters=tuple(
            DashboardTopCommenter(name=name, comments=comments, likes=likes)
            for name, (comments, likes) in sorted(
                commenters.items(),
                key=lambda item: (-item[1][0], -item[1][1], item[0].lower()),
            )[:8]
        ),
        top_liked_comments=tuple(
            DashboardTopLikedComment(
                name=(row.author_name or "Anonymous").strip() or "Anonymous",
                comment=row.text[:240],
                likes=row.like_count,
                replies=row.reply_count,
            )
            for row in sorted(
                rows,
                key=lambda item: (-item.like_count, item.external_comment_id),
            )[:8]
        ),
    )


def top_hashtags(rows: tuple[ReportingContent, ...]) -> tuple[DashboardHashtag, ...]:
    counts: dict[str, int] = {}
    for row in rows:
        # FB/IG punctuation terminates a hashtag. Count each tag once per
        # caption so a repeated tag in one post cannot inflate popularity.
        tags = {
            f"#{tag.casefold()}"
            for tag in re.findall(r"(?<!\w)#(\w+)", row.message, flags=re.UNICODE)
        }
        for normalized in tags:
            counts[normalized] = counts.get(normalized, 0) + 1
    return tuple(
        DashboardHashtag(name=name, count=count)
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8]
    )


def comment_sentiment_breakdown(
    rows: tuple[ReportingComment, ...],
) -> DashboardBreakdown | None:
    """Build the chart from classified comments in the selected date range."""

    labels = ("Positive", "Neutral", "Negative")
    counts = {label: 0 for label in labels}
    for row in rows:
        sentiment = str(row.sentiment or "").strip().lower()
        if sentiment in {"positive", "neutral", "negative"}:
            counts[sentiment.title()] += 1
    total = sum(counts.values())
    if total == 0:
        return None
    return DashboardBreakdown(
        metric_id=MetricId.INTERACTIONS,
        dimension="comment_sentiment",
        items=tuple(
            DashboardBreakdownItem(
                key=label,
                value=float(counts[label]),
                percentage=counts[label] / total * 100,
            )
            for label in labels
            if counts[label]
        ),
    )


def _named_breakdown(
    breakdowns: tuple[DashboardBreakdown, ...], hint: str
) -> tuple[DashboardNamedValue, ...]:
    row = next(
        (item for item in breakdowns if hint in item.dimension.lower()),
        None,
    )
    return tuple(
        DashboardNamedValue(name=item.key, value=item.value) for item in (row.items if row else ())
    )


def content_summary(
    rows: tuple[ReportingContent, ...],
    breakdowns: tuple[DashboardBreakdown, ...],
    *,
    accounts_available: bool,
) -> DashboardContentSummary:
    counts: dict[str, int] = {}
    for row in rows:
        label = (row.content_type or "post").replace("_", " ").title()
        counts[label] = counts.get(label, 0) + 1
    by_type = tuple(
        DashboardNamedValue(name=name, value=float(value)) for name, value in sorted(counts.items())
    )
    reach_by_type = _named_breakdown(breakdowns, "content_type_reach")
    views_by_type = _named_breakdown(breakdowns, "content_type_views")
    if not reach_by_type:
        reach_totals: dict[str, float] = defaultdict(float)
        for row in rows:
            if row.reach_count is not None:
                label = (row.content_type or "post").replace("_", " ").title()
                reach_totals[label] += row.reach_count
        reach_by_type = tuple(
            DashboardNamedValue(name=name, value=value)
            for name, value in sorted(reach_totals.items())
        )
    if not views_by_type:
        view_totals: dict[str, float] = defaultdict(float)
        for row in rows:
            if row.views_count is not None:
                label = (row.content_type or "post").replace("_", " ").title()
                view_totals[label] += row.views_count
        views_by_type = tuple(
            DashboardNamedValue(name=name, value=value)
            for name, value in sorted(view_totals.items())
        )
    if not accounts_available:
        status = DataStatus.UNAVAILABLE
    elif rows and reach_by_type and views_by_type:
        status = DataStatus.AVAILABLE
    else:
        status = DataStatus.PARTIAL
    return DashboardContentSummary(
        total=len(rows),
        by_type=by_type,
        reach_by_type=reach_by_type,
        views_by_type=views_by_type,
        data_status=status,
    )


def _source_values(
    breakdowns: tuple[DashboardBreakdown, ...],
    metric_id: MetricId,
) -> tuple[DashboardSourceValues | None, bool]:
    row = next(
        (
            item
            for item in breakdowns
            if item.metric_id is metric_id
            and any(
                "organic" in value.key.lower() or "paid" in value.key.lower()
                for value in item.items
            )
        ),
        None,
    )
    if row is None:
        return None, False
    organic = next(
        (item.value for item in row.items if "organic" in item.key.lower()),
        None,
    )
    paid_item = next(
        (item for item in row.items if "paid" in item.key.lower()),
        None,
    )
    status = DataStatus.AVAILABLE if organic is not None else DataStatus.PARTIAL
    return (
        DashboardSourceValues(
            organic=organic,
            paid=paid_item.value if paid_item else None,
            data_status=status,
        ),
        paid_item is not None,
    )


def _source_series_values(
    samples: tuple[ReportingMetric, ...],
    *,
    organic_metric_id: MetricId,
    paid_metric_id: MetricId,
) -> tuple[DashboardSourceValues | None, bool]:
    """Aggregate the V1 organic/paid series over the selected reporting range.

    The immutable legacy import stores source delivery as four canonical series
    (views/reach x organic/paid), while current Meta responses also expose a
    breakdown on the parent metric.  Ignoring the series made an old Brand's
    source cards empty even though every selected day was present in storage.
    Keep this read-only compatibility path so imported Brands work immediately;
    native breakdowns remain the fallback for newly collected accounts.
    """
    organic_rows = tuple(
        sample
        for sample in samples
        if sample.metric_id is organic_metric_id and sample.breakdown_key is None
    )
    paid_rows = tuple(
        sample
        for sample in samples
        if sample.metric_id is paid_metric_id and sample.breakdown_key is None
    )
    if not organic_rows and not paid_rows:
        return None, False
    return (
        DashboardSourceValues(
            organic=sum(sample.value for sample in organic_rows) if organic_rows else None,
            paid=sum(sample.value for sample in paid_rows) if paid_rows else None,
            data_status=(DataStatus.AVAILABLE if organic_rows else DataStatus.PARTIAL),
        ),
        bool(paid_rows),
    )


def source_breakdown(
    breakdowns: tuple[DashboardBreakdown, ...],
    samples: tuple[ReportingMetric, ...] = (),
) -> DashboardSourceBreakdown | None:
    views, views_paid = _source_series_values(
        samples,
        organic_metric_id=MetricId.VIEWS_ORGANIC,
        paid_metric_id=MetricId.VIEWS_PAID,
    )
    if views is None:
        views, views_paid = _source_values(breakdowns, MetricId.VIEWS)
    reach, reach_paid = _source_series_values(
        samples,
        organic_metric_id=MetricId.REACH_ORGANIC,
        paid_metric_id=MetricId.REACH_PAID,
    )
    if reach is None:
        reach, reach_paid = _source_values(breakdowns, MetricId.REACH)
    if views is None and reach is None:
        return None
    statuses = {item.data_status for item in (views, reach) if item is not None}
    status = (
        DataStatus.AVAILABLE
        if statuses == {DataStatus.AVAILABLE} and views is not None and reach is not None
        else DataStatus.PARTIAL
    )
    paid_available = views_paid or reach_paid
    return DashboardSourceBreakdown(
        organic_only=not paid_available,
        paid_available=paid_available,
        views=views,
        reach=reach,
        data_status=status,
    )


def metric_methodology(platform: PlatformId, catalog: MetricCatalog) -> DashboardMetricMethodology:
    def method(metric_id: MetricId) -> str:
        try:
            return methodology_for_definition(catalog.get(platform, metric_id))
        except MetricCatalogError:
            return "unavailable"

    engagement_id = (
        MetricId.VIDEO_ENGAGEMENT_RATE
        if platform is PlatformId.TIKTOK
        else MetricId.ENGAGEMENT_RATE
    )
    return DashboardMetricMethodology(
        follower_flow=method(MetricId.NEW_FOLLOWERS),
        engagement_rate=method(engagement_id),
        reach=method(MetricId.REACH),
    )


def audience_capabilities(
    platform: PlatformId,
    breakdowns: tuple[DashboardBreakdown, ...],
    *,
    accounts_available: bool,
) -> DashboardAudienceCapabilities:
    singular = {
        "ages": "age",
        "genders": "gender",
        "countries": "country",
        "cities": "city",
    }
    dimensions = {
        frozenset(
            singular.get(token, token)
            for token in item.dimension.lower().replace("-", "_").split("_")
        )
        for item in breakdowns
    }
    country_available = any("country" in item for item in dimensions)
    city_available = any("city" in item for item in dimensions)
    age_available = any("age" in item for item in dimensions)
    gender_available = any("gender" in item for item in dimensions)
    activity_available = any(
        "activity" in item or "hourly" in item or {"best", "time"} <= item for item in dimensions
    )
    if platform is PlatformId.FACEBOOK:
        return DashboardAudienceCapabilities(
            source="meta_graph_api_v23",
            geo=(
                AvailabilityStatus.AVAILABLE
                if country_available or city_available
                else AvailabilityStatus.PENDING
                if accounts_available
                else AvailabilityStatus.UNAVAILABLE
            ),
            age_gender=AvailabilityStatus.PROVIDER_UNAVAILABLE,
            activity=AvailabilityStatus.PROVIDER_UNAVAILABLE,
        )
    geo_status = (
        AvailabilityStatus.AVAILABLE
        if country_available and city_available
        else AvailabilityStatus.PARTIAL
        if country_available or city_available
        else AvailabilityStatus.UNAVAILABLE
    )
    age_status = (
        AvailabilityStatus.AVAILABLE
        if age_available and gender_available
        else AvailabilityStatus.PARTIAL
        if age_available or gender_available
        else AvailabilityStatus.UNAVAILABLE
    )
    return DashboardAudienceCapabilities(
        source=platform_definition(platform).audience_source,
        geo=geo_status,
        age_gender=age_status,
        activity=(
            AvailabilityStatus.AVAILABLE if activity_available else AvailabilityStatus.UNAVAILABLE
        ),
    )


def _breakdown_total(breakdowns: tuple[DashboardBreakdown, ...], hint: str) -> float | None:
    row = next((item for item in breakdowns if hint in item.dimension.lower()), None)
    return sum(item.value for item in row.items) if row else None


def _story_named_totals(breakdowns: tuple[DashboardBreakdown, ...], hint: str) -> dict[str, float]:
    row = next((item for item in breakdowns if hint in item.dimension.lower()), None)
    return {item.key.lower(): item.value for item in row.items} if row else {}


def _first_named_value(values: dict[str, float], *keys: str) -> float | None:
    for key in keys:
        if key in values:
            return values[key]
    return None


def _optional_sum(values: tuple[float | None, ...]) -> float | None:
    available = tuple(value for value in values if value is not None)
    return sum(available) if available else None


def _story_interactions(row: ReportingContent) -> float | None:
    return _content_interactions(row)


def _story_completion(rows: tuple[ReportingContent, ...]) -> float | None:
    values = tuple(row.completion_rate for row in rows if row.completion_rate is not None)
    return sum(values) / len(values) if values else None


def _story_summary_from_rows(
    rows: tuple[ReportingContent, ...],
) -> DashboardStorySummary:
    story_views = _optional_sum(tuple(row.views_count for row in rows))
    story_reach = _optional_sum(tuple(row.reach_count for row in rows))
    story_interactions = _optional_sum(tuple(_story_interactions(row) for row in rows))
    story_replies = _optional_sum(
        tuple(
            row.replies_count
            if row.replies_count is not None
            else _optional_float(row.comments_count)
            for row in rows
        )
    )
    story_completion = _story_completion(rows)
    status = (
        DataStatus.AVAILABLE
        if rows
        and all(
            value is not None
            for value in (
                story_views,
                story_reach,
                story_interactions,
                story_replies,
                story_completion,
            )
        )
        else DataStatus.PARTIAL
        if rows
        else DataStatus.UNAVAILABLE
    )
    return DashboardStorySummary(
        count=len(rows),
        views=story_views,
        reach=story_reach,
        interactions=story_interactions,
        replies=story_replies,
        completion_rate=story_completion,
        data_status=status,
    )


def stories_contract(
    *,
    platform: PlatformId,
    rows: tuple[ReportingContent, ...],
    previous_rows: tuple[ReportingContent, ...],
    breakdowns: tuple[DashboardBreakdown, ...],
    date_range: ReportingRange,
) -> DashboardStories | None:
    if platform is not PlatformId.INSTAGRAM:
        return None
    story_rows = tuple(
        sorted(
            (row for row in rows if "story" in row.content_type.lower()),
            key=lambda row: row.published_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
    )
    previous_story_rows = tuple(row for row in previous_rows if "story" in row.content_type.lower())
    has_story_breakdown = any("story_" in row.dimension.lower() for row in breakdowns)
    if not story_rows and not has_story_breakdown:
        return None
    row_summary = _story_summary_from_rows(story_rows)
    summary_views = _breakdown_total(breakdowns, "story_views")
    summary_reach = _breakdown_total(breakdowns, "story_reach")
    summary_interactions = _breakdown_total(breakdowns, "story_interactions")
    summary_replies = _breakdown_total(breakdowns, "story_replies")
    summary_completion = _breakdown_total(breakdowns, "story_completion_rate")
    summary_views = row_summary.views if summary_views is None else summary_views
    summary_reach = row_summary.reach if summary_reach is None else summary_reach
    summary_interactions = (
        row_summary.interactions if summary_interactions is None else summary_interactions
    )
    summary_replies = row_summary.replies if summary_replies is None else summary_replies
    summary_completion = (
        row_summary.completion_rate if summary_completion is None else summary_completion
    )
    complete_summary = all(
        value is not None
        for value in (
            summary_views,
            summary_reach,
            summary_interactions,
            summary_replies,
            summary_completion,
        )
    )
    navigation_values = _story_named_totals(breakdowns, "story_navigation")
    action_values = _story_named_totals(breakdowns, "story_actions")
    labels = tuple(
        date_range.start_on + timedelta(days=index)
        for index in range((date_range.end_on - date_range.start_on).days + 1)
    )
    views_available = any(row.views_count is not None for row in story_rows)
    reach_available = any(row.reach_count is not None for row in story_rows)
    views_complete = bool(story_rows) and all(row.views_count is not None for row in story_rows)
    reach_complete = bool(story_rows) and all(row.reach_count is not None for row in story_rows)
    daily_views: dict[date, float] = defaultdict(float)
    daily_reach: dict[date, float] = defaultdict(float)
    stories_by_day: dict[date, list[ReportingContent]] = defaultdict(list)
    for row in story_rows:
        observed_on = row.published_at.date() if row.published_at else date_range.start_on
        stories_by_day[observed_on].append(row)
        if row.views_count is not None:
            daily_views[observed_on] += row.views_count
        if row.reach_count is not None:
            daily_reach[observed_on] += row.reach_count

    def daily_values(
        values: dict[date, float],
        field: str,
        *,
        available: bool,
    ) -> tuple[float | None, ...]:
        if not available:
            return tuple(None for _ in labels)
        result: list[float | None] = []
        for observed_on in labels:
            day_rows = stories_by_day.get(observed_on, ())
            if not day_rows:
                result.append(0.0)
            elif any(getattr(row, field) is not None for row in day_rows):
                result.append(values.get(observed_on, 0.0))
            else:
                result.append(None)
        return tuple(result)

    navigation_from_rows = {
        "taps_forward": _optional_sum(tuple(row.taps_forward for row in story_rows)),
        "taps_back": _optional_sum(tuple(row.taps_back for row in story_rows)),
        "swipe_forward": _optional_sum(tuple(row.swipe_forward for row in story_rows)),
        "exits": _optional_sum(tuple(row.exits for row in story_rows)),
    }
    actions_from_rows = {
        "replies": _optional_sum(
            tuple(
                row.replies_count
                if row.replies_count is not None
                else _optional_float(row.comments_count)
                for row in story_rows
            )
        ),
        "shares": _optional_sum(
            tuple(_optional_float(row.shares_count) for row in story_rows)
        ),
        "profile_visits": _optional_sum(tuple(row.profile_visits for row in story_rows)),
        MetricId.FOLLOWS.value: _optional_sum(tuple(row.follows_count for row in story_rows)),
        "sticker_taps": _optional_sum(tuple(row.sticker_taps for row in story_rows)),
        "saves": _optional_sum(tuple(row.saves_count for row in story_rows)),
    }
    previous_summary = _story_summary_from_rows(previous_story_rows)
    navigation_complete = bool(navigation_values) or all(
        value is not None for value in navigation_from_rows.values()
    )
    core_action_values = (
        actions_from_rows["replies"],
        actions_from_rows["shares"],
        actions_from_rows["profile_visits"],
        actions_from_rows[MetricId.FOLLOWS.value],
    )
    actions_complete = bool(action_values) or all(value is not None for value in core_action_values)
    items_complete = bool(story_rows) and all(
        all(
            value is not None
            for value in (
                row.views_count,
                row.reach_count,
                row.profile_visits,
                row.follows_count,
                row.taps_forward,
                row.taps_back,
                row.swipe_forward,
                row.exits,
                row.navigation_count,
                row.completion_rate,
            )
        )
        for row in story_rows
    )
    structured_available = (
        complete_summary
        and previous_summary.data_status is DataStatus.AVAILABLE
        and views_complete
        and reach_complete
        and navigation_complete
        and actions_complete
        and items_complete
    )
    return DashboardStories(
        summary=DashboardStorySummary(
            count=len(story_rows),
            views=summary_views,
            reach=summary_reach,
            interactions=summary_interactions,
            replies=summary_replies,
            completion_rate=summary_completion,
            data_status=DataStatus.AVAILABLE if complete_summary else DataStatus.PARTIAL,
        ),
        previous_summary=previous_summary,
        trend=DashboardStoryTrend(
            labels=labels,
            views=daily_values(
                daily_views,
                "views_count",
                available=views_available,
            ),
            reach=daily_values(
                daily_reach,
                "reach_count",
                available=reach_available,
            ),
            data_status=(
                DataStatus.AVAILABLE
                if views_complete and reach_complete
                else DataStatus.PARTIAL
                if views_available or reach_available
                else DataStatus.UNAVAILABLE
            ),
        ),
        navigation=DashboardStoryNavigation(
            taps_forward=_first_named_value(navigation_values, "forward", "tap forward")
            if navigation_values
            else navigation_from_rows["taps_forward"],
            taps_back=_first_named_value(navigation_values, "back", "tap back")
            if navigation_values
            else navigation_from_rows["taps_back"],
            swipe_forward=_first_named_value(navigation_values, "next story", "swipe forward")
            if navigation_values
            else navigation_from_rows["swipe_forward"],
            exits=_first_named_value(navigation_values, "exited", "exits")
            if navigation_values
            else navigation_from_rows["exits"],
            data_status=(
                DataStatus.AVAILABLE
                if navigation_values
                or all(value is not None for value in navigation_from_rows.values())
                else DataStatus.PARTIAL
                if any(value is not None for value in navigation_from_rows.values())
                else DataStatus.UNAVAILABLE
            ),
        ),
        actions=DashboardStoryActions(
            replies=(
                action_values.get("replies") if action_values else actions_from_rows["replies"]
            ),
            shares=(action_values.get("shares") if action_values else actions_from_rows["shares"]),
            profile_visits=(
                action_values.get("profile visits")
                if action_values
                else actions_from_rows["profile_visits"]
            ),
            follows=(
                action_values.get(MetricId.FOLLOWS.value)
                if action_values
                else actions_from_rows[MetricId.FOLLOWS.value]
            ),
            sticker_taps=(
                action_values.get("sticker taps")
                if action_values
                else actions_from_rows["sticker_taps"]
            ),
            saves=(action_values.get("saves") if action_values else actions_from_rows["saves"]),
            data_status=(
                DataStatus.AVAILABLE
                if action_values or all(value is not None for value in actions_from_rows.values())
                else DataStatus.PARTIAL
                if any(value is not None for value in actions_from_rows.values())
                else DataStatus.UNAVAILABLE
            ),
        ),
        items=tuple(
            DashboardStoryItem(
                content_id=row.external_content_id,
                title=row.message[:120] or "Story",
                # A video Story's media URL is an MP4 and cannot be rendered by
                # the gallery's <img>. Prefer the provider thumbnail/local
                # cover; media_url remains the last resort for image Stories.
                cover_url=row.cover_url or row.thumbnail_url or row.media_url,
                permalink=row.permalink,
                created_time=row.published_at,
                views=row.views_count,
                reach=row.reach_count,
                interactions=_story_interactions(row),
                replies=(
                    row.replies_count
                    if row.replies_count is not None
                    else _optional_float(row.comments_count)
                ),
                shares=_optional_float(row.shares_count),
                profile_visits=row.profile_visits,
                follows=row.follows_count,
                sticker_taps=row.sticker_taps,
                saves=row.saves_count,
                taps_forward=row.taps_forward,
                taps_back=row.taps_back,
                swipe_forward=row.swipe_forward,
                exits=row.exits,
                navigation=row.navigation_count,
                completion_rate=row.completion_rate,
                data_status=(
                    DataStatus.AVAILABLE
                    if all(
                        value is not None
                        for value in (
                            row.views_count,
                            row.reach_count,
                            row.profile_visits,
                            row.follows_count,
                            row.taps_forward,
                            row.taps_back,
                            row.swipe_forward,
                            row.exits,
                            row.navigation_count,
                            row.completion_rate,
                        )
                    )
                    else DataStatus.PARTIAL
                ),
            )
            for row in story_rows
        ),
        data_status=(DataStatus.AVAILABLE if structured_available else DataStatus.PARTIAL),
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
    "audience_capabilities",
    "best_time_to_engage_breakdown",
    "community_summary",
    "content_metric_comparisons",
    "content_summary",
    "content_cards",
    "freshness",
    "metric_breakdowns",
    "metric_cards",
    "metric_methodology",
    "metric_series",
    "methodology_for_definition",
    "source_breakdown",
    "stories_contract",
    "top_hashtags",
    "comment_sentiment_breakdown",
]
