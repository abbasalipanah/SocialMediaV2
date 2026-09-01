from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.domain.metrics import MetricId, bootstrap_metric_catalog
from app.domain.platforms import CapabilityId, PlatformId
from app.infrastructure.providers.x import (
    XContentReader,
    XProfileReader,
    authenticated_user_query,
    user_posts_query,
    user_posts_url,
)
from app.infrastructure.providers.x.responses import XResponseError

NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)


def _account(platform: PlatformId = PlatformId.X) -> ProviderAccount:
    return ProviderAccount(
        platform=platform,
        account_id="123456789",
        credential=ProviderCredential(access_token="opaque"),
    )


def test_x_queries_are_bounded_and_request_only_owned_posts() -> None:
    assert authenticated_user_query() == {
        "user.fields": "name,username,public_metrics,profile_image_url"
    }
    assert user_posts_url("https://api.x.com/2", "123456789") == (
        "https://api.x.com/2/users/123456789/tweets"
    )
    assert user_posts_query(cursor="next-token") == {
        "max_results": "100",
        "exclude": "retweets,replies",
        "tweet.fields": "attachments,created_at,non_public_metrics,public_metrics",
        "expansions": "attachments.media_keys",
        "media.fields": "type,url,preview_image_url",
        "pagination_token": "next-token",
    }


def test_x_profile_maps_only_catalogued_snapshot_metrics() -> None:
    reader = XProfileReader(
        lambda _account: {
            "data": {
                "id": "123456789",
                "name": "Example Brand",
                "username": "example",
                "public_metrics": {
                    "followers_count": 1200,
                    "following_count": 45,
                    "tweet_count": 88,
                    "listed_count": 3,
                },
            }
        },
        clock=lambda: NOW,
    )

    snapshot = reader.fetch_profile(_account())

    assert snapshot.display_name == "Example Brand"
    assert snapshot.handle == "@example"
    assert snapshot.metric_values == {
        MetricId.FOLLOWERS: 1200,
        MetricId.MEDIA_COUNT: 88,
    }
    bootstrap_metric_catalog().validate_values(
        platform=PlatformId.X,
        capability=CapabilityId.PROFILE,
        values=snapshot.metric_values,
    )


def test_x_content_maps_public_and_owned_post_metrics_with_media() -> None:
    reader = XContentReader(
        lambda _account, _cursor: {
            "data": [
                {
                    "id": "1900000000000000001",
                    "text": "A post",
                    "created_at": "2026-08-31T10:00:00Z",
                    "attachments": {"media_keys": ["3_photo"]},
                    "public_metrics": {
                        "retweet_count": 2,
                        "reply_count": 3,
                        "like_count": 7,
                        "quote_count": 1,
                        "bookmark_count": 4,
                        "impression_count": 100,
                    },
                    "non_public_metrics": {
                        "engagements": 20,
                        "user_profile_clicks": 5,
                    },
                }
            ],
            "includes": {
                "media": [
                    {
                        "media_key": "3_photo",
                        "type": "photo",
                        "url": "https://pbs.twimg.com/media/example.jpg",
                    }
                ]
            },
            "meta": {"next_token": "next-token"},
        },
        clock=lambda: NOW,
    )

    page = reader.list_content(_account())
    fields = page.items[0].fields

    assert page.next_cursor == "next-token"
    assert fields["content_type"] == "image"
    assert fields["permalink"] == (
        "https://x.com/i/web/status/1900000000000000001"
    )
    assert fields["media_url"] == "https://pbs.twimg.com/media/example.jpg"
    assert fields["likes_count"] == 7
    assert fields["comments_count"] == 3
    assert fields["shares_count"] == 3
    assert fields["views_count"] == 100
    assert fields["interactions_count"] == 20
    assert fields["saves_count"] == 4
    assert fields["profile_visits"] == 5


def test_x_content_derives_public_interactions_and_rejects_missing_media() -> None:
    reader = XContentReader(
        lambda _account, _cursor: {
            "data": [
                {
                    "id": "1900000000000000001",
                    "text": "A post",
                    "public_metrics": {
                        "retweet_count": 2,
                        "reply_count": 3,
                        "like_count": 7,
                        "quote_count": 1,
                    },
                }
            ]
        },
        clock=lambda: NOW,
    )
    assert reader.list_content(_account()).items[0].fields["interactions_count"] == 13

    missing_media = XContentReader(
        lambda _account, _cursor: {
            "data": [
                {
                    "id": "1900000000000000001",
                    "attachments": {"media_keys": ["missing"]},
                    "public_metrics": {},
                }
            ]
        }
    )
    with pytest.raises(XResponseError, match="^x_timeline_response_invalid$"):
        missing_media.list_content(_account())


def test_x_readers_reject_wrong_provider_family() -> None:
    profile = XProfileReader(lambda _account: {})
    content = XContentReader(lambda _account, _cursor: {})
    with pytest.raises(ValueError, match="^provider_family_mismatch$"):
        profile.fetch_profile(_account(PlatformId.YOUTUBE))
    with pytest.raises(ValueError, match="^provider_family_mismatch$"):
        content.list_content(_account(PlatformId.YOUTUBE))
