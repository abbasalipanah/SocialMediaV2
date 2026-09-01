from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.domain.metrics import MetricId, bootstrap_metric_catalog
from app.domain.platforms import CapabilityId, PlatformId
from app.infrastructure.providers.x import (
    XContentReader,
    XMentionsReader,
    XProfileReader,
    authenticated_user_query,
    user_mentions_query,
    user_mentions_url,
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
    assert user_mentions_url("https://api.x.com/2", "123456789") == (
        "https://api.x.com/2/users/123456789/mentions"
    )
    assert user_mentions_query(cursor="mention-token") == {
        "max_results": "25",
        "tweet.fields": "author_id,created_at,public_metrics",
        "expansions": "author_id",
        "user.fields": "id,name,username",
        "pagination_token": "mention-token",
    }
    assert user_posts_query(cursor="next-token") == {
        "max_results": "25",
        "exclude": "retweets,replies",
        "tweet.fields": "attachments,created_at,entities,non_public_metrics,public_metrics",
        "expansions": "attachments.media_keys",
        "media.fields": "type,url,preview_image_url,public_metrics,non_public_metrics",
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
                        "url_link_clicks": 6,
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
    assert fields["reposts_count"] == 2
    assert fields["quotes_count"] == 1
    assert fields["link_clicks"] == 6
    assert fields["profile_clicks"] == 5
    assert fields["video_views_count"] is None


def test_x_content_maps_video_playback_and_derives_completion_rate() -> None:
    reader = XContentReader(
        lambda _account, _cursor: {
            "data": [
                {
                    "id": "1900000000000000002",
                    "text": "Watch this",
                    "created_at": "2026-08-31T10:00:00Z",
                    "attachments": {"media_keys": ["7_video"]},
                    "public_metrics": {},
                }
            ],
            "includes": {
                "media": [
                    {
                        "media_key": "7_video",
                        "type": "video",
                        "preview_image_url": "https://pbs.twimg.com/video_thumb/example.jpg",
                        "public_metrics": {"view_count": 80},
                        "non_public_metrics": {
                            "playback_0_count": 60,
                            "playback_25_count": 50,
                            "playback_50_count": 40,
                            "playback_75_count": 30,
                            "playback_100_count": 24,
                        },
                    }
                ]
            },
        },
        clock=lambda: NOW,
    )

    fields = reader.list_content(_account()).items[0].fields

    assert fields["content_type"] == "video"
    assert fields["video_views_count"] == 80
    assert fields["video_playback_0_count"] == 60
    assert fields["video_playback_25_count"] == 50
    assert fields["video_playback_50_count"] == 40
    assert fields["video_playback_75_count"] == 30
    assert fields["video_playback_100_count"] == 24
    assert fields["completion_rate"] == pytest.approx(0.4)


def test_x_content_classifies_text_and_link_posts_from_entities() -> None:
    def payload(with_url: bool):
        return {
            "data": [
                {
                    "id": "1900000000000000003",
                    "text": "Read more" if with_url else "Plain post",
                    "entities": {"urls": [{"expanded_url": "https://example.test"}]}
                    if with_url
                    else {},
                    "public_metrics": {},
                }
            ]
        }

    assert XContentReader(lambda _account, _cursor: payload(False)).list_content(
        _account()
    ).items[0].fields["content_type"] == "text"
    assert XContentReader(lambda _account, _cursor: payload(True)).list_content(
        _account()
    ).items[0].fields["content_type"] == "link"


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


def test_x_mentions_map_author_identity_and_public_activity() -> None:
    reader = XMentionsReader(
        lambda _account, _cursor: {
            "data": [
                {
                    "id": "1900000000000000004",
                    "author_id": "987654321",
                    "text": "@example useful report",
                    "created_at": "2026-08-31T11:00:00Z",
                    "public_metrics": {"like_count": 4, "reply_count": 2},
                }
            ],
            "includes": {
                "users": [
                    {
                        "id": "987654321",
                        "name": "Reader",
                        "username": "reader",
                    }
                ]
            },
            "meta": {"next_token": "mention-next"},
        },
        clock=lambda: NOW,
    )

    page = reader.list_mentions(_account())

    assert page.next_cursor == "mention-next"
    assert page.items[0].fields == {
        "author_id": "987654321",
        "author_name": "reader",
        "text": "@example useful report",
        "like_count": 4,
        "reply_count": 2,
        "commented_at": datetime(2026, 8, 31, 11, tzinfo=UTC),
    }
