from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.domain.platforms import PlatformId
from app.infrastructure.providers.youtube import (
    YouTubeCommentsReader,
    YouTubeResponseError,
    comment_threads_query,
)

NOW = datetime(2026, 8, 31, 12, tzinfo=UTC)


def _account(platform: PlatformId = PlatformId.YOUTUBE) -> ProviderAccount:
    return ProviderAccount(
        platform=platform,
        account_id="UC-channel",
        credential=ProviderCredential(access_token="opaque"),
    )


def test_youtube_comment_query_requests_plain_text_top_level_threads() -> None:
    assert comment_threads_query("video-a", cursor="next-token") == {
        "part": "id,snippet",
        "videoId": "video-a",
        "maxResults": "100",
        "order": "time",
        "textFormat": "plainText",
        "pageToken": "next-token",
    }


def test_youtube_comments_map_top_level_comment_and_thread_reply_total() -> None:
    observed: list[tuple[str, str | None]] = []

    def fetch(
        account: ProviderAccount, video_id: str, cursor: str | None
    ) -> dict[str, object]:
        observed.append((video_id, cursor))
        return {
            "items": [
                {
                    "id": "thread-a",
                    "snippet": {
                        "totalReplyCount": 4,
                        "topLevelComment": {
                            "id": "comment-a",
                            "snippet": {
                                "authorChannelId": {"value": "UC-author"},
                                "authorDisplayName": "Viewer",
                                "textDisplay": "Useful video",
                                "likeCount": 3,
                                "publishedAt": "2026-08-02T10:00:00Z",
                            },
                        },
                    },
                }
            ],
            "nextPageToken": "next-token",
        }

    page = YouTubeCommentsReader(fetch, clock=lambda: NOW).list_comments(
        _account(), content_id="video-a"
    )

    assert observed == [("video-a", None)]
    assert page.content_id == "video-a"
    assert page.next_cursor == "next-token"
    assert page.observed_at == NOW
    assert len(page.items) == 1
    assert page.items[0].external_id == "comment-a"
    assert page.items[0].fields == {
        "author_id": "UC-author",
        "author_name": "Viewer",
        "text": "Useful video",
        "like_count": 3,
        "reply_count": 4,
        "attachment_type": None,
        "attachment_media_type": None,
        "attachment_url": None,
        "commented_at": datetime(2026, 8, 2, 10, tzinfo=UTC),
        "thread_id": "thread-a",
    }


def test_youtube_comments_allow_deleted_author_identity() -> None:
    payload = {
        "items": [
            {
                "id": "thread-a",
                "snippet": {
                    "totalReplyCount": 0,
                    "topLevelComment": {
                        "id": "comment-a",
                        "snippet": {
                            "textDisplay": "Anonymous",
                            "likeCount": 0,
                            "publishedAt": "2026-08-02T10:00:00Z",
                        },
                    },
                },
            }
        ]
    }
    reader = YouTubeCommentsReader(lambda account, video_id, cursor: payload)

    page = reader.list_comments(_account(), content_id="video-a")

    assert page.items[0].fields["author_id"] is None
    assert page.items[0].fields["author_name"] is None


def test_youtube_comments_fail_closed_when_required_counts_are_missing() -> None:
    payload = {
        "items": [
            {
                "id": "thread-a",
                "snippet": {
                    "topLevelComment": {
                        "id": "comment-a",
                        "snippet": {
                            "textDisplay": "Missing count",
                            "likeCount": 0,
                        },
                    },
                },
            }
        ]
    }
    reader = YouTubeCommentsReader(lambda account, video_id, cursor: payload)

    with pytest.raises(YouTubeResponseError, match="^response_field_invalid$"):
        reader.list_comments(_account(), content_id="video-a")


def test_youtube_comments_reject_invalid_video_id_and_provider_family() -> None:
    reader = YouTubeCommentsReader(lambda account, video_id, cursor: {})

    with pytest.raises(YouTubeResponseError, match="^content_id_invalid$"):
        reader.list_comments(_account(), content_id="https://example.test/video")
    with pytest.raises(ValueError, match="^provider_family_mismatch$"):
        reader.list_comments(_account(PlatformId.LINKEDIN), content_id="video-a")
