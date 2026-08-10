#!/usr/bin/env python3
"""Read-only Pine Beach dashboard and in-memory XLSX certification for Revision 6 / R24."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree
from zipfile import ZipFile

from sqlalchemy import create_engine, event, text

from app.application.queries import (
    DashboardQuery,
    build_overview_dashboard,
    build_platform_dashboard,
    resolve_reporting_range,
)
from app.domain.metrics import MetricId, bootstrap_metric_catalog
from app.domain.platforms import PlatformId
from app.domain.reporting import OverviewDashboard, PlatformDashboard, ReportingRange
from app.infrastructure.persistence.social_v2 import SocialReportingStore
from app.infrastructure.reports import (
    ReportContext,
    build_overview_xlsx,
    build_platform_xlsx,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LOGO_PATH = (
    REPOSITORY_ROOT
    / "frontend"
    / "public"
    / "branding"
    / "accumulate-sidebar-logo.png"
)
AS_OF = datetime(2026, 8, 10, 12, tzinfo=UTC)
PINE_BRAND_ID = "18"
PINE_BRAND_NAME = "Pine Beach Belek"
RANGE_KEYS = ("last_7_days", "last_30_days", "last_90_days", "last_365_days")
RANGE_DAYS = {
    "last_7_days": 7,
    "last_30_days": 30,
    "last_90_days": 90,
    "last_365_days": 365,
}
PRIMARY_METRICS = {
    PlatformId.FACEBOOK: (
        MetricId.FOLLOWERS,
        MetricId.NEW_FOLLOWERS,
        MetricId.REACH,
        MetricId.VIEWS,
        MetricId.INTERACTIONS,
        MetricId.ENGAGEMENT_RATE,
    ),
    PlatformId.INSTAGRAM: (
        MetricId.FOLLOWERS,
        MetricId.NEW_FOLLOWERS,
        MetricId.REACH,
        MetricId.VIEWS,
        MetricId.INTERACTIONS,
        MetricId.ENGAGEMENT_RATE,
    ),
    PlatformId.TIKTOK: (
        MetricId.FOLLOWERS,
        MetricId.VIDEO_VIEWS_TOTAL,
        MetricId.VIDEO_LIKES_TOTAL,
        MetricId.VIDEO_COMMENTS_TOTAL,
        MetricId.VIDEO_SHARES_TOTAL,
        MetricId.VIDEO_ENGAGEMENT_RATE,
    ),
}
FOLLOWER_FLOW = (MetricId.FOLLOWS, MetricId.UNFOLLOWS, MetricId.FOLLOWERS_NET)
EXPECTED_SHEETS = {
    "overview.overview": (
        "Report Info",
        "Data - Performance",
        "Overview",
        "Platform Summary",
        "All Content",
        "Community",
        "Data Dictionary",
    ),
    "facebook.cover": (
        "Report Info",
        "Data - Daily",
        "Page",
        "Content",
        "Audience",
        "All Content",
        "Data - Breakdowns",
        "Community",
        "Data Dictionary",
    ),
    "facebook.page": ("Report Info", "Data - Daily", "Page", "Data Dictionary"),
    "facebook.content": (
        "Report Info",
        "Data - Daily",
        "Content",
        "All Content",
        "Data Dictionary",
    ),
    "facebook.audience": (
        "Report Info",
        "Data - Daily",
        "Audience",
        "Data - Breakdowns",
        "Community",
        "Data Dictionary",
    ),
    "instagram.cover": (
        "Report Info",
        "Data - Daily",
        "Page",
        "Content",
        "Stories",
        "Data - Story Trend",
        "Audience",
        "All Content",
        "Story History",
        "Data - Breakdowns",
        "Community",
        "Data Dictionary",
    ),
    "instagram.page": ("Report Info", "Data - Daily", "Page", "Data Dictionary"),
    "instagram.content": (
        "Report Info",
        "Data - Daily",
        "Content",
        "All Content",
        "Data Dictionary",
    ),
    "instagram.stories": (
        "Report Info",
        "Data - Daily",
        "Stories",
        "Data - Story Trend",
        "Story History",
        "Data Dictionary",
    ),
    "instagram.audience": (
        "Report Info",
        "Data - Daily",
        "Audience",
        "Data - Breakdowns",
        "Community",
        "Data Dictionary",
    ),
    "tiktok.cover": (
        "Report Info",
        "Data - Daily",
        "Account",
        "Content",
        "Audience",
        "All Content",
        "Data - Breakdowns",
        "Community",
        "Data Dictionary",
    ),
    "tiktok.account": ("Report Info", "Data - Daily", "Account", "Data Dictionary"),
    "tiktok.content": (
        "Report Info",
        "Data - Daily",
        "Content",
        "All Content",
        "Data Dictionary",
    ),
    "tiktok.audience": (
        "Report Info",
        "Data - Daily",
        "Audience",
        "Data - Breakdowns",
        "Community",
        "Data Dictionary",
    ),
}
EXPECTED_CHARTS = {
    "overview.overview": 1,
    "facebook.cover": 7,
    "facebook.page": 3,
    "facebook.content": 2,
    "facebook.audience": 2,
    "instagram.cover": 8,
    "instagram.page": 3,
    "instagram.content": 2,
    "instagram.stories": 1,
    "instagram.audience": 2,
    "tiktok.cover": 7,
    "tiktok.account": 3,
    "tiktok.content": 2,
    "tiktok.audience": 2,
}
PLATFORM_TABS = {
    PlatformId.FACEBOOK: ("cover", "page", "content", "audience"),
    PlatformId.INSTAGRAM: ("cover", "page", "content", "stories", "audience"),
    PlatformId.TIKTOK: ("cover", "account", "content", "audience"),
}
XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "office_rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RuntimeError(code)


def _read_only_engine():
    database_url = os.environ.get("SOCIAL_DB_URL", "").strip()
    _require(bool(database_url), "social_db_url_missing")
    parsed = urlparse(database_url.replace("postgresql+psycopg", "postgresql", 1))
    _require(parsed.hostname in {"127.0.0.1", "localhost", "::1"}, "non_local_database_denied")
    _require(parsed.path.lstrip("/").startswith("social_media_v2"), "non_v2_database_denied")
    engine = create_engine(database_url, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def set_read_only(dbapi_connection, _record) -> None:
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET default_transaction_read_only = on")

    with engine.connect() as connection:
        _require(
            connection.execute(text("SHOW default_transaction_read_only")).scalar_one() == "on",
            "read_only_connection_required",
        )
    return engine


def _metric_map(dashboard: PlatformDashboard) -> dict[MetricId, Any]:
    return {item.metric_id: item for item in dashboard.metrics}


def _series_map(dashboard: PlatformDashboard) -> dict[MetricId, Any]:
    return {item.metric_id: item for item in dashboard.series}


def _assert_metric_semantics(dashboard: PlatformDashboard) -> None:
    metrics = _metric_map(dashboard)
    for metric_id in PRIMARY_METRICS[dashboard.meta.platform]:
        _require(metric_id in metrics, f"primary_metric_missing:{dashboard.meta.dashboard_id}:{metric_id}")
        _require(
            metrics[metric_id].value is not None,
            f"primary_metric_empty:{dashboard.meta.dashboard_id}:{metric_id}",
        )
    series = _series_map(dashboard)
    for metric_id in FOLLOWER_FLOW:
        _require(metric_id in series, f"follower_flow_missing:{dashboard.meta.dashboard_id}:{metric_id}")
        _require(bool(series[metric_id].points), f"follower_flow_empty:{dashboard.meta.dashboard_id}:{metric_id}")
    for item in dashboard.series:
        _require(
            all(
                dashboard.meta.date_range.start_on
                <= point.observed_on
                <= dashboard.meta.date_range.end_on
                for point in item.points
            ),
            f"series_outside_range:{dashboard.meta.dashboard_id}:{item.metric_id}",
        )
    for breakdown in dashboard.breakdowns:
        percentages = [item.percentage for item in breakdown.items if item.percentage is not None]
        if percentages:
            _require(
                abs(sum(percentages) - 100) < 1e-6,
                f"breakdown_percentage_invalid:{dashboard.meta.dashboard_id}:{breakdown.dimension}",
            )
    if dashboard.meta.platform in {PlatformId.FACEBOOK, PlatformId.INSTAGRAM}:
        numerator = metrics[MetricId.INTERACTIONS].value
        denominator = metrics[MetricId.VIEWS].value
        rate = metrics[MetricId.ENGAGEMENT_RATE].value
    else:
        numerator = metrics[MetricId.VIDEO_ENGAGEMENTS_TOTAL].value
        denominator = metrics[MetricId.VIDEO_VIEWS_TOTAL].value
        rate = metrics[MetricId.VIDEO_ENGAGEMENT_RATE].value
    _require(
        denominator is not None and denominator > 0 and numerator is not None and rate is not None,
        f"engagement_components_missing:{dashboard.meta.dashboard_id}",
    )
    _require(
        abs(rate - (numerator / denominator)) < 1e-12,
        f"engagement_rate_mismatch:{dashboard.meta.dashboard_id}",
    )
    for content in dashboard.content:
        _require(bool(content.content_type.strip()), "content_type_empty")
        _require(content.likes_count >= 0, "content_likes_negative")
        _require(content.comments_count >= 0, "content_comments_negative")
        _require(content.shares_count >= 0, "content_shares_negative")
        _require(content.interactions >= 0, "content_interactions_negative")
    if dashboard.stories is not None:
        for story in dashboard.stories.items:
            if story.completion_rate is not None:
                _require(0 <= story.completion_rate <= 100, "story_completion_percent_invalid")


def _assert_overview_totals(dashboard: OverviewDashboard) -> None:
    for metric in dashboard.metrics:
        platform_values = [
            item.value
            for platform in dashboard.platforms
            for item in platform.metrics
            if item.metric_id is metric.metric_id and item.value is not None
        ]
        expected = sum(platform_values) if platform_values else None
        _require(metric.value == expected, f"overview_total_mismatch:{metric.metric_id}")


def _sheet_rows(archive: ZipFile, sheet_name: str) -> list[dict[str, str]]:
    shared: list[str] = []
    if "xl/sharedStrings.xml" in archive.namelist():
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = [
            "".join(node.text or "" for node in item.findall(".//main:t", XML_NS))
            for item in root.findall("main:si", XML_NS)
        ]
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
    sheet = next(
        item
        for item in workbook.findall("main:sheets/main:sheet", XML_NS)
        if item.attrib["name"] == sheet_name
    )
    relation_id = sheet.attrib[f"{{{XML_NS['office_rel']}}}id"]
    target = targets[relation_id]
    path = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
    root = ElementTree.fromstring(archive.read(path))
    result: list[dict[str, str]] = []
    for row in root.findall(".//main:sheetData/main:row", XML_NS):
        values: dict[str, str] = {"__row__": row.attrib["r"]}
        for cell in row.findall("main:c", XML_NS):
            column = re.match(r"[A-Z]+", cell.attrib["r"])
            if column is None:
                continue
            value_node = cell.find("main:v", XML_NS)
            value = "" if value_node is None or value_node.text is None else value_node.text
            if cell.attrib.get("t") == "s" and value:
                value = shared[int(value)]
            elif cell.attrib.get("t") == "inlineStr":
                value = "".join(
                    node.text or "" for node in cell.findall(".//main:t", XML_NS)
                )
            values[column.group()] = value
        result.append(values)
    return result


def _sheet_names(archive: ZipFile) -> tuple[str, ...]:
    root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    return tuple(
        item.attrib["name"] for item in root.findall("main:sheets/main:sheet", XML_NS)
    )


def _float(value: str) -> float | None:
    if not value or value in {"Not provided", "—"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _assert_content_sheet(archive: ZipFile, dashboard: PlatformDashboard | OverviewDashboard) -> None:
    if "All Content" not in _sheet_names(archive):
        return
    rows = _sheet_rows(archive, "All Content")
    data_rows = [
        row
        for row in rows
        if int(row["__row__"]) >= 6 and row.get("B") and row.get("B") != "Content ID"
    ]
    content = tuple(
        item for item in dashboard.content if "story" not in item.content_type.lower()
    )
    _require(len(data_rows) == len(content), "xlsx_content_row_count_mismatch")
    expected = {
        "F": sum(item.views or 0 for item in content),
        "G": sum(item.reach or 0 for item in content),
        "H": sum(item.likes_count for item in content),
        "I": sum(item.comments_count for item in content),
        "J": sum(item.shares_count for item in content),
        "K": sum(item.interactions for item in content),
    }
    for column, total in expected.items():
        actual = sum(value for row in data_rows if (value := _float(row.get(column, ""))) is not None)
        _require(abs(actual - total) < 1e-6, f"xlsx_content_total_mismatch:{column}")


def _assert_story_sheet(archive: ZipFile, dashboard: PlatformDashboard) -> None:
    if "Story History" not in _sheet_names(archive):
        return
    rows = _sheet_rows(archive, "Story History")
    data_rows = [
        row
        for row in rows
        if int(row["__row__"]) >= 6 and row.get("B") and row.get("B") != "Story ID"
    ]
    stories = dashboard.stories.items if dashboard.stories is not None else ()
    _require(len(data_rows) == len(stories), "xlsx_story_row_count_mismatch")
    expected_interactions = sum(item.interactions or 0 for item in stories)
    actual_interactions = sum(
        value for row in data_rows if (value := _float(row.get("G", ""))) is not None
    )
    _require(
        abs(actual_interactions - expected_interactions) < 1e-6,
        "xlsx_story_total_mismatch",
    )


def _assert_daily_sheet(archive: ZipFile, dashboard: PlatformDashboard) -> None:
    rows = _sheet_rows(archive, "Data - Daily")
    header = next(row for row in rows if "Followers" in row.values())
    followers_column = next(column for column, value in header.items() if value == "Followers")
    data_rows = [row for row in rows if _float(row.get("B", "")) is not None]
    series = _series_map(dashboard)[MetricId.FOLLOWERS]
    _require(len(data_rows) == dashboard.meta.expected_days, "xlsx_daily_date_count_mismatch")
    _require(
        _float(data_rows[-1].get(followers_column, "")) == series.points[-1].value,
        "xlsx_daily_followers_mismatch",
    )


def _assert_workbook(
    *,
    key: str,
    blob: bytes,
    dashboard: PlatformDashboard | OverviewDashboard,
) -> dict[str, Any]:
    expected_logo = LOGO_PATH.read_bytes()
    with ZipFile(BytesIO(blob)) as archive:
        names = set(archive.namelist())
        sheets = _sheet_names(archive)
        _require(sheets == EXPECTED_SHEETS[key], f"xlsx_sheet_set_mismatch:{key}")
        media = sorted(name for name in names if name.startswith("xl/media/"))
        _require(len(media) == 1, f"xlsx_logo_count_mismatch:{key}")
        _require(archive.read(media[0]) == expected_logo, f"xlsx_logo_mismatch:{key}")
        _require(not any(name.startswith("xl/externalLinks/") for name in names), "xlsx_external_link")
        _require(not any(name.endswith("vbaProject.bin") for name in names), "xlsx_macro")
        worksheet_xml = b"".join(
            archive.read(name)
            for name in names
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        _require(b"<f" not in worksheet_xml, f"xlsx_formula_present:{key}")
        _require(b"#REF!" not in worksheet_xml, f"xlsx_ref_error:{key}")
        _require(b"#VALUE!" not in worksheet_xml, f"xlsx_value_error:{key}")
        charts = [name for name in names if name.startswith("xl/charts/chart")]
        _require(len(charts) == EXPECTED_CHARTS[key], f"xlsx_chart_count_mismatch:{key}")
        report_info = " ".join(value for row in _sheet_rows(archive, "Report Info") for value in row.values())
        _require(PINE_BRAND_NAME in report_info, f"xlsx_brand_missing:{key}")
        _require("11 Jul 2026 – 09 Aug 2026" in report_info, f"xlsx_period_missing:{key}")
        _assert_content_sheet(archive, dashboard)
        if isinstance(dashboard, PlatformDashboard):
            _assert_daily_sheet(archive, dashboard)
            _assert_story_sheet(archive, dashboard)
    return {
        "bytes": len(blob),
        "charts": EXPECTED_CHARTS[key],
        "sheets": len(EXPECTED_SHEETS[key]),
        "sha256": hashlib.sha256(blob).hexdigest(),
    }


def _platform_query(date_range: ReportingRange, platform: PlatformId, tab: str) -> DashboardQuery:
    return DashboardQuery(
        requested_brand_id=PINE_BRAND_ID,
        resolved_brand_ids=(PINE_BRAND_ID,),
        rollup=False,
        date_range=date_range,
        content_type="story" if tab == "stories" else None,
        excluded_content_types=(
            ("story",) if platform is PlatformId.INSTAGRAM and tab == "content" else ()
        ),
    )


def main() -> None:
    engine = _read_only_engine()
    store = SocialReportingStore(engine)
    catalog = bootstrap_metric_catalog()
    result: dict[str, Any] = {
        "artifact": "revision6_r24_data_xlsx_certification",
        "status": "passed",
        "brand": {"id": PINE_BRAND_ID, "name": PINE_BRAND_NAME},
        "date_ranges": {},
        "accounts": {},
        "rollup": {},
        "xlsx": {},
        "critical_findings": [],
        "high_findings": [],
    }
    try:
        with engine.connect() as connection:
            brand = connection.execute(
                text("SELECT CAST(id AS text), name FROM brands WHERE id=:brand_id AND active"),
                {"brand_id": int(PINE_BRAND_ID)},
            ).one()
            _require(brand == (PINE_BRAND_ID, PINE_BRAND_NAME), "pine_brand_identity_mismatch")

        dashboards_by_range: dict[str, dict[PlatformId, PlatformDashboard]] = {}
        for range_key in RANGE_KEYS:
            date_range = resolve_reporting_range(
                range_key=range_key,
                start_on=None,
                end_on=None,
                now=AS_OF,
            )
            _require(
                (date_range.end_on - date_range.start_on).days + 1 == RANGE_DAYS[range_key],
                f"range_length_mismatch:{range_key}",
            )
            query = DashboardQuery(
                requested_brand_id=PINE_BRAND_ID,
                resolved_brand_ids=(PINE_BRAND_ID,),
                rollup=False,
                date_range=date_range,
            )
            overview = build_overview_dashboard(
                store=store,
                catalog=catalog,
                query=query,
                now=AS_OF,
            )
            _assert_overview_totals(overview)
            platform_results: dict[PlatformId, PlatformDashboard] = {}
            range_result: dict[str, Any] = {
                "start_on": date_range.start_on.isoformat(),
                "end_on": date_range.end_on.isoformat(),
                "overview_status": overview.meta.data_status.value,
                "platforms": {},
            }
            for platform in PlatformId:
                dashboard = build_platform_dashboard(
                    store=store,
                    catalog=catalog,
                    platform=platform,
                    query=query,
                    now=AS_OF,
                )
                _assert_metric_semantics(dashboard)
                if range_key in {"last_7_days", "last_30_days", "last_90_days"}:
                    for metric_id in FOLLOWER_FLOW:
                        _require(
                            len(_series_map(dashboard)[metric_id].points) == RANGE_DAYS[range_key],
                            f"follower_flow_coverage_mismatch:{platform}:{range_key}:{metric_id}",
                        )
                if platform is PlatformId.TIKTOK and range_key == "last_30_days":
                    for metric_id in (MetricId.VIEWS, MetricId.REACH):
                        _require(
                            len(_series_map(dashboard)[metric_id].points) == 30,
                            f"tiktok_performance_period_mismatch:{metric_id}",
                        )
                platform_results[platform] = dashboard
                range_result["platforms"][platform.value] = {
                    "status": dashboard.meta.data_status.value,
                    "observed_days": dashboard.meta.observed_days,
                    "expected_days": dashboard.meta.expected_days,
                    "metrics": len(dashboard.metrics),
                    "series": len(dashboard.series),
                    "breakdowns": len(dashboard.breakdowns),
                    "content": len(dashboard.content),
                    "stories": len(dashboard.stories.items) if dashboard.stories else 0,
                }
            dashboards_by_range[range_key] = platform_results
            result["date_ranges"][range_key] = range_result

        last_30 = resolve_reporting_range(
            range_key="last_30_days", start_on=None, end_on=None, now=AS_OF
        )
        accounts: dict[PlatformId, tuple[Any, ...]] = {}
        for platform in PlatformId:
            rows = store.list_accounts(brand_ids=(PINE_BRAND_ID,), platform=platform)
            _require(bool(rows), f"account_missing:{platform}")
            accounts[platform] = rows
            for account in rows:
                dashboard = build_platform_dashboard(
                    store=store,
                    catalog=catalog,
                    platform=platform,
                    query=DashboardQuery(
                        requested_brand_id=PINE_BRAND_ID,
                        resolved_brand_ids=(PINE_BRAND_ID,),
                        rollup=False,
                        date_range=last_30,
                        account_id=account.account_id,
                    ),
                    now=AS_OF,
                )
                _require(
                    dashboard.meta.resolved_account_ids == (account.account_id,),
                    f"account_selection_mismatch:{platform}:{account.account_id}",
                )
            result["accounts"][platform.value] = [row.account_id for row in rows]
        wrong_account = accounts[PlatformId.INSTAGRAM][0].account_id
        try:
            build_platform_dashboard(
                store=store,
                catalog=catalog,
                platform=PlatformId.FACEBOOK,
                query=DashboardQuery(
                    requested_brand_id=PINE_BRAND_ID,
                    resolved_brand_ids=(PINE_BRAND_ID,),
                    rollup=False,
                    date_range=last_30,
                    account_id=wrong_account,
                ),
                now=AS_OF,
            )
        except ValueError as exc:
            _require(str(exc) == "dashboard_account_scope_denied", "wrong_account_error_mismatch")
        else:
            raise RuntimeError("cross_platform_account_scope_allowed")

        instagram_cover = dashboards_by_range["last_30_days"][PlatformId.INSTAGRAM]
        instagram_content = build_platform_dashboard(
            store=store,
            catalog=catalog,
            platform=PlatformId.INSTAGRAM,
            query=_platform_query(last_30, PlatformId.INSTAGRAM, "content"),
            now=AS_OF,
        )
        instagram_stories = build_platform_dashboard(
            store=store,
            catalog=catalog,
            platform=PlatformId.INSTAGRAM,
            query=_platform_query(last_30, PlatformId.INSTAGRAM, "stories"),
            now=AS_OF,
        )
        _require(
            all(item.content_type.lower() != "story" for item in instagram_content.content),
            "instagram_content_contains_story",
        )
        _require(
            all(item.content_type.lower() == "story" for item in instagram_stories.content),
            "instagram_stories_contains_non_story",
        )
        _require(
            len(instagram_cover.content)
            == len(instagram_content.content) + len(instagram_stories.content),
            "instagram_cover_content_partition_mismatch",
        )

        with engine.connect() as connection:
            rollup_ids = tuple(
                connection.execute(
                    text(
                        """SELECT CAST(id AS text) FROM brands
                        WHERE active AND (id=19 OR parent_brand_id=19) ORDER BY id"""
                    )
                ).scalars()
            )
        _require(rollup_ids == ("19", "28", "29", "30"), "rollup_brand_set_mismatch")
        rollup_query = DashboardQuery("19", rollup_ids, True, last_30)
        rollup_overview = build_overview_dashboard(
            store=store, catalog=catalog, query=rollup_query, now=AS_OF
        )
        _require(rollup_overview.meta.rollup, "rollup_flag_missing")
        _require(rollup_overview.meta.resolved_brand_ids == rollup_ids, "rollup_scope_mismatch")
        exact_parent = build_overview_dashboard(
            store=store,
            catalog=catalog,
            query=DashboardQuery("19", ("19",), False, last_30),
            now=AS_OF,
        )
        _require(not exact_parent.meta.rollup, "exact_parent_marked_rollup")
        _require(
            set(exact_parent.meta.resolved_account_ids).issubset(
                set(rollup_overview.meta.resolved_account_ids)
            ),
            "rollup_account_union_invalid",
        )
        result["rollup"] = {
            "requested_brand_id": "19",
            "resolved_brand_ids": list(rollup_ids),
            "exact_accounts": list(exact_parent.meta.resolved_account_ids),
            "rollup_accounts": list(rollup_overview.meta.resolved_account_ids),
        }

        overview_query = DashboardQuery(PINE_BRAND_ID, (PINE_BRAND_ID,), False, last_30)
        overview = build_overview_dashboard(
            store=store, catalog=catalog, query=overview_query, now=AS_OF
        )
        overview_artifact = build_overview_xlsx(
            dashboard=overview,
            context=ReportContext(
                brand_name=PINE_BRAND_NAME,
                account_name="All accounts",
                surface="overview",
                tab="overview",
                rollup=False,
            ),
            progress=lambda _value, _stage: None,
        )
        result["xlsx"]["overview.overview"] = _assert_workbook(
            key="overview.overview",
            blob=overview_artifact.content,
            dashboard=overview,
        )
        for platform in PlatformId:
            account_name = ", ".join(row.display_name for row in accounts[platform])
            for tab in PLATFORM_TABS[platform]:
                dashboard = build_platform_dashboard(
                    store=store,
                    catalog=catalog,
                    platform=platform,
                    query=_platform_query(last_30, platform, tab),
                    now=AS_OF,
                )
                artifact = build_platform_xlsx(
                    dashboard=dashboard,
                    context=ReportContext(
                        brand_name=PINE_BRAND_NAME,
                        account_name=account_name,
                        surface=platform.value,
                        tab=tab,
                        rollup=False,
                    ),
                    progress=lambda _value, _stage: None,
                )
                key = f"{platform.value}.{tab}"
                result["xlsx"][key] = _assert_workbook(
                    key=key,
                    blob=artifact.content,
                    dashboard=dashboard,
                )
        result["xlsx_summary"] = {
            "workbooks": len(result["xlsx"]),
            "total_sheets": sum(item["sheets"] for item in result["xlsx"].values()),
            "total_charts": sum(item["charts"] for item in result["xlsx"].values()),
            "persistent_artifacts": 0,
            "logo_sha256": hashlib.sha256(LOGO_PATH.read_bytes()).hexdigest(),
        }
    finally:
        engine.dispose()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
