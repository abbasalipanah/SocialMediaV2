"""Canonical query application scaffold."""
from .dashboards import DashboardQuery, build_overview_dashboard, build_platform_dashboard
from .reporting_range import previous_reporting_range, resolve_reporting_range

__all__ = [
    "DashboardQuery",
    "build_overview_dashboard",
    "build_platform_dashboard",
    "previous_reporting_range",
    "resolve_reporting_range",
]
