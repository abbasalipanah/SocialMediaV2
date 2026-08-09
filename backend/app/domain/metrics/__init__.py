"""Versioned metric semantics used before collection, storage, or querying."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from app.domain.platforms import CapabilityId, PlatformId


class MetricCatalogError(ValueError):
    pass


class MetricId(StrEnum):
    FOLLOWERS = "followers"
    FOLLOWING = "following"
    NEW_FOLLOWERS = "new_followers"
    FOLLOWS = "follows"
    UNFOLLOWS = "unfollows"
    FOLLOWERS_NET = "followers_net"
    REACH = "reach"
    REACH_PAID = "reach_paid"
    REACH_ORGANIC = "reach_organic"
    VIEWS = "views"
    VIEWS_PAID = "views_paid"
    VIEWS_ORGANIC = "views_organic"
    INTERACTIONS = "interactions"
    ENGAGEMENT_RATE = "engagement_rate"
    PAGE_VIEWS = "page_views"
    PROFILE_VIEWS = "profile_views"
    WEBSITE_CLICKS = "website_clicks"
    TOTAL_ACTIONS = "total_actions"
    REACTIONS = "reactions"
    MEDIA_COUNT = "media_count"
    VIDEO_VIEWS_TOTAL = "video_views_total"
    VIDEO_VIEWS_CHANGE = "video_views_change"
    VIDEO_LIKES_TOTAL = "video_likes_total"
    VIDEO_COMMENTS_TOTAL = "video_comments_total"
    VIDEO_SHARES_TOTAL = "video_shares_total"
    VIDEO_ENGAGEMENTS_TOTAL = "video_engagements_total"
    VIDEO_ENGAGEMENT_RATE = "video_engagement_rate"


class EntityScope(StrEnum):
    PROFILE = "profile"
    CONTENT = "content"


class SemanticType(StrEnum):
    SNAPSHOT = "snapshot"
    FLOW = "flow"
    CUMULATIVE = "cumulative"
    RATIO = "ratio"


class Unit(StrEnum):
    COUNT = "count"
    RATIO = "ratio"


class CollectionGranularity(StrEnum):
    SAMPLE = "sample"
    DAY = "day"


class AggregationPolicy(StrEnum):
    LAST_VALID = "last_valid"
    SUM = "sum"
    RECOMPUTE = "recompute"


class NullPolicy(StrEnum):
    NOT_AVAILABLE = "not_available"


class ResetPolicy(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    FLAG_AND_WAIT_FOR_NEXT_SAMPLE = "flag_and_wait_for_next_sample"


class FirstSamplePolicy(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    NOT_AVAILABLE = "not_available"


class ZeroDenominatorPolicy(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    NOT_AVAILABLE = "not_available"


class DerivationOperator(StrEnum):
    CUMULATIVE_DELTA = "cumulative_delta"
    SUM_COMPONENTS = "sum_components"
    RATIO_FROM_COMPONENTS = "ratio_from_components"


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: MetricId
    platform: PlatformId
    entity_scope: EntityScope
    semantic_type: SemanticType
    unit: Unit
    source_field: str | None
    collection_granularity: CollectionGranularity
    period_aggregation: AggregationPolicy
    brand_rollup_aggregation: AggregationPolicy
    null_policy: NullPolicy
    reset_policy: ResetPolicy
    derived_from_metric_ids: tuple[MetricId, ...]
    derivation_operator: DerivationOperator | None
    derivation_version: int | None
    derivation_window: str | None
    first_sample_policy: FirstSamplePolicy
    numerator_metric_id: MetricId | None
    denominator_metric_id: MetricId | None
    zero_denominator_policy: ZeroDenominatorPolicy
    allowed_breakdowns: tuple[str, ...]
    required_capability: CapabilityId
    version: int

    def __post_init__(self) -> None:
        if self.version < 1:
            raise MetricCatalogError("metric_version_invalid")
        if not self.source_field and not self.derived_from_metric_ids:
            raise MetricCatalogError("metric_source_missing")
        if len(set(self.allowed_breakdowns)) != len(self.allowed_breakdowns):
            raise MetricCatalogError("metric_breakdown_duplicate")
        self._validate_derived_contract()
        self._validate_ratio_contract()
        self._validate_aggregation_contract()

    def _validate_derived_contract(self) -> None:
        derived_fields = (
            self.derivation_operator,
            self.derivation_version,
            self.derivation_window,
        )
        if self.derived_from_metric_ids:
            if any(value is None for value in derived_fields):
                raise MetricCatalogError("derived_metric_contract_incomplete")
            if self.derivation_version is not None and self.derivation_version < 1:
                raise MetricCatalogError("derivation_version_invalid")
            if self.source_field is not None:
                raise MetricCatalogError("derived_metric_has_source_field")
        elif any(value is not None for value in derived_fields):
            raise MetricCatalogError("source_metric_has_derivation")

    def _validate_ratio_contract(self) -> None:
        ratio_fields = (self.numerator_metric_id, self.denominator_metric_id)
        if self.semantic_type is SemanticType.RATIO:
            if any(value is None for value in ratio_fields):
                raise MetricCatalogError("ratio_metric_contract_incomplete")
            if self.zero_denominator_policy is ZeroDenominatorPolicy.NOT_APPLICABLE:
                raise MetricCatalogError("ratio_zero_denominator_policy_missing")
            if self.period_aggregation is not AggregationPolicy.RECOMPUTE:
                raise MetricCatalogError("ratio_period_aggregation_invalid")
            if self.brand_rollup_aggregation is not AggregationPolicy.RECOMPUTE:
                raise MetricCatalogError("ratio_rollup_aggregation_invalid")
            if self.unit is not Unit.RATIO:
                raise MetricCatalogError("ratio_unit_invalid")
            if not set(ratio_fields).issubset(self.derived_from_metric_ids):
                raise MetricCatalogError("ratio_sources_incomplete")
        elif any(value is not None for value in ratio_fields) or (
            self.zero_denominator_policy is not ZeroDenominatorPolicy.NOT_APPLICABLE
        ):
            raise MetricCatalogError("non_ratio_has_ratio_contract")
        elif self.unit is Unit.RATIO:
            raise MetricCatalogError("non_ratio_unit_invalid")

    def _validate_aggregation_contract(self) -> None:
        if self.semantic_type in {SemanticType.SNAPSHOT, SemanticType.CUMULATIVE}:
            if self.period_aggregation is not AggregationPolicy.LAST_VALID:
                raise MetricCatalogError("total_metric_period_aggregation_invalid")
        if self.semantic_type is SemanticType.FLOW:
            if self.period_aggregation is not AggregationPolicy.SUM:
                raise MetricCatalogError("flow_period_aggregation_invalid")
        if self.derivation_operator is DerivationOperator.CUMULATIVE_DELTA:
            if self.semantic_type is not SemanticType.FLOW:
                raise MetricCatalogError("cumulative_delta_must_be_flow")
            if self.first_sample_policy is not FirstSamplePolicy.NOT_AVAILABLE:
                raise MetricCatalogError("cumulative_delta_first_sample_invalid")
            if self.reset_policy is ResetPolicy.NOT_APPLICABLE:
                raise MetricCatalogError("cumulative_delta_reset_policy_missing")


class MetricCatalog:
    def __init__(self, definitions: tuple[MetricDefinition, ...]) -> None:
        by_key: dict[tuple[PlatformId, MetricId], MetricDefinition] = {}
        for definition in definitions:
            key = (definition.platform, definition.metric_id)
            if key in by_key:
                raise MetricCatalogError("metric_definition_duplicate")
            by_key[key] = definition
        self._definitions = MappingProxyType(by_key)
        self._validate_references()

    def _validate_references(self) -> None:
        for definition in self._definitions.values():
            references = set(definition.derived_from_metric_ids)
            references.update(
                metric_id
                for metric_id in (
                    definition.numerator_metric_id,
                    definition.denominator_metric_id,
                )
                if metric_id is not None
            )
            for metric_id in references:
                if (definition.platform, metric_id) not in self._definitions:
                    raise MetricCatalogError("metric_reference_not_registered")

    def get(self, platform: PlatformId, metric_id: MetricId) -> MetricDefinition:
        try:
            return self._definitions[(platform, metric_id)]
        except KeyError as exc:
            raise MetricCatalogError("metric_not_registered") from exc

    def require_capability(
        self,
        platform: PlatformId,
        metric_id: MetricId,
        capability: CapabilityId,
    ) -> MetricDefinition:
        definition = self.get(platform, metric_id)
        if definition.required_capability is not capability:
            raise MetricCatalogError("metric_capability_mismatch")
        return definition

    def validate_values(
        self,
        *,
        platform: PlatformId,
        capability: CapabilityId,
        values: Mapping[MetricId, float | int | None],
    ) -> Mapping[MetricId, float | int | None]:
        validated: dict[MetricId, float | int | None] = {}
        for metric_id, value in values.items():
            if not isinstance(metric_id, MetricId):
                raise MetricCatalogError("metric_id_must_be_canonical")
            self.require_capability(platform, metric_id, capability)
            if isinstance(value, bool):
                raise MetricCatalogError("metric_value_invalid")
            if isinstance(value, float) and not math.isfinite(value):
                raise MetricCatalogError("metric_value_invalid")
            if value is not None and not isinstance(value, int | float):
                raise MetricCatalogError("metric_value_invalid")
            validated[metric_id] = value
        return MappingProxyType(validated)

    def definitions(self) -> tuple[MetricDefinition, ...]:
        return tuple(self._definitions.values())


def _profile_snapshot(
    platform: PlatformId,
    metric_id: MetricId,
    source_field: str,
    *,
    allowed_breakdowns: tuple[str, ...] = (),
) -> MetricDefinition:
    return MetricDefinition(
        metric_id=metric_id,
        platform=platform,
        entity_scope=EntityScope.PROFILE,
        semantic_type=SemanticType.SNAPSHOT,
        unit=Unit.COUNT,
        source_field=source_field,
        collection_granularity=CollectionGranularity.SAMPLE,
        period_aggregation=AggregationPolicy.LAST_VALID,
        brand_rollup_aggregation=AggregationPolicy.SUM,
        null_policy=NullPolicy.NOT_AVAILABLE,
        reset_policy=ResetPolicy.NOT_APPLICABLE,
        derived_from_metric_ids=(),
        derivation_operator=None,
        derivation_version=None,
        derivation_window=None,
        first_sample_policy=FirstSamplePolicy.NOT_APPLICABLE,
        numerator_metric_id=None,
        denominator_metric_id=None,
        zero_denominator_policy=ZeroDenominatorPolicy.NOT_APPLICABLE,
        allowed_breakdowns=allowed_breakdowns,
        required_capability=CapabilityId.PROFILE,
        version=1,
    )


def _profile_flow(platform: PlatformId, metric_id: MetricId, source_field: str) -> MetricDefinition:
    return MetricDefinition(
        metric_id=metric_id,
        platform=platform,
        entity_scope=EntityScope.PROFILE,
        semantic_type=SemanticType.FLOW,
        unit=Unit.COUNT,
        source_field=source_field,
        collection_granularity=CollectionGranularity.DAY,
        period_aggregation=AggregationPolicy.SUM,
        brand_rollup_aggregation=AggregationPolicy.SUM,
        null_policy=NullPolicy.NOT_AVAILABLE,
        reset_policy=ResetPolicy.NOT_APPLICABLE,
        derived_from_metric_ids=(),
        derivation_operator=None,
        derivation_version=None,
        derivation_window=None,
        first_sample_policy=FirstSamplePolicy.NOT_APPLICABLE,
        numerator_metric_id=None,
        denominator_metric_id=None,
        zero_denominator_policy=ZeroDenominatorPolicy.NOT_APPLICABLE,
        allowed_breakdowns=(),
        required_capability=CapabilityId.PROFILE,
        version=1,
    )


def _profile_cumulative_delta(
    platform: PlatformId,
    metric_id: MetricId,
    source_metric_id: MetricId,
) -> MetricDefinition:
    return MetricDefinition(
        metric_id=metric_id,
        platform=platform,
        entity_scope=EntityScope.PROFILE,
        semantic_type=SemanticType.FLOW,
        unit=Unit.COUNT,
        source_field=None,
        collection_granularity=CollectionGranularity.DAY,
        period_aggregation=AggregationPolicy.SUM,
        brand_rollup_aggregation=AggregationPolicy.SUM,
        null_policy=NullPolicy.NOT_AVAILABLE,
        reset_policy=ResetPolicy.FLAG_AND_WAIT_FOR_NEXT_SAMPLE,
        derived_from_metric_ids=(source_metric_id,),
        derivation_operator=DerivationOperator.CUMULATIVE_DELTA,
        derivation_version=1,
        derivation_window="utc_day",
        first_sample_policy=FirstSamplePolicy.NOT_AVAILABLE,
        numerator_metric_id=None,
        denominator_metric_id=None,
        zero_denominator_policy=ZeroDenominatorPolicy.NOT_APPLICABLE,
        allowed_breakdowns=(),
        required_capability=CapabilityId.PROFILE,
        version=1,
    )


def _profile_ratio(
    platform: PlatformId,
    metric_id: MetricId,
    numerator_metric_id: MetricId,
    denominator_metric_id: MetricId,
) -> MetricDefinition:
    return MetricDefinition(
        metric_id=metric_id,
        platform=platform,
        entity_scope=EntityScope.PROFILE,
        semantic_type=SemanticType.RATIO,
        unit=Unit.RATIO,
        source_field=None,
        collection_granularity=CollectionGranularity.DAY,
        period_aggregation=AggregationPolicy.RECOMPUTE,
        brand_rollup_aggregation=AggregationPolicy.RECOMPUTE,
        null_policy=NullPolicy.NOT_AVAILABLE,
        reset_policy=ResetPolicy.NOT_APPLICABLE,
        derived_from_metric_ids=(numerator_metric_id, denominator_metric_id),
        derivation_operator=DerivationOperator.RATIO_FROM_COMPONENTS,
        derivation_version=1,
        derivation_window="selected_period",
        first_sample_policy=FirstSamplePolicy.NOT_APPLICABLE,
        numerator_metric_id=numerator_metric_id,
        denominator_metric_id=denominator_metric_id,
        zero_denominator_policy=ZeroDenominatorPolicy.NOT_AVAILABLE,
        allowed_breakdowns=(),
        required_capability=CapabilityId.PROFILE,
        version=1,
    )


FACEBOOK_DAILY_SOURCE_METRICS = (
    ("page_media_view", MetricId.VIEWS),
    ("page_posts_impressions", MetricId.VIEWS),
    ("page_impressions_unique", MetricId.REACH),
    ("page_posts_impressions_unique", MetricId.REACH),
    ("page_views_total", MetricId.PAGE_VIEWS),
    ("page_post_engagements", MetricId.INTERACTIONS),
    ("page_total_actions", MetricId.TOTAL_ACTIONS),
    ("page_actions_post_reactions_total", MetricId.REACTIONS),
)

INSTAGRAM_DAILY_SOURCE_METRICS = (
    ("reach", MetricId.REACH),
    ("views", MetricId.VIEWS),
    ("profile_views", MetricId.PROFILE_VIEWS),
    ("website_clicks", MetricId.WEBSITE_CLICKS),
    ("total_interactions", MetricId.INTERACTIONS),
)


def bootstrap_metric_catalog() -> MetricCatalog:
    views_total = MetricDefinition(
        metric_id=MetricId.VIDEO_VIEWS_TOTAL,
        platform=PlatformId.TIKTOK,
        entity_scope=EntityScope.CONTENT,
        semantic_type=SemanticType.CUMULATIVE,
        unit=Unit.COUNT,
        source_field="play_count",
        collection_granularity=CollectionGranularity.SAMPLE,
        period_aggregation=AggregationPolicy.LAST_VALID,
        brand_rollup_aggregation=AggregationPolicy.SUM,
        null_policy=NullPolicy.NOT_AVAILABLE,
        reset_policy=ResetPolicy.FLAG_AND_WAIT_FOR_NEXT_SAMPLE,
        derived_from_metric_ids=(),
        derivation_operator=None,
        derivation_version=None,
        derivation_window=None,
        first_sample_policy=FirstSamplePolicy.NOT_APPLICABLE,
        numerator_metric_id=None,
        denominator_metric_id=None,
        zero_denominator_policy=ZeroDenominatorPolicy.NOT_APPLICABLE,
        allowed_breakdowns=(),
        required_capability=CapabilityId.CONTENT,
        version=1,
    )
    views_change = MetricDefinition(
        metric_id=MetricId.VIDEO_VIEWS_CHANGE,
        platform=PlatformId.TIKTOK,
        entity_scope=EntityScope.CONTENT,
        semantic_type=SemanticType.FLOW,
        unit=Unit.COUNT,
        source_field=None,
        collection_granularity=CollectionGranularity.DAY,
        period_aggregation=AggregationPolicy.SUM,
        brand_rollup_aggregation=AggregationPolicy.SUM,
        null_policy=NullPolicy.NOT_AVAILABLE,
        reset_policy=ResetPolicy.FLAG_AND_WAIT_FOR_NEXT_SAMPLE,
        derived_from_metric_ids=(MetricId.VIDEO_VIEWS_TOTAL,),
        derivation_operator=DerivationOperator.CUMULATIVE_DELTA,
        derivation_version=1,
        derivation_window="utc_day",
        first_sample_policy=FirstSamplePolicy.NOT_AVAILABLE,
        numerator_metric_id=None,
        denominator_metric_id=None,
        zero_denominator_policy=ZeroDenominatorPolicy.NOT_APPLICABLE,
        allowed_breakdowns=(),
        required_capability=CapabilityId.CONTENT,
        version=1,
    )
    counter_fields = (
        (MetricId.VIDEO_LIKES_TOTAL, "like_count"),
        (MetricId.VIDEO_COMMENTS_TOTAL, "comment_count"),
        (MetricId.VIDEO_SHARES_TOTAL, "share_count"),
    )
    engagement_counters = tuple(
        MetricDefinition(
            metric_id=metric_id,
            platform=PlatformId.TIKTOK,
            entity_scope=EntityScope.CONTENT,
            semantic_type=SemanticType.CUMULATIVE,
            unit=Unit.COUNT,
            source_field=source_field,
            collection_granularity=CollectionGranularity.SAMPLE,
            period_aggregation=AggregationPolicy.LAST_VALID,
            brand_rollup_aggregation=AggregationPolicy.SUM,
            null_policy=NullPolicy.NOT_AVAILABLE,
            reset_policy=ResetPolicy.FLAG_AND_WAIT_FOR_NEXT_SAMPLE,
            derived_from_metric_ids=(),
            derivation_operator=None,
            derivation_version=None,
            derivation_window=None,
            first_sample_policy=FirstSamplePolicy.NOT_APPLICABLE,
            numerator_metric_id=None,
            denominator_metric_id=None,
            zero_denominator_policy=ZeroDenominatorPolicy.NOT_APPLICABLE,
            allowed_breakdowns=(),
            required_capability=CapabilityId.CONTENT,
            version=1,
        )
        for metric_id, source_field in counter_fields
    )
    engagements_total = MetricDefinition(
        metric_id=MetricId.VIDEO_ENGAGEMENTS_TOTAL,
        platform=PlatformId.TIKTOK,
        entity_scope=EntityScope.CONTENT,
        semantic_type=SemanticType.CUMULATIVE,
        unit=Unit.COUNT,
        source_field=None,
        collection_granularity=CollectionGranularity.SAMPLE,
        period_aggregation=AggregationPolicy.LAST_VALID,
        brand_rollup_aggregation=AggregationPolicy.SUM,
        null_policy=NullPolicy.NOT_AVAILABLE,
        reset_policy=ResetPolicy.FLAG_AND_WAIT_FOR_NEXT_SAMPLE,
        derived_from_metric_ids=tuple(metric_id for metric_id, _ in counter_fields),
        derivation_operator=DerivationOperator.SUM_COMPONENTS,
        derivation_version=1,
        derivation_window="same_sample",
        first_sample_policy=FirstSamplePolicy.NOT_APPLICABLE,
        numerator_metric_id=None,
        denominator_metric_id=None,
        zero_denominator_policy=ZeroDenominatorPolicy.NOT_APPLICABLE,
        allowed_breakdowns=(),
        required_capability=CapabilityId.CONTENT,
        version=1,
    )
    engagement_rate = MetricDefinition(
        metric_id=MetricId.VIDEO_ENGAGEMENT_RATE,
        platform=PlatformId.TIKTOK,
        entity_scope=EntityScope.CONTENT,
        semantic_type=SemanticType.RATIO,
        unit=Unit.RATIO,
        source_field=None,
        collection_granularity=CollectionGranularity.SAMPLE,
        period_aggregation=AggregationPolicy.RECOMPUTE,
        brand_rollup_aggregation=AggregationPolicy.RECOMPUTE,
        null_policy=NullPolicy.NOT_AVAILABLE,
        reset_policy=ResetPolicy.NOT_APPLICABLE,
        derived_from_metric_ids=(
            MetricId.VIDEO_ENGAGEMENTS_TOTAL,
            MetricId.VIDEO_VIEWS_TOTAL,
        ),
        derivation_operator=DerivationOperator.RATIO_FROM_COMPONENTS,
        derivation_version=1,
        derivation_window="same_sample",
        first_sample_policy=FirstSamplePolicy.NOT_APPLICABLE,
        numerator_metric_id=MetricId.VIDEO_ENGAGEMENTS_TOTAL,
        denominator_metric_id=MetricId.VIDEO_VIEWS_TOTAL,
        zero_denominator_policy=ZeroDenominatorPolicy.NOT_AVAILABLE,
        allowed_breakdowns=(),
        required_capability=CapabilityId.CONTENT,
        version=1,
    )
    return MetricCatalog(
        (
            _profile_snapshot(
                PlatformId.FACEBOOK,
                MetricId.FOLLOWERS,
                "followers_count",
                allowed_breakdowns=("page_fans_country", "page_fans_city"),
            ),
            _profile_cumulative_delta(
                PlatformId.FACEBOOK,
                MetricId.NEW_FOLLOWERS,
                MetricId.FOLLOWERS,
            ),
            _profile_flow(PlatformId.FACEBOOK, MetricId.FOLLOWS, "follows"),
            _profile_flow(PlatformId.FACEBOOK, MetricId.UNFOLLOWS, "unfollows"),
            _profile_flow(PlatformId.FACEBOOK, MetricId.FOLLOWERS_NET, "followers_net"),
            _profile_flow(PlatformId.FACEBOOK, MetricId.VIEWS_ORGANIC, "views_organic"),
            _profile_flow(PlatformId.FACEBOOK, MetricId.VIEWS_PAID, "views_paid"),
            _profile_flow(PlatformId.FACEBOOK, MetricId.REACH_ORGANIC, "reach_organic"),
            _profile_flow(PlatformId.FACEBOOK, MetricId.REACH_PAID, "reach_paid"),
            *(
                _profile_flow(PlatformId.FACEBOOK, metric_id, source_field)
                for metric_id, source_field in {
                    metric_id: source_field
                    for source_field, metric_id in FACEBOOK_DAILY_SOURCE_METRICS
                }.items()
            ),
            _profile_ratio(
                PlatformId.FACEBOOK,
                MetricId.ENGAGEMENT_RATE,
                MetricId.INTERACTIONS,
                MetricId.VIEWS,
            ),
            _profile_snapshot(
                PlatformId.INSTAGRAM,
                MetricId.FOLLOWERS,
                "followers_count",
                allowed_breakdowns=(
                    "follower_demographics_country",
                    "follower_demographics_city",
                    "follower_demographics_age",
                    "follower_demographics_gender",
                    "follower_demographics_age_gender",
                    "engaged_audience_demographics_country",
                    "engaged_audience_demographics_city",
                    "engaged_audience_demographics_age",
                    "engaged_audience_demographics_gender",
                    "engaged_audience_demographics_age_gender",
                    "reached_audience_demographics_country",
                    "reached_audience_demographics_city",
                    "reached_audience_demographics_age",
                    "reached_audience_demographics_gender",
                    "reached_audience_demographics_age_gender",
                ),
            ),
            _profile_snapshot(PlatformId.INSTAGRAM, MetricId.FOLLOWING, "follows_count"),
            _profile_snapshot(PlatformId.INSTAGRAM, MetricId.MEDIA_COUNT, "media_count"),
            _profile_cumulative_delta(
                PlatformId.INSTAGRAM,
                MetricId.NEW_FOLLOWERS,
                MetricId.FOLLOWERS,
            ),
            _profile_flow(PlatformId.INSTAGRAM, MetricId.FOLLOWS, "follows"),
            _profile_flow(PlatformId.INSTAGRAM, MetricId.UNFOLLOWS, "unfollows"),
            _profile_flow(PlatformId.INSTAGRAM, MetricId.FOLLOWERS_NET, "followers_net"),
            _profile_flow(PlatformId.INSTAGRAM, MetricId.VIEWS_ORGANIC, "views_organic"),
            _profile_flow(PlatformId.INSTAGRAM, MetricId.VIEWS_PAID, "views_paid"),
            _profile_flow(PlatformId.INSTAGRAM, MetricId.REACH_ORGANIC, "reach_organic"),
            _profile_flow(PlatformId.INSTAGRAM, MetricId.REACH_PAID, "reach_paid"),
            *(
                _profile_flow(PlatformId.INSTAGRAM, metric_id, source_field)
                for source_field, metric_id in INSTAGRAM_DAILY_SOURCE_METRICS
            ),
            _profile_ratio(
                PlatformId.INSTAGRAM,
                MetricId.ENGAGEMENT_RATE,
                MetricId.INTERACTIONS,
                MetricId.VIEWS,
            ),
            _profile_snapshot(
                PlatformId.TIKTOK,
                MetricId.FOLLOWERS,
                "followers_count",
                allowed_breakdowns=(
                    "audience_countries",
                    "audience_genders",
                    "audience_ages",
                    "audience_activity",
                ),
            ),
            _profile_cumulative_delta(
                PlatformId.TIKTOK,
                MetricId.NEW_FOLLOWERS,
                MetricId.FOLLOWERS,
            ),
            _profile_snapshot(PlatformId.TIKTOK, MetricId.FOLLOWING, "following_count"),
            _profile_flow(PlatformId.TIKTOK, MetricId.FOLLOWS, "follows"),
            _profile_flow(PlatformId.TIKTOK, MetricId.UNFOLLOWS, "unfollows"),
            _profile_flow(PlatformId.TIKTOK, MetricId.FOLLOWERS_NET, "followers_net"),
            _profile_flow(PlatformId.TIKTOK, MetricId.VIEWS, "views"),
            _profile_flow(PlatformId.TIKTOK, MetricId.REACH, "reach"),
            _profile_flow(PlatformId.TIKTOK, MetricId.PROFILE_VIEWS, "profile_views"),
            _profile_flow(PlatformId.TIKTOK, MetricId.INTERACTIONS, "interactions"),
            views_total,
            views_change,
            *engagement_counters,
            engagements_total,
            engagement_rate,
        )
    )


__all__ = [
    "AggregationPolicy",
    "CollectionGranularity",
    "DerivationOperator",
    "EntityScope",
    "FirstSamplePolicy",
    "FACEBOOK_DAILY_SOURCE_METRICS",
    "INSTAGRAM_DAILY_SOURCE_METRICS",
    "MetricCatalog",
    "MetricCatalogError",
    "MetricDefinition",
    "MetricId",
    "NullPolicy",
    "ResetPolicy",
    "SemanticType",
    "Unit",
    "ZeroDenominatorPolicy",
    "bootstrap_metric_catalog",
]
