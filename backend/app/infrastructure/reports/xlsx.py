"""Professional XLSX workbooks rendered from canonical dashboard projections."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import xlsxwriter

from app.application.services.report_exports import ReportArtifact
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.domain.reporting import (
    DashboardContent,
    DashboardMetric,
    DashboardPoint,
    DashboardSeries,
    OverviewDashboard,
    PlatformDashboard,
)

Progress = Callable[[int, str], None]

PALETTE = {
    "ink": "#14213D",
    "muted": "#64748B",
    "border": "#E2E8F0",
    "surface": "#FFFFFF",
    "canvas": "#F7F9FC",
    "purple": "#5B3DF5",
    MetricId.FOLLOWERS.value: "#38BDF8",
    MetricId.FOLLOWS.value: "#3B82F6",
    MetricId.UNFOLLOWS.value: "#F59E0B",
    "net": "#14B8A6",
    MetricId.VIEWS.value: "#5EEAD4",
    MetricId.REACH.value: "#EC4899",
    "organic": "#8357F6",
    "paid": "#F59E0B",
    "organic_views": "#3B82F6",
    "organic_reach": "#6366F1",
    "likes": "#EF5DA8",
    "comments": "#3B82F6",
    "shares": "#22C55E",
    "positive": "#16A36A",
    "negative": "#E5484D",
}

METRIC_LABELS = {
    MetricId.FOLLOWERS.value: "Followers",
    MetricId.NEW_FOLLOWERS.value: "New Followers",
    MetricId.FOLLOWS.value: "Follows",
    MetricId.UNFOLLOWS.value: "Unfollows",
    MetricId.FOLLOWERS_NET.value: "Net",
    MetricId.REACH.value: "Reach",
    MetricId.REACH_PAID.value: "Paid Reach",
    MetricId.REACH_ORGANIC.value: "Organic Reach",
    MetricId.VIEWS.value: "Views",
    MetricId.VIEWS_PAID.value: "Paid Views",
    MetricId.VIEWS_ORGANIC.value: "Organic Views",
    MetricId.INTERACTIONS.value: "Interactions",
    MetricId.ENGAGEMENT_RATE.value: "Engagement Rate",
    MetricId.PAGE_VIEWS.value: "Page Views",
    MetricId.PROFILE_VIEWS.value: "Profile Views",
    MetricId.WEBSITE_CLICKS.value: "Website Clicks",
    MetricId.TOTAL_ACTIONS.value: "Total Actions",
    MetricId.REACTIONS.value: "Reactions",
    MetricId.MEDIA_COUNT.value: "Published Content",
    MetricId.VIDEO_VIEWS_TOTAL.value: "Video Views",
    MetricId.VIDEO_LIKES_TOTAL.value: "Video Likes",
    MetricId.VIDEO_COMMENTS_TOTAL.value: "Video Comments",
    MetricId.VIDEO_SHARES_TOTAL.value: "Video Shares",
    MetricId.VIDEO_ENGAGEMENTS_TOTAL.value: "Video Interactions",
    MetricId.VIDEO_ENGAGEMENT_RATE.value: "Video Engagement Rate",
}

PLATFORM_COLORS = {
    PlatformId.INSTAGRAM: "#EC4899",
    PlatformId.FACEBOOK: "#2563EB",
    PlatformId.TIKTOK: "#14213D",
}

CHART_KEYS = {
    MetricId.FOLLOWERS.value: ("Followers", PALETTE[MetricId.FOLLOWERS.value]),
    MetricId.FOLLOWS.value: ("Follows", PALETTE[MetricId.FOLLOWS.value]),
    MetricId.UNFOLLOWS.value: ("Unfollows", PALETTE[MetricId.UNFOLLOWS.value]),
    MetricId.FOLLOWERS_NET.value: ("Net", PALETTE["net"]),
    MetricId.VIEWS.value: ("Views", PALETTE[MetricId.VIEWS.value]),
    MetricId.REACH.value: ("Reach", PALETTE[MetricId.REACH.value]),
    MetricId.VIEWS_ORGANIC.value: ("Organic Views", PALETTE["organic_views"]),
    MetricId.VIEWS_PAID.value: ("Paid Views", PALETTE["paid"]),
    MetricId.REACH_ORGANIC.value: ("Organic Reach", PALETTE["organic_reach"]),
    MetricId.REACH_PAID.value: ("Paid Reach", PALETTE["paid"]),
    MetricId.INTERACTIONS.value: ("Interactions", PALETTE[MetricId.UNFOLLOWS.value]),
    MetricId.VIDEO_LIKES_TOTAL.value: ("Likes", PALETTE["likes"]),
    MetricId.VIDEO_COMMENTS_TOTAL.value: ("Comments", PALETTE["comments"]),
    MetricId.VIDEO_SHARES_TOTAL.value: ("Shares", PALETTE["shares"]),
    "instagram_performance": ("Instagram", PLATFORM_COLORS[PlatformId.INSTAGRAM]),
    "facebook_performance": ("Facebook", PLATFORM_COLORS[PlatformId.FACEBOOK]),
    "tiktok_performance": ("TikTok", PLATFORM_COLORS[PlatformId.TIKTOK]),
}

_RELEASE_ROOT = Path(__file__).resolve().parents[4]
_LOGO_PATHS = (
    _RELEASE_ROOT
    / "frontend"
    / "public"
    / "branding"
    / "accumulate-sidebar-logo.png",
    _RELEASE_ROOT
    / "frontend"
    / "dist"
    / "branding"
    / "accumulate-sidebar-logo.png",
)


@dataclass(frozen=True)
class ReportContext:
    brand_name: str
    account_name: str
    surface: str
    tab: str
    rollup: bool
    export_version: str = "social-media-v2-r21"


@dataclass(frozen=True)
class _ChartData:
    sheet_name: str
    columns: dict[str, int]
    rows: int


class _Formats:
    def __init__(self, workbook: xlsxwriter.Workbook) -> None:
        base = {"font_name": "Inter", "font_color": PALETTE["ink"]}
        self.title = workbook.add_format({**base, "font_size": 20, "bold": True})
        self.subtitle = workbook.add_format(
            {**base, "font_size": 10, "font_color": PALETTE["muted"]}
        )
        self.section = workbook.add_format({**base, "font_size": 13, "bold": True})
        self.label = workbook.add_format(
            {**base, "font_size": 9, "bold": True, "font_color": PALETTE["muted"]}
        )
        self.value = workbook.add_format({**base, "font_size": 18, "bold": True})
        self.delta = workbook.add_format(
            {**base, "font_size": 9, "font_color": PALETTE["positive"]}
        )
        self.delta_down = workbook.add_format(
            {**base, "font_size": 9, "font_color": PALETTE["negative"]}
        )
        self.card = workbook.add_format(
            {**base, "bg_color": PALETTE["surface"], "border": 1, "border_color": PALETTE["border"]}
        )
        self.key = workbook.add_format(
            {
                **base,
                "font_size": 9,
                "bold": True,
                "bg_color": "#F2EFFF",
                "border": 1,
                "border_color": PALETTE["border"],
            }
        )
        self.text = workbook.add_format(
            {**base, "font_size": 9, "border": 1, "border_color": PALETTE["border"]}
        )
        self.wrap = workbook.add_format(
            {
                **base,
                "font_size": 9,
                "text_wrap": True,
                "valign": "top",
                "border": 1,
                "border_color": PALETTE["border"],
            }
        )
        self.number = workbook.add_format(
            {
                **base,
                "font_size": 9,
                "num_format": "#,##0.0",
                "border": 1,
                "border_color": PALETTE["border"],
            }
        )
        self.integer = workbook.add_format(
            {
                **base,
                "font_size": 9,
                "num_format": "#,##0",
                "border": 1,
                "border_color": PALETTE["border"],
            }
        )
        self.percent = workbook.add_format(
            {
                **base,
                "font_size": 9,
                "num_format": "0.0%",
                "border": 1,
                "border_color": PALETTE["border"],
            }
        )
        self.date = workbook.add_format(
            {
                **base,
                "font_size": 9,
                "num_format": "dd mmm yyyy",
                "border": 1,
                "border_color": PALETTE["border"],
            }
        )
        self.datetime = workbook.add_format(
            {
                **base,
                "font_size": 9,
                "num_format": "dd mmm yyyy hh:mm",
                "border": 1,
                "border_color": PALETTE["border"],
            }
        )
        self.note = workbook.add_format(
            {
                **base,
                "font_size": 9,
                "font_color": PALETTE["muted"],
                "text_wrap": True,
                "valign": "top",
            }
        )
        self.logo = workbook.add_format(
            {**base, "font_size": 22, "bold": True, "font_color": "#2F368E"}
        )
        self.logo_ai = workbook.add_format(
            {
                **base,
                "font_size": 9,
                "bold": True,
                "font_color": "#5B3DF5",
                "bg_color": "#EEEAFE",
                "align": "center",
                "valign": "vcenter",
            }
        )


class _WorkbookRenderer:
    def __init__(self) -> None:
        self.output = BytesIO()
        self.workbook = xlsxwriter.Workbook(
            self.output,
            {
                "in_memory": True,
                "strings_to_formulas": False,
                "strings_to_urls": False,
                "strings_to_numbers": False,
            },
        )
        self.workbook.set_properties(
            {
                "title": "Accumulate Social Media Report",
                "subject": "Scoped dashboard export",
                "author": "Accumulate",
                "company": "Accumulate",
                "comments": "Generated from the Social Media V2 dashboard projection.",
            }
        )
        self.formats = _Formats(self.workbook)
        self.table_index = 0
        self.daily_data: _ChartData | None = None

    def close(self) -> bytes:
        self.workbook.close()
        return self.output.getvalue()

    def sheet(self, name: str, *, landscape: bool = True) -> Any:
        worksheet = self.workbook.add_worksheet(name[:31])
        worksheet.hide_gridlines(2)
        worksheet.set_tab_color(PALETTE["purple"])
        worksheet.set_landscape() if landscape else worksheet.set_portrait()
        worksheet.set_paper(9)
        worksheet.fit_to_pages(1, 0)
        worksheet.set_margins(0.3, 0.3, 0.45, 0.45)
        worksheet.set_header("&RAccumulate · Social Media")
        worksheet.set_footer("&LGenerated by Accumulate&CPage &P of &N")
        return worksheet

    def heading(self, worksheet: Any, title: str, subtitle: str) -> None:
        worksheet.merge_range("A1:R2", title, self.formats.title)
        worksheet.merge_range("A3:R3", subtitle, self.formats.subtitle)
        worksheet.set_row(0, 22)
        worksheet.set_row(1, 8)
        worksheet.set_row(2, 18)
        worksheet.set_column("A:A", 2)
        worksheet.set_column("B:R", 12)

    def report_info(
        self,
        context: ReportContext,
        dashboard: PlatformDashboard | OverviewDashboard,
    ) -> None:
        sheet = self.sheet("Report Info", landscape=False)
        sheet.set_column("A:A", 3)
        sheet.set_column("B:B", 24)
        sheet.set_column("C:H", 17)
        sheet.set_row(1, 34)
        logo_path = next((path for path in _LOGO_PATHS if path.is_file()), None)
        if logo_path is not None:
            logo_data = BytesIO(logo_path.read_bytes())
            sheet.insert_image(
                "B2",
                "accumulate-logo.png",
                {
                    "image_data": logo_data,
                    "x_scale": 0.145,
                    "y_scale": 0.145,
                    "object_position": 1,
                    "description": "Accumulate",
                },
            )
        else:
            sheet.merge_range("B2:F3", "Accumulate", self.formats.logo)
            sheet.write("G2", "AI", self.formats.logo_ai)
        sheet.merge_range("B5:H6", "SOCIAL MEDIA REPORT", self.formats.title)
        sheet.merge_range(
            "B7:H7", f"{context.brand_name} · {context.surface.title()}", self.formats.subtitle
        )
        previous_start = dashboard.meta.date_range.start_on - timedelta(
            days=dashboard.meta.expected_days
        )
        previous_end = dashboard.meta.date_range.start_on - timedelta(days=1)
        values = (
            ("Brand", context.brand_name),
            ("Surface", context.surface.title()),
            ("Account", context.account_name),
            ("Active Page", context.tab.title()),
            ("Scope", "Brand family rollup" if context.rollup else "Selected Brand"),
            (
                "Reporting Period",
                (
                    f"{dashboard.meta.date_range.start_on:%d %b %Y} – "
                    f"{dashboard.meta.date_range.end_on:%d %b %Y}"
                ),
            ),
            ("Comparison Period", f"{previous_start:%d %b %Y} – {previous_end:%d %b %Y}"),
            ("Generated At", _iso_datetime(dashboard.meta.generated_at)),
            ("Data Last Updated", _iso_datetime(dashboard.meta.last_sync_at)),
            ("Timezone", "UTC"),
            ("Data Status", dashboard.meta.data_status.value.title()),
            ("Freshness", dashboard.meta.freshness.value.replace("_", " ").title()),
            ("Coverage", f"{dashboard.meta.observed_days} of {dashboard.meta.expected_days} days"),
            ("Export Version", context.export_version),
        )
        sheet.merge_range("B10:H10", "Report Information", self.formats.section)
        for row, (label, value) in enumerate(values, 11):
            sheet.write(row, 1, label, self.formats.key)
            sheet.merge_range(row, 2, row, 7, value, self.formats.text)
        note_row = 27
        sheet.merge_range(note_row, 1, note_row, 7, "Data Notes", self.formats.section)
        notes = list(dashboard.meta.warnings) or ["No reporting warnings for the selected scope."]
        sheet.merge_range(
            note_row + 1,
            1,
            note_row + 4,
            7,
            "\n".join(f"• {item}" for item in notes),
            self.formats.note,
        )
        sheet.freeze_panes(9, 0)
        sheet.print_area(0, 0, note_row + 4, 7)

    def add_kpis(
        self, worksheet: Any, start_row: int, kpis: Sequence[tuple[str, DashboardMetric | None]]
    ) -> int:
        for index, (label, metric) in enumerate(kpis[:6]):
            group_row = start_row + (index // 3) * 5
            column = 1 + (index % 3) * 6
            worksheet.merge_range(
                group_row, column, group_row, column + 4, label, self.formats.label
            )
            value = _metric_display(metric)
            worksheet.merge_range(
                group_row + 1, column, group_row + 2, column + 4, value, self.formats.value
            )
            delta = metric.delta_pct if metric is not None else None
            delta_copy = (
                "Comparison unavailable" if delta is None else f"{delta:+.1f}% vs previous period"
            )
            worksheet.merge_range(
                group_row + 3,
                column,
                group_row + 3,
                column + 4,
                delta_copy,
                self.formats.delta if delta is not None and delta >= 0 else self.formats.delta_down,
            )
            for row in range(group_row, group_row + 4):
                worksheet.set_row(row, 20 if row != group_row + 1 else 26)
            worksheet.set_column(column, column + 4, 10)
        return start_row + 10

    def write_daily_data(self, series: Sequence[DashboardSeries]) -> _ChartData:
        items = tuple(
            (
                item.metric_id.value,
                METRIC_LABELS.get(
                    item.metric_id.value,
                    item.metric_id.value.replace("_", " ").title(),
                ),
                item.points,
            )
            for item in series
        )
        self.daily_data = self.write_named_daily_data("Data - Daily", items)
        return self.daily_data

    def write_named_daily_data(
        self,
        sheet_name: str,
        items: Sequence[tuple[str, str, Sequence[Any]]],
    ) -> _ChartData:
        dates = sorted({point.observed_on for _, _, points in items for point in points})
        ordered_keys = [key for key, _, _ in items]
        sheet = self.sheet(sheet_name)
        sheet.freeze_panes(4, 1)
        self.heading(
            sheet,
            "Daily Metric Data",
            "Canonical dashboard series used by report charts",
        )
        headers = ["Date", *[label for _, label, _ in items]]
        value_maps = {
            key: {point.observed_on: point.value for point in points} for key, _, points in items
        }
        rows: list[list[Any]] = []
        for observed_on in dates:
            row: list[Any] = [datetime.combine(observed_on, datetime.min.time())]
            for key in ordered_keys:
                value = value_maps[key].get(observed_on)
                if key == MetricId.UNFOLLOWS.value and value is not None:
                    value = -abs(value)
                row.append(value)
            rows.append(row)
        self._table(sheet, 4, 1, headers, rows, "DailyMetrics")
        sheet.set_column(1, 1, 14, self.formats.date)
        if len(headers) > 1:
            sheet.set_column(2, len(headers), 16, self.formats.number)
        return _ChartData(
            sheet_name=sheet_name,
            columns={key: index + 1 for index, key in enumerate(ordered_keys)},
            rows=len(rows),
        )

    def write_story_data(self, dashboard: PlatformDashboard) -> _ChartData | None:
        stories = dashboard.stories
        if stories is None:
            return None
        views = tuple(
            DashboardPoint(observed_on=observed_on, value=value)
            for observed_on, value in zip(
                stories.trend.labels,
                stories.trend.views,
                strict=True,
            )
            if value is not None
        )
        reach = tuple(
            DashboardPoint(observed_on=observed_on, value=value)
            for observed_on, value in zip(
                stories.trend.labels,
                stories.trend.reach,
                strict=True,
            )
            if value is not None
        )
        return self.write_named_daily_data(
            "Data - Story Trend",
            (
                (MetricId.VIEWS.value, "Story Views", views),
                (MetricId.REACH.value, "Story Reach", reach),
            ),
        )

    def add_trend_chart(
        self,
        worksheet: Any,
        cell: str,
        title: str,
        keys: Sequence[str],
        *,
        column: bool = False,
        width: int = 650,
        height: int = 280,
        source: _ChartData | None = None,
    ) -> None:
        data = source or self.daily_data
        available = [
            key for key in keys if data is not None and key in data.columns and data.rows > 0
        ]
        if not available or data is None:
            worksheet.merge_range(
                cell + ":" + _offset_cell(cell, 7, 10),
                f"{title}\nData unavailable",
                self.formats.note,
            )
            return
        chart_type = "column" if column else "area"
        chart = self.workbook.add_chart({"type": chart_type})
        for key in available:
            label, color = CHART_KEYS.get(
                key, (METRIC_LABELS.get(key, key.title()), PALETTE["purple"])
            )
            series_options: dict[str, Any] = {
                "name": label,
                "categories": [data.sheet_name, 5, 1, 4 + data.rows, 1],
                "values": [
                    data.sheet_name,
                    5,
                    data.columns[key] + 1,
                    4 + data.rows,
                    data.columns[key] + 1,
                ],
                "line": {"color": color, "width": 1.25},
                "fill": {"color": color, "transparency": 22 if column else 78},
            }
            chart.add_series(series_options)
        chart.set_title(
            {
                "name": title,
                "name_font": {"name": "Inter", "size": 11, "bold": True, "color": PALETTE["ink"]},
            }
        )
        chart.set_legend(
            {"position": "top", "font": {"name": "Inter", "size": 8, "color": PALETTE["muted"]}}
        )
        chart.set_x_axis(
            {
                "date_axis": True,
                "num_format": "dd mmm",
                "label_position": "low",
                "line": {"color": PALETTE["border"]},
                "num_font": {"name": "Inter", "size": 8, "color": PALETTE["muted"]},
            }
        )
        chart.set_y_axis(
            {
                "major_gridlines": {"visible": True, "line": {"color": "#EEF2F7", "width": 0.55}},
                "line": {"none": True},
                "num_font": {"name": "Inter", "size": 8, "color": PALETTE["muted"]},
            }
        )
        chart.set_chartarea(
            {
                "border": {"color": PALETTE["border"], "width": 0.75},
                "fill": {"color": PALETTE["surface"]},
            }
        )
        chart.set_plotarea({"border": {"none": True}, "fill": {"color": PALETTE["surface"]}})
        chart.set_size({"width": width, "height": height})
        worksheet.insert_chart(cell, chart)

    def summary_table(
        self,
        worksheet: Any,
        start_row: int,
        title: str,
        rows: Sequence[tuple[str, Any]],
        *,
        start_column: int = 1,
    ) -> int:
        worksheet.merge_range(
            start_row,
            start_column,
            start_row,
            start_column + 7,
            title,
            self.formats.section,
        )
        values = [[label, value if value is not None else "Not provided"] for label, value in rows]
        self._table(
            worksheet,
            start_row + 2,
            start_column,
            ["Metric", "Value"],
            values,
            title,
        )
        return start_row + max(6, len(values) + 4)

    def breakdowns(self, dashboard: PlatformDashboard) -> None:
        sheet = self.sheet("Data - Breakdowns")
        self.heading(
            sheet,
            "Audience & Source Breakdowns",
            "Provider-reported dimensions for the selected period",
        )
        sheet.freeze_panes(4, 1)
        rows = [
            [item.metric_id.value, item.dimension, row.key, row.value, row.percentage]
            for item in dashboard.breakdowns
            for row in item.items
        ]
        self._table(
            sheet, 4, 1, ["Metric", "Dimension", "Value", "Count", "Percentage"], rows, "Breakdowns"
        )

    def content(self, rows: Sequence[DashboardContent]) -> None:
        sheet = self.sheet("All Content")
        self.heading(
            sheet,
            "All Performing Content",
            "Content-level values returned by the canonical dashboard projection",
        )
        sheet.freeze_panes(4, 1)
        values = [
            [
                row.external_content_id,
                row.published_at,
                row.content_type,
                row.message,
                row.views,
                row.reach,
                row.likes_count,
                row.comments_count,
                row.shares_count,
                row.interactions,
                row.data_status.value,
            ]
            for row in rows
            if "story" not in row.content_type.lower()
        ]
        self._table(
            sheet,
            4,
            1,
            [
                "Content ID",
                "Published At",
                "Type",
                "Caption / Name",
                "Views",
                "Reach",
                "Likes",
                "Comments",
                "Shares",
                "Interactions",
                "Data Status",
            ],
            values,
            "Content",
        )
        sheet.set_column(4, 4, 44, self.formats.wrap)

    def stories(self, dashboard: PlatformDashboard) -> None:
        sheet = self.sheet("Story History")
        self.heading(
            sheet,
            "Story History",
            "Story-level actions, navigation and completion for the selected period",
        )
        sheet.freeze_panes(4, 1)
        stories = dashboard.stories.items if dashboard.stories is not None else ()
        rows = [
            [
                row.content_id,
                row.created_time,
                row.title,
                row.views,
                row.reach,
                row.interactions,
                row.replies,
                row.shares,
                row.profile_visits,
                row.follows,
                row.sticker_taps,
                row.saves,
                row.taps_forward,
                row.taps_back,
                row.swipe_forward,
                row.exits,
                row.navigation,
                None if row.completion_rate is None else row.completion_rate / 100,
                row.data_status.value,
            ]
            for row in stories
        ]
        self._table(
            sheet,
            4,
            1,
            [
                "Story ID",
                "Published At",
                "Title",
                "Views",
                "Reach",
                "Interactions",
                "Replies",
                "Shares",
                "Profile Visits",
                "Follows",
                "Sticker Taps",
                "Saves",
                "Tap Forward",
                "Tap Back",
                "Swipe Forward",
                "Exits",
                "Navigation",
                "Completion Rate",
                "Data Status",
            ],
            rows,
            "Stories",
        )

    def community(self, dashboard: PlatformDashboard | OverviewDashboard) -> None:
        sheet = self.sheet("Community")
        self.heading(sheet, "Community", "Comment activity and ranked community contributions")
        summary = dashboard.community
        row = self.summary_table(
            sheet,
            5,
            "Community Summary",
            (
                ("Total Comments", summary.total_comments),
                ("Answered Comments", summary.answered_comments),
                ("Unanswered Comments", summary.unanswered_comments),
                ("Comment Likes", summary.comment_likes),
                ("Data Status", summary.data_status.value.title()),
            ),
        )
        self._table(
            sheet,
            row,
            1,
            ["Name", "Comments", "Likes"],
            [[item.name, item.comments, item.likes] for item in summary.top_commenters],
            "TopCommenters",
        )
        row += max(5, len(summary.top_commenters) + 3)
        self._table(
            sheet,
            row,
            1,
            ["Name", "Comment", "Likes", "Replies"],
            [
                [item.name, item.comment, item.likes, item.replies]
                for item in summary.top_liked_comments
            ],
            "TopLikedComments",
        )
        sheet.set_column(2, 2, 42, self.formats.wrap)

    def dictionary(self, metrics: Sequence[DashboardMetric]) -> None:
        sheet = self.sheet("Data Dictionary")
        self.heading(
            sheet, "Data Dictionary", "Metric semantics and methodology used in this workbook"
        )
        rows = [
            [
                METRIC_LABELS.get(
                    item.metric_id.value, item.metric_id.value.replace("_", " ").title()
                ),
                item.metric_id.value,
                item.semantic_type.value,
                item.unit.value,
                item.methodology,
                item.data_status.value,
                item.availability_reason or "",
            ]
            for item in metrics
        ]
        self._table(
            sheet,
            4,
            1,
            [
                "Metric",
                "Metric ID",
                "Semantic Type",
                "Unit",
                "Methodology",
                "Data Status",
                "Availability Reason",
            ],
            rows,
            "Dictionary",
        )
        sheet.freeze_panes(4, 1)
        sheet.set_column(5, 5, 32, self.formats.wrap)
        sheet.set_column(7, 7, 34, self.formats.wrap)

    def _table(
        self,
        worksheet: Any,
        row: int,
        column: int,
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]],
        stem: str,
    ) -> None:
        self.table_index += 1
        table_name = _table_name(f"{stem}{self.table_index}")
        if not rows:
            for offset, header in enumerate(headers):
                worksheet.write(row, column + offset, header, self.formats.key)
            worksheet.merge_range(
                row + 1,
                column,
                row + 2,
                column + len(headers) - 1,
                "No data available for the selected scope and period.",
                self.formats.note,
            )
            return
        for row_offset, values in enumerate(rows, row + 1):
            for column_offset, value in enumerate(values, column):
                literal = _literal(value)
                worksheet.write(
                    row_offset,
                    column_offset,
                    literal,
                    self._cell_format(headers[column_offset - column], literal),
                )
        worksheet.add_table(
            row,
            column,
            row + len(rows),
            column + len(headers) - 1,
            {
                "name": table_name,
                "style": "Table Style Medium 2",
                "columns": [{"header": header} for header in headers],
            },
        )
        worksheet.set_column(column, column + len(headers) - 1, 15)

    def _cell_format(self, header: str, value: Any) -> Any:
        if isinstance(value, datetime):
            return (
                self.formats.datetime if value.time() != datetime.min.time() else self.formats.date
            )
        normalized = header.lower()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "rate" in normalized or "percentage" in normalized:
                return self.formats.percent
            return self.formats.number
        return (
            self.formats.wrap if normalized in {"caption / name", "comment"} else self.formats.text
        )


def build_platform_xlsx(
    *,
    dashboard: PlatformDashboard,
    context: ReportContext,
    progress: Progress,
) -> ReportArtifact:
    renderer = _WorkbookRenderer()
    progress(12, "Creating report cover")
    renderer.report_info(context, dashboard)
    progress(20, "Preparing canonical chart data")
    renderer.write_daily_data(dashboard.series)
    sections = _platform_sections(dashboard.meta.platform, context.tab)
    for index, section in enumerate(sections):
        progress(25 + round(index / max(1, len(sections)) * 48), f"Rendering {section} page")
        if section in {"Page", "Account"}:
            _render_page(renderer, dashboard, section)
        elif section == "Content":
            _render_content(renderer, dashboard)
        elif section == "Stories":
            _render_stories(renderer, dashboard)
        elif section == "Audience":
            _render_audience(renderer, dashboard)
    if "Content" in sections:
        progress(76, "Writing full content table")
        renderer.content(dashboard.content)
    if "Stories" in sections and dashboard.meta.platform is PlatformId.INSTAGRAM:
        progress(82, "Writing story history")
        renderer.stories(dashboard)
    if "Audience" in sections:
        progress(86, "Writing audience breakdowns")
        renderer.breakdowns(dashboard)
        renderer.community(dashboard)
    progress(93, "Writing metric dictionary")
    renderer.dictionary(dashboard.metrics)
    progress(98, "Finalizing workbook")
    content = renderer.close()
    return ReportArtifact(
        filename=_filename(context, dashboard.meta.date_range.end_on.isoformat()), content=content
    )


def build_overview_xlsx(
    *,
    dashboard: OverviewDashboard,
    context: ReportContext,
    progress: Progress,
) -> ReportArtifact:
    renderer = _WorkbookRenderer()
    progress(12, "Creating report cover")
    renderer.report_info(context, dashboard)
    progress(22, "Preparing cross-platform data")
    overview_series = []
    for platform_dashboard in dashboard.platforms:
        platform = platform_dashboard.meta.platform
        if platform is None:
            continue
        metric_ids = (
            (MetricId.VIDEO_ENGAGEMENTS_TOTAL.value, MetricId.INTERACTIONS.value)
            if platform is PlatformId.TIKTOK
            else (MetricId.INTERACTIONS.value,)
        )
        selected = next(
            (
                item
                for metric_id in metric_ids
                for item in platform_dashboard.series
                if item.metric_id.value == metric_id
            ),
            None,
        )
        if selected is not None:
            overview_series.append(
                (
                    f"{platform.value}_performance",
                    platform.value.title(),
                    selected.points,
                )
            )
    overview_data = renderer.write_named_daily_data(
        "Data - Performance",
        overview_series,
    )
    sheet = renderer.sheet("Overview")
    renderer.heading(
        sheet,
        "Social Media Overview",
        (
            f"{context.brand_name} · {dashboard.meta.date_range.start_on:%d %b %Y} – "
            f"{dashboard.meta.date_range.end_on:%d %b %Y}"
        ),
    )
    renderer.add_kpis(
        sheet,
        5,
        [
            (METRIC_LABELS.get(item.metric_id.value, item.metric_id.value), item)
            for item in dashboard.metrics[:6]
        ],
    )
    renderer.add_trend_chart(
        sheet,
        "B17",
        "Performance Trend",
        [
            "instagram_performance",
            "facebook_performance",
            "tiktok_performance",
        ],
        width=1050,
        height=360,
        source=overview_data,
    )
    progress(55, "Writing platform summary")
    platform_sheet = renderer.sheet("Platform Summary")
    renderer.heading(
        platform_sheet,
        "Platform Summary",
        "Connected channel performance for the selected Brand scope",
    )
    platform_rows = []
    for platform in dashboard.platforms:
        lookup = _metric_lookup(platform.metrics)
        platform_rows.append(
            [
                platform.meta.platform.value.title() if platform.meta.platform else "",
                *[
                    _metric_value(lookup.get(metric_id))
                    for metric_id in (
                        MetricId.FOLLOWERS.value,
                        MetricId.REACH.value,
                        MetricId.VIEWS.value,
                        MetricId.INTERACTIONS.value,
                        MetricId.ENGAGEMENT_RATE.value,
                    )
                ],
                platform.meta.data_status.value,
            ]
        )
    renderer._table(
        platform_sheet,
        4,
        1,
        [
            "Platform",
            "Followers",
            "Reach",
            "Views",
            "Interactions",
            "Engagement Rate",
            "Data Status",
        ],
        platform_rows,
        "PlatformSummary",
    )
    progress(72, "Writing top content")
    renderer.content(dashboard.content)
    progress(82, "Writing community data")
    renderer.community(dashboard)
    progress(91, "Writing metric dictionary")
    renderer.dictionary(dashboard.metrics)
    progress(98, "Finalizing workbook")
    content = renderer.close()
    return ReportArtifact(
        filename=_filename(context, dashboard.meta.date_range.end_on.isoformat()), content=content
    )


def _render_page(renderer: _WorkbookRenderer, dashboard: PlatformDashboard, title: str) -> None:
    sheet = renderer.sheet(title)
    renderer.heading(
        sheet,
        f"{dashboard.meta.platform.value.title()} {title}",
        "Account performance, follower movement and delivery sources",
    )
    lookup = _metric_lookup(dashboard.metrics)
    platform = dashboard.meta.platform
    if platform is PlatformId.TIKTOK:
        ids = (
            MetricId.FOLLOWERS.value,
            MetricId.NEW_FOLLOWERS.value,
            MetricId.VIDEO_VIEWS_TOTAL.value,
            MetricId.REACH.value,
            MetricId.VIDEO_ENGAGEMENTS_TOTAL.value,
            MetricId.VIDEO_ENGAGEMENT_RATE.value,
        )
    elif platform is PlatformId.FACEBOOK:
        ids = (
            MetricId.FOLLOWERS.value,
            MetricId.NEW_FOLLOWERS.value,
            MetricId.REACH.value,
            MetricId.PAGE_VIEWS.value,
            MetricId.INTERACTIONS.value,
            MetricId.ENGAGEMENT_RATE.value,
        )
    else:
        ids = (
            MetricId.FOLLOWERS.value,
            MetricId.NEW_FOLLOWERS.value,
            MetricId.REACH.value,
            MetricId.VIEWS.value,
            MetricId.INTERACTIONS.value,
            MetricId.ENGAGEMENT_RATE.value,
        )
    renderer.add_kpis(
        sheet, 5, [(METRIC_LABELS.get(item, item.title()), lookup.get(item)) for item in ids]
    )
    renderer.add_trend_chart(sheet, "B17", "Followers Trend", [MetricId.FOLLOWERS.value])
    renderer.add_trend_chart(
        sheet,
        "K17",
        "New Followers Trend",
        [MetricId.FOLLOWS.value, MetricId.UNFOLLOWS.value, MetricId.FOLLOWERS_NET.value],
    )
    renderer.add_trend_chart(
        sheet,
        "B33",
        "Performance Trends",
        [MetricId.REACH.value, MetricId.VIEWS.value],
        column=True,
        width=1050,
        height=330,
    )
    source = dashboard.source_breakdown
    renderer.summary_table(
        sheet,
        52,
        "Views Source",
        (
            ("Organic", source.views.organic if source and source.views else None),
            ("Paid", source.views.paid if source and source.views else None),
        ),
    )
    renderer.summary_table(
        sheet,
        52,
        "Reach Source",
        (
            ("Organic", source.reach.organic if source and source.reach else None),
            ("Paid", source.reach.paid if source and source.reach else None),
        ),
        start_column=10,
    )
    sheet.freeze_panes(4, 0)


def _render_content(renderer: _WorkbookRenderer, dashboard: PlatformDashboard) -> None:
    sheet = renderer.sheet("Content")
    renderer.heading(
        sheet,
        f"{dashboard.meta.platform.value.title()} Content",
        "Content performance, interaction mix and format distribution",
    )
    lookup = _metric_lookup(dashboard.metrics)
    if dashboard.meta.platform is PlatformId.TIKTOK:
        ids = (
            MetricId.VIDEO_VIEWS_TOTAL.value,
            MetricId.REACH.value,
            MetricId.VIDEO_LIKES_TOTAL.value,
            MetricId.VIDEO_COMMENTS_TOTAL.value,
            MetricId.VIDEO_SHARES_TOTAL.value,
            MetricId.VIDEO_ENGAGEMENT_RATE.value,
        )
    else:
        ids = (
            MetricId.VIEWS.value,
            MetricId.REACH.value,
            MetricId.REACTIONS.value,
            MetricId.INTERACTIONS.value,
            MetricId.MEDIA_COUNT.value,
            MetricId.ENGAGEMENT_RATE.value,
        )
    renderer.add_kpis(
        sheet, 5, [(METRIC_LABELS.get(item, item.title()), lookup.get(item)) for item in ids]
    )
    renderer.add_trend_chart(
        sheet,
        "B17",
        "Views & Reach Trend",
        [MetricId.VIEWS.value, MetricId.REACH.value],
        width=1050,
        height=320,
    )
    interaction_keys = (
        [
            MetricId.VIDEO_LIKES_TOTAL.value,
            MetricId.VIDEO_COMMENTS_TOTAL.value,
            MetricId.VIDEO_SHARES_TOTAL.value,
        ]
        if dashboard.meta.platform is PlatformId.TIKTOK
        else [MetricId.INTERACTIONS.value]
    )
    renderer.add_trend_chart(
        sheet,
        "B35",
        "Interaction Trend",
        interaction_keys,
        width=650,
        height=300,
    )
    renderer.summary_table(
        sheet,
        35,
        "Content Type",
        tuple((item.name, item.value) for item in dashboard.content_summary.by_type),
        start_column=10,
    )
    renderer.summary_table(
        sheet,
        47,
        "Top Hashtags",
        tuple((item.name, item.count) for item in dashboard.top_hashtags),
        start_column=10,
    )
    sheet.freeze_panes(4, 0)


def _render_stories(renderer: _WorkbookRenderer, dashboard: PlatformDashboard) -> None:
    sheet = renderer.sheet("Stories")
    renderer.heading(
        sheet, "Instagram Stories", "Story performance, audience behaviour and history"
    )
    stories = dashboard.stories
    if stories is None:
        sheet.merge_range(
            "B6:Q12",
            "Story data unavailable for the selected scope and period.",
            renderer.formats.note,
        )
        return
    summary = stories.summary
    rows = (
        ("Story Count", summary.count),
        ("Story Views", summary.views),
        ("Story Reach", summary.reach),
        ("Interactions", summary.interactions),
        ("Replies", summary.replies),
        (
            "Completion Rate",
            None if summary.completion_rate is None else f"{summary.completion_rate:.1f}%",
        ),
    )
    renderer.summary_table(sheet, 5, "Period Summary", rows)
    actions = stories.actions
    renderer.summary_table(
        sheet,
        5,
        "Behaviour Totals",
        (
            ("Replies", actions.replies),
            ("Shares", actions.shares),
            ("Profile Visits", actions.profile_visits),
            ("Follows", actions.follows),
            ("Sticker Taps", actions.sticker_taps),
            ("Saves", actions.saves),
        ),
        start_column=10,
    )
    navigation = stories.navigation
    renderer.summary_table(
        sheet,
        18,
        "Navigation Split",
        (
            ("Tap Forward", navigation.taps_forward),
            ("Swipe Forward", navigation.swipe_forward),
            ("Tap Back", navigation.taps_back),
            ("Exits", navigation.exits),
        ),
    )
    story_data = renderer.write_story_data(dashboard)
    renderer.add_trend_chart(
        sheet,
        "B31",
        "Story Evolution",
        [MetricId.VIEWS.value, MetricId.REACH.value],
        width=1050,
        height=340,
        source=story_data,
    )
    sheet.freeze_panes(4, 0)


def _render_audience(renderer: _WorkbookRenderer, dashboard: PlatformDashboard) -> None:
    sheet = renderer.sheet("Audience")
    renderer.heading(
        sheet,
        f"{dashboard.meta.platform.value.title()} Audience",
        "Audience growth, geography, demographics and activity",
    )
    lookup = _metric_lookup(dashboard.metrics)
    ids = (
        MetricId.FOLLOWERS.value,
        MetricId.NEW_FOLLOWERS.value,
        MetricId.VIEWS.value,
        MetricId.REACH.value,
        MetricId.PROFILE_VIEWS.value,
        MetricId.ENGAGEMENT_RATE.value,
    )
    renderer.add_kpis(
        sheet, 5, [(METRIC_LABELS.get(item, item.title()), lookup.get(item)) for item in ids]
    )
    renderer.add_trend_chart(sheet, "B17", "Followers Trend", [MetricId.FOLLOWERS.value])
    renderer.add_trend_chart(
        sheet,
        "K17",
        "New Followers Trend",
        [MetricId.FOLLOWS.value, MetricId.UNFOLLOWS.value, MetricId.FOLLOWERS_NET.value],
    )
    row = 34
    for breakdown in dashboard.breakdowns[:6]:
        title = breakdown.dimension.replace("_", " ").title()
        rows = tuple((item.key, item.value) for item in breakdown.items[:12])
        row = renderer.summary_table(sheet, row, title, rows)
    sheet.freeze_panes(4, 0)


def _platform_sections(platform: PlatformId | None, tab: str) -> tuple[str, ...]:
    if platform is PlatformId.TIKTOK:
        all_sections = ("Account", "Content", "Audience")
        normalized = "Account" if tab == "account" else tab.title()
    elif platform is PlatformId.INSTAGRAM:
        all_sections = ("Page", "Content", "Stories", "Audience")
        normalized = tab.title()
    else:
        all_sections = ("Page", "Content", "Audience")
        normalized = tab.title()
    return (
        all_sections
        if tab == "cover"
        else tuple(item for item in all_sections if item == normalized)
    )


def _metric_lookup(metrics: Iterable[DashboardMetric]) -> dict[str, DashboardMetric]:
    return {item.metric_id.value: item for item in metrics}


def _metric_value(metric: DashboardMetric | None) -> float | None:
    return None if metric is None else metric.value


def _metric_display(metric: DashboardMetric | None) -> str:
    if metric is None or metric.value is None:
        return "—"
    if metric.unit.value == "ratio":
        return f"{metric.value * 100:.1f}%"
    value = metric.value
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def _literal(value: Any) -> Any:
    if value is None:
        return "Not provided"
    if isinstance(value, datetime):
        return value.astimezone(UTC).replace(tzinfo=None)
    if isinstance(value, str):
        return value.replace("\x00", "")[:32_000]
    return value


def _iso_datetime(value: datetime | None) -> str:
    if value is None:
        return "Not available"
    return value.astimezone(UTC).strftime("%d %b %Y, %H:%M UTC")


def _table_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "", value)
    return (normalized or "ReportTable")[:240]


def _filename(context: ReportContext, end_on: str) -> str:
    brand = re.sub(r"[^a-z0-9]+", "-", context.brand_name.lower()).strip("-") or "brand"
    return f"accumulate-{brand}-{context.surface}-{context.tab}-{end_on}.xlsx"


def _offset_cell(cell: str, columns: int, rows: int) -> str:
    match = re.fullmatch(r"([A-Z]+)([0-9]+)", cell)
    if not match:
        return cell
    column_value = 0
    for char in match.group(1):
        column_value = column_value * 26 + ord(char) - 64
    column_value += columns
    letters = ""
    while column_value:
        column_value, remainder = divmod(column_value - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{letters}{int(match.group(2)) + rows}"


__all__ = ["ReportContext", "build_overview_xlsx", "build_platform_xlsx"]
