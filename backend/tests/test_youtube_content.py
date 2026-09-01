from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.domain.platforms import PlatformId
from app.infrastructure.providers.youtube import (
    YouTubeContentReader,
    YouTubeResponseError,
    playlist_items_query,
    uploads_playlist_query,
    videos_query,
)

NOW = datetime(2026, 8, 31, 12, tzinfo=UTC)


def _account(platform: PlatformId = PlatformId.YOUTUBE) -> ProviderAccount:
    return ProviderAccount(
        platform=platform,
        account_id="UC-channel",
        credential=ProviderCredential(access_token="opaque"),
    )


def test_youtube_content_queries_use_low_cost_uploads_playlist_path() -> None:
    assert uploads_playlist_query("UC-channel") == {
        "part": "id,contentDetails",
        "id": "UC-channel",
        "maxResults": "1",
    }
    assert playlist_items_query("UU-uploads", cursor="next-token") == {
        "part": "contentDetails",
        "playlistId": "UU-uploads",
        "maxResults": "50",
        "pageToken": "next-token",
    }
    assert videos_query(("video-a", "video-b")) == {
        "part": "id,snippet,statistics",
        "id": "video-a,video-b",
        "maxResults": "2",
    }


def test_youtube_content_maps_video_page_without_inventing_share_count() -> None:
    channel_calls = 0
    playlist_calls: list[tuple[str, str | None]] = []

    def fetch_channel(account: ProviderAccount) -> dict[str, object]:
        nonlocal channel_calls
        channel_calls += 1
        return {
            "items": [
                {
                    "id": account.account_id,
                    "contentDetails": {"relatedPlaylists": {"uploads": "UU-uploads"}},
                }
            ]
        }

    def fetch_playlist(
        account: ProviderAccount, playlist_id: str, cursor: str | None
    ) -> dict[str, object]:
        playlist_calls.append((playlist_id, cursor))
        return {
            "items": [
                {"contentDetails": {"videoId": "video-a"}},
                {"contentDetails": {"videoId": "video-b"}},
            ],
            "nextPageToken": "next-token",
        }

    def fetch_videos(
        account: ProviderAccount, video_ids: tuple[str, ...]
    ) -> dict[str, object]:
        assert video_ids == ("video-a", "video-b")
        return {
            "items": [
                {
                    "id": "video-b",
                    "snippet": {
                        "title": "Second",
                        "publishedAt": "2026-08-02T10:00:00Z",
                    },
                    "statistics": {"viewCount": "20", "commentCount": "2"},
                },
                {
                    "id": "video-a",
                    "snippet": {
                        "title": "First",
                        "publishedAt": "2026-08-01T10:00:00Z",
                        "thumbnails": {
                            "default": {"url": "https://img.test/default.jpg"},
                            "high": {"url": "https://img.test/high.jpg"},
                        },
                    },
                    "statistics": {
                        "viewCount": "100",
                        "likeCount": "7",
                        "commentCount": "3",
                    },
                },
            ]
        }

    reader = YouTubeContentReader(
        fetch_channel,
        fetch_playlist,
        fetch_videos,
        clock=lambda: NOW,
    )
    page = reader.list_content(_account())
    reader.list_content(_account(), cursor="next-token")

    assert channel_calls == 1
    assert playlist_calls == [("UU-uploads", None), ("UU-uploads", "next-token")]
    assert page.next_cursor == "next-token"
    assert [item.external_id for item in page.items] == ["video-a", "video-b"]
    first = page.items[0]
    assert first.fields["permalink"] == "https://www.youtube.com/watch?v=video-a"
    assert first.fields["thumbnail_url"] == "https://img.test/high.jpg"
    assert first.fields["published_at"] == datetime(2026, 8, 1, 10, tzinfo=UTC)
    assert first.fields["likes_count"] == 7
    assert first.fields["comments_count"] == 3
    assert first.fields["shares_count"] is None
    assert first.fields["views_count"] == 100
    assert first.fields["interactions_count"] is None
    assert page.items[1].fields["likes_count"] is None


def test_youtube_content_fails_closed_when_video_details_are_incomplete() -> None:
    reader = YouTubeContentReader(
        lambda account: {
            "items": [
                {
                    "id": account.account_id,
                    "contentDetails": {"relatedPlaylists": {"uploads": "UU-uploads"}},
                }
            ]
        },
        lambda account, playlist_id, cursor: {
            "items": [{"contentDetails": {"videoId": "video-a"}}]
        },
        lambda account, video_ids: {"items": []},
    )

    with pytest.raises(YouTubeResponseError, match="^video_response_incomplete$"):
        reader.list_content(_account())


def test_youtube_content_rejects_wrong_provider_family() -> None:
    reader = YouTubeContentReader(
        lambda account: {},
        lambda account, playlist_id, cursor: {},
        lambda account, video_ids: {},
    )

    with pytest.raises(ValueError, match="^provider_family_mismatch$"):
        reader.list_content(_account(PlatformId.X))
