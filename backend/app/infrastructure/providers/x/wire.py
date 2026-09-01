"""Stable query construction for X API v2 reads."""

from __future__ import annotations


def authenticated_user_query() -> dict[str, str]:
    return {
        "user.fields": "name,username,public_metrics,profile_image_url",
    }


def user_posts_query(*, cursor: str | None = None) -> dict[str, str]:
    query = {
        "max_results": "100",
        "exclude": "retweets,replies",
        "tweet.fields": (
            "attachments,created_at,non_public_metrics,public_metrics"
        ),
        "expansions": "attachments.media_keys",
        "media.fields": "type,url,preview_image_url",
    }
    if cursor:
        query["pagination_token"] = cursor
    return query


def user_posts_url(api_base_url: str, user_id: str) -> str:
    if not api_base_url.strip() or not user_id.isdigit():
        raise ValueError("x_provider_account_id_invalid")
    return f"{api_base_url.rstrip('/')}/users/{user_id}/tweets"


__all__ = ["authenticated_user_query", "user_posts_query", "user_posts_url"]
