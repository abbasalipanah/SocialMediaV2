"""Daily LinkedIn Company Page follower, content, and page metrics."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.profile import DailyMetricSnapshot
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId

from .responses import LinkedInResponseError, elements, required_count, required_mapping
from .wire import MAX_LINKEDIN_DAILY_WINDOW_DAYS, organization_urn


class LinkedInDailyMetricsReader:
    def __init__(
        self,
        fetch_share_statistics: Callable[[ProviderAccount, date, date], Mapping[str, Any]],
        fetch_follower_statistics: Callable[[ProviderAccount, date, date], Mapping[str, Any]],
        fetch_page_statistics: Callable[[ProviderAccount, date, date], Mapping[str, Any]],
    ) -> None:
        self._fetch_share_statistics = fetch_share_statistics
        self._fetch_follower_statistics = fetch_follower_statistics
        self._fetch_page_statistics = fetch_page_statistics

    def fetch_daily_metrics(
        self,
        account: ProviderAccount,
        *,
        since: date,
        until: date,
    ) -> tuple[DailyMetricSnapshot, ...]:
        if account.platform is not PlatformId.LINKEDIN:
            raise ValueError("provider_family_mismatch")
        if until < since or (until - since).days >= MAX_LINKEDIN_DAILY_WINDOW_DAYS:
            raise ValueError("linkedin_metric_range_invalid")
        by_day: dict[date, dict[MetricId, int]] = {}
        expected_urn = organization_urn(account.account_id)
        self._add_share_rows(
            by_day,
            elements(self._fetch_share_statistics(account, since, until), limit=32),
            expected_urn,
            since,
            until,
        )
        self._add_follower_rows(
            by_day,
            elements(self._fetch_follower_statistics(account, since, until), limit=32),
            expected_urn,
            since,
            until,
        )
        self._add_page_rows(
            by_day,
            elements(self._fetch_page_statistics(account, since, until), limit=32),
            expected_urn,
            since,
            until,
        )
        return tuple(
            DailyMetricSnapshot(
                account_id=account.account_id,
                observed_on=observed_on,
                metric_values=values,
            )
            for observed_on, values in sorted(by_day.items())
        )

    @staticmethod
    def _add_share_rows(
        by_day: dict[date, dict[MetricId, int]],
        rows: tuple[Mapping[str, Any], ...],
        expected_urn: str,
        since: date,
        until: date,
    ) -> None:
        seen: set[date] = set()
        for row in rows:
            observed_on = _row_day(row, "organizationalEntity", expected_urn, since, until)
            if observed_on in seen:
                raise LinkedInResponseError("linkedin_daily_duplicate")
            seen.add(observed_on)
            totals = required_mapping(row, "totalShareStatistics")
            clicks = required_count(totals, "clickCount")
            likes = _like_count(totals)
            comments = required_count(totals, "commentCount")
            shares = required_count(totals, "shareCount")
            values = by_day.setdefault(observed_on, {})
            values.update(
                {
                    MetricId.VIEWS: required_count(totals, "impressionCount"),
                    MetricId.INTERACTIONS: clicks + likes + comments + shares,
                    MetricId.CLICKS: clicks,
                }
            )
            unique = totals.get(
                "uniqueImpressionsCount",
                totals.get("uniqueImpressionsCounts"),
            )
            if unique is not None:
                values[MetricId.REACH] = _count(unique)

    @staticmethod
    def _add_follower_rows(
        by_day: dict[date, dict[MetricId, int]],
        rows: tuple[Mapping[str, Any], ...],
        expected_urn: str,
        since: date,
        until: date,
    ) -> None:
        seen: set[date] = set()
        for row in rows:
            observed_on = _row_day(row, "organizationalEntity", expected_urn, since, until)
            if observed_on in seen:
                raise LinkedInResponseError("linkedin_daily_duplicate")
            seen.add(observed_on)
            gains = required_mapping(row, "followerGains")
            by_day.setdefault(observed_on, {})[MetricId.FOLLOWER_GAINS] = required_count(
                gains, "organicFollowerGain"
            ) + required_count(gains, "paidFollowerGain")

    @staticmethod
    def _add_page_rows(
        by_day: dict[date, dict[MetricId, int]],
        rows: tuple[Mapping[str, Any], ...],
        expected_urn: str,
        since: date,
        until: date,
    ) -> None:
        seen: set[date] = set()
        for row in rows:
            observed_on = _row_day(row, "organization", expected_urn, since, until)
            if observed_on in seen:
                raise LinkedInResponseError("linkedin_daily_duplicate")
            seen.add(observed_on)
            totals = required_mapping(row, "totalPageStatistics")
            views = required_mapping(required_mapping(totals, MetricId.VIEWS.value), "allPageViews")
            by_day.setdefault(observed_on, {})[MetricId.PAGE_VIEWS] = required_count(
                views, "pageViews"
            )


def _row_day(
    row: Mapping[str, Any],
    entity_key: str,
    expected_urn: str,
    since: date,
    until: date,
) -> date:
    if row.get(entity_key) != expected_urn:
        raise LinkedInResponseError("linkedin_daily_account_mismatch")
    time_range = required_mapping(row, "timeRange")
    start = time_range.get("start")
    end = time_range.get("end")
    if (
        isinstance(start, bool)
        or not isinstance(start, int)
        or isinstance(end, bool)
        or not isinstance(end, int)
        or end <= start
    ):
        raise LinkedInResponseError("linkedin_daily_time_invalid")
    observed = datetime.fromtimestamp(start / 1000, tz=UTC)
    if observed.time() != datetime.min.time() or end - start != 86_400_000:
        raise LinkedInResponseError("linkedin_daily_time_invalid")
    observed_on = observed.date()
    if observed_on < since or observed_on > until:
        raise LinkedInResponseError("linkedin_daily_time_invalid")
    return observed_on


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LinkedInResponseError("linkedin_response_field_invalid")
    return value


def _like_count(payload: Mapping[str, Any]) -> int:
    value = payload.get("likeCount")
    if isinstance(value, bool) or not isinstance(value, int):
        raise LinkedInResponseError("linkedin_response_field_invalid")
    # LinkedIn documents that organic likeCount may be negative after an unlike
    # of a sponsored reaction. It is not a usable count, so expose no negative
    # value to the product's non-negative metric contract.
    return max(0, value)


__all__ = ["LinkedInDailyMetricsReader"]
