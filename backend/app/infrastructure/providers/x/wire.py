"""Stable query construction for X API v2 reads."""

from __future__ import annotations

X_POSTS_PAGE_SIZE = 25
X_MENTIONS_PAGE_SIZE = 25


def authenticated_user_query() -> dict[str, str]:
    return {
        "user.fields": "name,username,public_metrics,profile_image_url",
    }


def user_posts_query(*, cursor: str | None = None) -> dict[str, str]:
    query = {
        "max_results": str(X_POSTS_PAGE_SIZE),
        "exclude": "retweets,replies",
        "tweet.fields": (
            "attachments,created_at,entities,non_public_metrics,public_metrics"
        ),
        "expansions": "attachments.media_keys",
        "media.fields": (
            "type,url,preview_image_url,public_metrics,non_public_metrics"
        ),
    }
    if cursor:
        query["pagination_token"] = cursor
    return query


def user_posts_url(api_base_url: str, user_id: str) -> str:
    if not api_base_url.strip() or not user_id.isdigit():
        raise ValueError("x_provider_account_id_invalid")
    return f"{api_base_url.rstrip('/')}/users/{user_id}/tweets"


def user_mentions_query(*, cursor: str | None = None) -> dict[str, str]:
    query = {
        "max_results": str(X_MENTIONS_PAGE_SIZE),
        "tweet.fields": "author_id,created_at,public_metrics",
        "expansions": "author_id",
        "user.fields": "id,name,username",
    }
    if cursor:
        query["pagination_token"] = cursor
    return query


def user_mentions_url(api_base_url: str, user_id: str) -> str:
    if not api_base_url.strip() or not user_id.isdigit():
        raise ValueError("x_provider_account_id_invalid")
    return f"{api_base_url.rstrip('/')}/users/{user_id}/mentions"


__all__ = [
    "X_POSTS_PAGE_SIZE",
    "X_MENTIONS_PAGE_SIZE",
    "authenticated_user_query",
    "user_posts_query",
    "user_posts_url",
    "user_mentions_query",
    "user_mentions_url",
]
