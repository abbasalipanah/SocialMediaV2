"""Fail closed when the active V2 Demo Company snapshot is incomplete."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.application.queries import (  # noqa: E402
    DashboardQuery,
    build_platform_dashboard,
    resolve_reporting_range,
)
from app.core import load_settings  # noqa: E402
from app.domain.metrics import bootstrap_metric_catalog  # noqa: E402
from app.domain.platforms import PlatformId  # noqa: E402
from app.infrastructure.persistence.social_v2 import SocialReportingStore  # noqa: E402

REQUIRED_BREAKDOWNS = {
    PlatformId.FACEBOOK: {
        "audience_countries",
        "audience_cities",
        "audience_ages",
        "audience_genders",
        "audience_activity",
        "best_time_to_engage",
    },
    PlatformId.INSTAGRAM: {
        "audience_countries",
        "audience_cities",
        "audience_ages",
        "audience_genders",
        "audience_activity",
        "best_time_to_engage",
    },
    PlatformId.TIKTOK: {
        "audience_countries",
        "audience_ages",
        "audience_genders",
        "audience_activity",
        "best_time_to_engage",
    },
}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand-id", default="286284")
    parser.add_argument("--brand-name", default="Demo Company")
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    settings = load_settings()
    if not settings.db.url or not settings.db.resolved_name.startswith("social_media_v2"):
        raise RuntimeError("v2_database_required")

    engine = create_engine(settings.db.url, pool_pre_ping=True)
    store = SocialReportingStore(engine)
    catalog = bootstrap_metric_catalog()
    now = datetime.now(UTC)
    date_range = resolve_reporting_range(
        range_key="last_30_days",
        start_on=None,
        end_on=None,
        now=now,
    )
    query = DashboardQuery(
        requested_brand_id=str(args.brand_id),
        resolved_brand_ids=(str(args.brand_id),),
        rollup=False,
        date_range=date_range,
    )
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text("SET TRANSACTION READ ONLY"))
            brand = connection.execute(
                text("SELECT name, active FROM brands WHERE id=:brand_id"),
                {"brand_id": int(args.brand_id)},
            ).one_or_none()
            transaction.rollback()
        if brand != (str(args.brand_name), True):
            raise RuntimeError(f"demo_brand_mismatch:{brand!r}")

        for platform in PlatformId:
            dashboard = build_platform_dashboard(
                store=store,
                catalog=catalog,
                platform=platform,
                query=query,
                now=now,
            )
            unavailable = [
                item.metric_id.value
                for item in dashboard.metrics
                if item.data_status.value != "available"
            ]
            dimensions = {item.dimension for item in dashboard.breakdowns}
            missing = REQUIRED_BREAKDOWNS[platform] - dimensions
            if (
                dashboard.meta.data_status.value != "available"
                or dashboard.meta.warnings
                or dashboard.meta.observed_days != dashboard.meta.expected_days
                or unavailable
                or missing
            ):
                raise RuntimeError(
                    f"demo_dashboard_incomplete:{platform.value}:"
                    f"status={dashboard.meta.data_status.value}:"
                    f"warnings={dashboard.meta.warnings}:"
                    f"days={dashboard.meta.observed_days}/{dashboard.meta.expected_days}:"
                    f"unavailable={unavailable}:"
                    f"breakdowns={sorted(dimensions)}:missing={sorted(missing)}"
                )
            print(
                f"{platform.value}=available:"
                f"days={dashboard.meta.observed_days}/{dashboard.meta.expected_days}:"
                f"breakdowns={len(dimensions)}"
            )

        insights = store.list_insights(brand_ids=(str(args.brand_id),))
        insight = next(
            (
                item
                for item in insights
                if item.status == "completed"
                and item.summary
                and item.recommendations
                and item.platform_evaluations
            ),
            None,
        )
        if insight is None or insight.date_to != date_range.end_on:
            raise RuntimeError("demo_ai_summary_incomplete")
        print(
            f"ai_summary=completed:insight_id={insight.insight_id}:"
            f"through={insight.date_to}"
        )
    finally:
        engine.dispose()

    print("demo_company_v2_snapshot=verified")


if __name__ == "__main__":
    main()
