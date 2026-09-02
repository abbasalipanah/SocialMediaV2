"""Stable Rest.li query construction for LinkedIn Company Page reads."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

LINKEDIN_POSTS_PAGE_SIZE = 25
MAX_LINKEDIN_DAILY_WINDOW_DAYS = 31


def organization_urn(organization_id: str) -> str:
    if not organization_id.isdigit() or len(organization_id) > 32:
        raise ValueError("linkedin_organization_id_invalid")
    return f"urn:li:organization:{organization_id}"


def organization_url(base_url: str, organization_id: str) -> str:
    return f"{base_url.rstrip('/')}/{organization_id}"


def network_size_url(base_url: str, organization_id: str) -> str:
    return f"{base_url.rstrip('/')}/{organization_urn(organization_id)}"


def network_size_query() -> dict[str, str]:
    return {"edgeType": "COMPANY_FOLLOWED_BY_MEMBER"}


def posts_query(organization_id: str, *, cursor: str | None = None) -> dict[str, str]:
    query = {
        "q": "author",
        "author": organization_urn(organization_id),
        "viewContext": "READER",
        "count": str(LINKEDIN_POSTS_PAGE_SIZE),
        "sortBy": "CREATED",
    }
    if cursor is not None:
        if not cursor.isdigit() or int(cursor) < 1:
            raise ValueError("linkedin_posts_cursor_invalid")
        query["start"] = cursor
    return query


def share_statistics_query(
    organization_id: str,
    *,
    since: date,
    until: date,
) -> dict[str, str]:
    return _daily_query("organizationalEntity", organization_id, since, until)


def follower_statistics_query(
    organization_id: str,
    *,
    since: date | None = None,
    until: date | None = None,
) -> dict[str, str]:
    if (since is None) is not (until is None):
        raise ValueError("linkedin_metric_range_invalid")
    if since is None or until is None:
        return {
            "q": "organizationalEntity",
            "organizationalEntity": organization_urn(organization_id),
        }
    return _daily_query("organizationalEntity", organization_id, since, until)


def page_statistics_query(
    organization_id: str,
    *,
    since: date,
    until: date,
) -> dict[str, str]:
    return _daily_query("organization", organization_id, since, until)


def post_statistics_queries(
    organization_id: str,
    post_urns: tuple[str, ...],
) -> tuple[dict[str, str], ...]:
    if len(post_urns) > LINKEDIN_POSTS_PAGE_SIZE or len(set(post_urns)) != len(post_urns):
        raise ValueError("linkedin_post_ids_invalid")
    base = {
        "q": "organizationalEntity",
        "organizationalEntity": organization_urn(organization_id),
    }
    shares = tuple(value for value in post_urns if value.startswith("urn:li:share:"))
    ugc_posts = tuple(value for value in post_urns if value.startswith("urn:li:ugcPost:"))
    if len(shares) + len(ugc_posts) != len(post_urns):
        raise ValueError("linkedin_post_ids_invalid")
    queries: list[dict[str, str]] = []
    if shares:
        queries.append({**base, "shares": f"List({','.join(shares)})"})
    if ugc_posts:
        queries.append(
            {
                **base,
                **{f"ugcPosts[{index}]": urn for index, urn in enumerate(ugc_posts)},
            }
        )
    return tuple(queries)


def _daily_query(
    entity_key: str,
    organization_id: str,
    since: date,
    until: date,
) -> dict[str, str]:
    if until < since or (until - since).days >= MAX_LINKEDIN_DAILY_WINDOW_DAYS:
        raise ValueError("linkedin_metric_range_invalid")
    start_ms = _epoch_milliseconds(since)
    end_ms = _epoch_milliseconds(until + timedelta(days=1))
    return {
        "q": entity_key,
        entity_key: organization_urn(organization_id),
        "timeIntervals": (f"(timeRange:(start:{start_ms},end:{end_ms}),timeGranularityType:DAY)"),
    }


def _epoch_milliseconds(value: date) -> int:
    observed = datetime.combine(value, time.min, tzinfo=UTC)
    return int(observed.timestamp() * 1000)


__all__ = [
    "LINKEDIN_POSTS_PAGE_SIZE",
    "MAX_LINKEDIN_DAILY_WINDOW_DAYS",
    "follower_statistics_query",
    "network_size_query",
    "network_size_url",
    "organization_urn",
    "organization_url",
    "page_statistics_query",
    "post_statistics_queries",
    "posts_query",
    "share_statistics_query",
]
