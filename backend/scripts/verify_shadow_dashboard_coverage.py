"""Exercise every brand/platform dashboard against a read-only V2 shadow database."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.encoders import jsonable_encoder
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.application.queries import (
    DashboardQuery,
    build_overview_dashboard,
    build_platform_dashboard,
)
from app.domain.metrics import MetricId, bootstrap_metric_catalog
from app.domain.platforms import PlatformId
from app.domain.reporting import ReportingRange
from app.infrastructure.persistence.social_v2 import SocialReportingStore
from app.infrastructure.persistence.social_v2.legacy_metrics import (
    KNOWN_LEGACY_BREAKDOWN_KEYS,
    KNOWN_LEGACY_METRIC_IDS_BY_PLATFORM,
    LegacyMetricDisposition,
    legacy_metric_disposition,
)

EXPECTED_KPIS: dict[PlatformId, frozenset[MetricId]] = {
    PlatformId.FACEBOOK: frozenset(
        {
            MetricId.FOLLOWERS,
            MetricId.NEW_FOLLOWERS,
            MetricId.REACH,
            MetricId.VIEWS,
            MetricId.INTERACTIONS,
            MetricId.ENGAGEMENT_RATE,
        }
    ),
    PlatformId.INSTAGRAM: frozenset(
        {
            MetricId.FOLLOWERS,
            MetricId.NEW_FOLLOWERS,
            MetricId.REACH,
            MetricId.VIEWS,
            MetricId.INTERACTIONS,
            MetricId.ENGAGEMENT_RATE,
        }
    ),
    PlatformId.TIKTOK: frozenset(
        {
            MetricId.FOLLOWERS,
            MetricId.NEW_FOLLOWERS,
            MetricId.VIDEO_VIEWS_TOTAL,
            MetricId.REACH,
            MetricId.VIDEO_ENGAGEMENTS_TOTAL,
            MetricId.VIDEO_ENGAGEMENT_RATE,
        }
    ),
}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-env", type=Path, required=True)
    parser.add_argument("--database-name", required=True)
    parser.add_argument("--expected-brand-count", type=int, required=True)
    return parser.parse_args()


def _env_value(path: Path, key: str) -> str:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip().removeprefix("export ").lstrip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"missing_setting:{key}")


def _inventory(connection) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    pairs = tuple(
        (str(row[0]), str(row[1]))
        for row in connection.execute(
            text(
                """SELECT DISTINCT a.platform, m.metric_id
                   FROM metrics_daily m JOIN assets a ON a.id=m.asset_id
                   ORDER BY a.platform, m.metric_id"""
            )
        )
    )
    dimensions = tuple(
        str(value)
        for value in connection.execute(
            text(
                """SELECT DISTINCT breakdown_key FROM metrics_daily
                   WHERE breakdown_key IS NOT NULL ORDER BY breakdown_key"""
            )
        ).scalars()
    )
    return pairs, dimensions


def main() -> None:
    args = _arguments()
    if args.expected_brand_count < 1:
        raise RuntimeError("expected_brand_count_must_be_positive")
    if not args.database_name.startswith("social_media_v2_shadow_"):
        raise RuntimeError("target_database_must_be_v2_shadow")
    base_url = make_url(_env_value(args.target_env, "SOCIAL_DB_URL"))
    target_url = base_url.set(database=args.database_name)
    if target_url.get_backend_name() != "postgresql":
        raise RuntimeError("postgresql_required")
    engine = create_engine(
        target_url,
        pool_pre_ping=True,
        connect_args={"options": "-c default_transaction_read_only=on"},
    )
    try:
        with engine.connect() as connection:
            if connection.execute(text("SHOW transaction_read_only")).scalar_one() != "on":
                raise RuntimeError("shadow_connection_is_not_read_only")
            brands = tuple(
                (str(row[0]), str(row[1] or ""))
                for row in connection.execute(text("SELECT id, name FROM brands ORDER BY id"))
            )
            if len(brands) != args.expected_brand_count:
                raise RuntimeError(
                    "shadow_brand_count_mismatch:"
                    f"expected={args.expected_brand_count}:actual={len(brands)}"
                )
            end_on = connection.execute(text("SELECT max(date) FROM metrics_daily")).scalar_one()
            if end_on is None:
                raise RuntimeError("shadow_metrics_empty")
            pairs, dimensions = _inventory(connection)

        expected_pairs = {
            (platform.value, metric_id)
            for platform, metric_ids in KNOWN_LEGACY_METRIC_IDS_BY_PLATFORM.items()
            for metric_id in metric_ids
        }
        if set(pairs) != expected_pairs:
            raise RuntimeError("shadow_metric_inventory_changed")
        if set(dimensions) != KNOWN_LEGACY_BREAKDOWN_KEYS:
            raise RuntimeError("shadow_dimension_inventory_changed")
        unknown = tuple(
            (platform, metric_id)
            for platform_value, metric_id in pairs
            if (
                platform := PlatformId(platform_value)
            ) and legacy_metric_disposition(platform, metric_id, None)
            is LegacyMetricDisposition.UNKNOWN
        )
        if unknown:
            raise RuntimeError(f"shadow_metric_policy_missing:{unknown!r}")

        date_range = ReportingRange(
            start_on=end_on - timedelta(days=29),
            end_on=end_on,
            key="last_30_days",
        )
        generated_at = datetime.combine(end_on, datetime.max.time(), tzinfo=UTC)
        store = SocialReportingStore(engine)
        catalog = bootstrap_metric_catalog()
        platform_dashboards = 0
        overviews = 0
        brands_with_metrics = 0
        story_brands = 0
        for brand_id, _brand_name in brands:
            query = DashboardQuery(
                requested_brand_id=brand_id,
                resolved_brand_ids=(brand_id,),
                rollup=False,
                date_range=date_range,
            )
            brand_has_metrics = False
            brand_has_stories = False
            for platform in PlatformId:
                dashboard = build_platform_dashboard(
                    store=store,
                    catalog=catalog,
                    platform=platform,
                    query=query,
                    now=generated_at,
                )
                jsonable_encoder(dashboard)
                if dashboard.meta.requested_brand_id != brand_id:
                    raise RuntimeError("dashboard_brand_scope_mismatch")
                if dashboard.meta.resolved_brand_ids != (brand_id,):
                    raise RuntimeError("dashboard_brand_scope_expanded")
                metric_ids = {row.metric_id for row in dashboard.metrics}
                missing = EXPECTED_KPIS[platform] - metric_ids
                if missing:
                    raise RuntimeError(
                        f"dashboard_kpi_contract_missing:{brand_id}:{platform.value}:{missing!r}"
                    )
                brand_has_metrics |= any(row.value is not None for row in dashboard.metrics)
                brand_has_stories |= bool(dashboard.stories and dashboard.stories.items)
                platform_dashboards += 1
            overview = build_overview_dashboard(
                store=store,
                catalog=catalog,
                query=query,
                now=generated_at,
            )
            jsonable_encoder(overview)
            if overview.meta.resolved_brand_ids != (brand_id,):
                raise RuntimeError("overview_brand_scope_expanded")
            overviews += 1
            brands_with_metrics += int(brand_has_metrics)
            story_brands += int(brand_has_stories)

        print(f"shadow_brands={len(brands)}")
        print(f"shadow_metric_pairs={len(pairs)}")
        print(f"shadow_metric_ids={len({metric_id for _, metric_id in pairs})}")
        print(f"shadow_breakdown_dimensions={len(dimensions)}")
        print(f"shadow_platform_dashboards={platform_dashboards}")
        print(f"shadow_overviews={overviews}")
        print(f"shadow_brands_with_metric_values={brands_with_metrics}")
        print(f"shadow_brands_with_stories={story_brands}")
        print("shadow_dashboard_coverage=verified")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
