"""LinkedIn Company Page post and organic share-stat normalization."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.application.ports.platforms.content import ContentPage
from app.core.time import utc_now
from app.domain.platforms import PlatformId

from .pagination import next_posts_cursor
from .responses import (
    LinkedInResponseError,
    elements,
    optional_text,
    required_mapping,
    required_text,
)
from .wire import LINKEDIN_POSTS_PAGE_SIZE, organization_urn

_POST_URN = re.compile(r"urn:li:(?:share|ugcPost):[0-9]{1,32}")


class LinkedInContentReader:
    def __init__(
        self,
        fetch_posts: Callable[[ProviderAccount, str | None], Mapping[str, Any]],
        fetch_statistics: Callable[
            [ProviderAccount, tuple[str, ...]], tuple[Mapping[str, Any], ...]
        ],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._fetch_posts = fetch_posts
        self._fetch_statistics = fetch_statistics
        self._clock = clock

    def list_content(
        self,
        account: ProviderAccount,
        *,
        cursor: str | None = None,
    ) -> ContentPage:
        if account.platform is not PlatformId.LINKEDIN:
            raise ValueError("provider_family_mismatch")
        observed_at = self._clock()
        payload = self._fetch_posts(account, cursor)
        cutoff = _rolling_year_start(observed_at)
        provider_posts = elements(payload, limit=LINKEDIN_POSTS_PAGE_SIZE)
        posts = tuple(
            post
            for post in provider_posts
            if _is_organic_published(post, account.account_id)
            and _timestamp(post.get("publishedAt", post.get("createdAt"))) >= cutoff
        )
        post_ids = tuple(_post_id(post) for post in posts)
        statistics = _statistics_by_post(
            self._fetch_statistics(account, post_ids),
            organization_id=account.account_id,
            requested=post_ids,
        )
        return ContentPage(
            items=tuple(
                _record(
                    post,
                    statistics.get(_post_id(post)),
                    observed_at=observed_at,
                )
                for post in posts
            ),
            next_cursor=(
                None
                if any(
                    _timestamp(post.get("publishedAt", post.get("createdAt"))) < cutoff
                    for post in provider_posts
                )
                else next_posts_cursor(payload)
            ),
            observed_at=observed_at,
        )


def _is_organic_published(post: Mapping[str, Any], organization_id: str) -> bool:
    if post.get("author") != organization_urn(organization_id):
        raise LinkedInResponseError("linkedin_post_author_mismatch")
    post_id = _post_id(post)
    if post.get("lifecycleState") != "PUBLISHED":
        return False
    ad_context = post.get("adContext")
    if ad_context is not None and not isinstance(ad_context, Mapping):
        raise LinkedInResponseError("linkedin_post_response_invalid")
    is_dsc = ad_context.get("isDsc", False) if ad_context is not None else False
    if not isinstance(is_dsc, bool):
        raise LinkedInResponseError("linkedin_post_response_invalid")
    return bool(post_id) and not is_dsc


def _post_id(post: Mapping[str, Any]) -> str:
    value = required_text(post, "id")
    if _POST_URN.fullmatch(value) is None:
        raise LinkedInResponseError("linkedin_post_id_invalid")
    return value


def _statistics_by_post(
    payloads: tuple[Mapping[str, Any], ...],
    *,
    organization_id: str,
    requested: tuple[str, ...],
) -> dict[str, Mapping[str, Any]]:
    if len(payloads) > 2:
        raise LinkedInResponseError("linkedin_post_statistics_invalid")
    requested_set = set(requested)
    normalized: dict[str, Mapping[str, Any]] = {}
    expected_organization = organization_urn(organization_id)
    for payload in payloads:
        for row in elements(payload, limit=LINKEDIN_POSTS_PAGE_SIZE):
            if row.get("organizationalEntity") != expected_organization:
                raise LinkedInResponseError("linkedin_post_statistics_account_mismatch")
            post_id = row.get("share", row.get("ugcPost"))
            if (
                not isinstance(post_id, str)
                or post_id not in requested_set
                or post_id in normalized
            ):
                raise LinkedInResponseError("linkedin_post_statistics_invalid")
            normalized[post_id] = required_mapping(row, "totalShareStatistics")
    return normalized


def _record(
    post: Mapping[str, Any],
    statistics: Mapping[str, Any] | None,
    *,
    observed_at: datetime,
) -> ProviderRecord:
    post_id = _post_id(post)
    if statistics is None:
        # LinkedIn explicitly defines omitted requested posts as zero-action,
        # zero-impression posts for this endpoint.
        likes: int | None = 0
        comments = shares = impressions = clicks = 0
        unique_impressions: int | None = 0
    else:
        likes = _like_count(statistics.get("likeCount"))
        comments = _count(statistics.get("commentCount"))
        shares = _count(statistics.get("shareCount"))
        impressions = _count(statistics.get("impressionCount"))
        clicks = _count(statistics.get("clickCount"))
        unique_value = statistics.get(
            "uniqueImpressionsCount",
            statistics.get("uniqueImpressionsCounts"),
        )
        unique_impressions = _count(unique_value) if unique_value is not None else None
    interactions = clicks + likes + comments + shares if likes is not None else None
    return ProviderRecord(
        external_id=post_id,
        observed_at=observed_at,
        fields={
            "content_type": _content_type(post),
            "permalink": f"https://www.linkedin.com/feed/update/{post_id}/",
            "message": optional_text(post, "commentary") or "",
            "media_url": "",
            "published_at": _timestamp(post.get("publishedAt", post.get("createdAt"))),
            "likes_count": likes,
            "comments_count": comments,
            "shares_count": shares,
            "views_count": impressions,
            "reach_count": unique_impressions,
            "interactions_count": interactions,
            "clicks_count": clicks,
        },
    )


def _content_type(post: Mapping[str, Any]) -> str:
    content = post.get("content", {})
    if not isinstance(content, Mapping):
        raise LinkedInResponseError("linkedin_post_response_invalid")
    if "multiImage" in content:
        return "image"
    if "article" in content:
        return "link"
    if "poll" in content:
        return "poll"
    if "media" in content:
        media = required_mapping(content, "media")
        media_id = required_text(media, "id")
        if media_id.startswith("urn:li:video:"):
            return "video"
        if media_id.startswith("urn:li:image:"):
            return "image"
        if media_id.startswith("urn:li:document:"):
            return "document"
        return "media"
    if "celebration" in content:
        return "celebration"
    if "reshareContext" in post:
        return "reshare"
    return "text"


def _timestamp(value: object) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise LinkedInResponseError("linkedin_post_timestamp_invalid")
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def _rolling_year_start(observed_at: datetime) -> datetime:
    try:
        return observed_at.replace(year=observed_at.year - 1)
    except ValueError:
        return observed_at.replace(year=observed_at.year - 1, day=28)


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LinkedInResponseError("linkedin_post_statistics_invalid")
    return value


def _like_count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LinkedInResponseError("linkedin_post_statistics_invalid")
    return value if value >= 0 else None


__all__ = ["LinkedInContentReader"]
