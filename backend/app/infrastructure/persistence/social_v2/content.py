"""V2 content persistence."""

from __future__ import annotations

import json
from typing import Any, cast

from sqlalchemy import Engine, text

from app.application.ports.persistence import ContentRecord
from app.core.write_policy import WritePolicy

from ..legacy_socialmedia.platforms import normalize_platform
from .base import SocialStoreBase


class SocialContentStore(SocialStoreBase):
    def __init__(self, engine: Engine, write_policy: WritePolicy) -> None:
        super().__init__(engine, write_policy)

    def upsert(self, record: ContentRecord) -> None:
        self._assert_mutation("content.upsert")
        with self.engine.begin() as connection:
            self._assert_account_scope(
                connection,
                account_id=record.account_id,
                platform=record.platform,
                brand_id=record.brand_id,
            )
            connection.execute(
                text(
                    """INSERT INTO content_items (
                        asset_id, brand_id, content_id, content_type, permalink,
                        message, media_url, created_time, likes_count,
                        comments_count, shares_count, views_count, reach_count,
                        cover_url, thumbnail_url, cover_candidates,
                        thumbnail_candidates, media_url_candidates,
                        full_video_watched_rate, total_time_watched,
                        average_time_watched, interactions_count, replies_count,
                        saves_count, sticker_taps, profile_visits, follows_count,
                        taps_forward, taps_back,
                        swipe_forward, exits, navigation_count, completion_rate,
                        created_at
                    ) VALUES (
                        :account_id, :brand_id, :content_id, :content_type, :permalink,
                        :message, :media_url, :published_at, :likes_count,
                        :comments_count, :shares_count, :views_count, :reach_count,
                        :cover_url, :thumbnail_url, CAST(:cover_candidates AS jsonb),
                        CAST(:thumbnail_candidates AS jsonb),
                        CAST(:media_url_candidates AS jsonb),
                        :full_video_watched_rate, :total_time_watched,
                        :average_time_watched, :interactions_count, :replies_count,
                        :saves_count, :sticker_taps, :profile_visits, :follows_count,
                        :taps_forward, :taps_back,
                        :swipe_forward, :exits, :navigation_count, :completion_rate,
                        now()
                    )
                    ON CONFLICT (asset_id, content_id) DO UPDATE SET
                        brand_id=EXCLUDED.brand_id,
                        content_type=EXCLUDED.content_type,
                        permalink=EXCLUDED.permalink,
                        message=EXCLUDED.message,
                        media_url=EXCLUDED.media_url,
                        created_time=EXCLUDED.created_time,
                        likes_count=EXCLUDED.likes_count,
                        comments_count=EXCLUDED.comments_count,
                        shares_count=EXCLUDED.shares_count,
                        views_count=EXCLUDED.views_count,
                        reach_count=EXCLUDED.reach_count,
                        cover_url=EXCLUDED.cover_url,
                        thumbnail_url=EXCLUDED.thumbnail_url,
                        cover_candidates=EXCLUDED.cover_candidates,
                        thumbnail_candidates=EXCLUDED.thumbnail_candidates,
                        media_url_candidates=EXCLUDED.media_url_candidates,
                        full_video_watched_rate=EXCLUDED.full_video_watched_rate,
                        total_time_watched=EXCLUDED.total_time_watched,
                        average_time_watched=EXCLUDED.average_time_watched,
                        interactions_count=EXCLUDED.interactions_count,
                        replies_count=EXCLUDED.replies_count,
                        saves_count=EXCLUDED.saves_count,
                        sticker_taps=EXCLUDED.sticker_taps,
                        profile_visits=EXCLUDED.profile_visits,
                        follows_count=EXCLUDED.follows_count,
                        taps_forward=EXCLUDED.taps_forward,
                        taps_back=EXCLUDED.taps_back,
                        swipe_forward=EXCLUDED.swipe_forward,
                        exits=EXCLUDED.exits,
                        navigation_count=EXCLUDED.navigation_count,
                        completion_rate=EXCLUDED.completion_rate,
                        updated_at=now()"""
                ),
                {
                    "account_id": record.account_id,
                    "brand_id": record.brand_id,
                    "content_id": record.external_content_id,
                    "content_type": record.content_type,
                    "permalink": record.permalink,
                    "message": record.message,
                    "media_url": record.media_url,
                    "published_at": record.published_at,
                    "likes_count": record.likes_count,
                    "comments_count": record.comments_count,
                    "shares_count": record.shares_count,
                    "views_count": record.views_count,
                    "reach_count": record.reach_count,
                    "cover_url": record.cover_url,
                    "thumbnail_url": record.thumbnail_url,
                    "cover_candidates": json.dumps(record.cover_candidates),
                    "thumbnail_candidates": json.dumps(record.thumbnail_candidates),
                    "media_url_candidates": json.dumps(record.media_url_candidates),
                    "full_video_watched_rate": record.full_video_watched_rate,
                    "total_time_watched": record.total_time_watched,
                    "average_time_watched": record.average_time_watched,
                    "interactions_count": record.interactions_count,
                    "replies_count": record.replies_count,
                    "saves_count": record.saves_count,
                    "sticker_taps": record.sticker_taps,
                    "profile_visits": record.profile_visits,
                    "follows_count": record.follows_count,
                    "taps_forward": record.taps_forward,
                    "taps_back": record.taps_back,
                    "swipe_forward": record.swipe_forward,
                    "exits": record.exits,
                    "navigation_count": record.navigation_count,
                    "completion_rate": record.completion_rate,
                },
            )

    def list_for_account(self, account_id: int) -> tuple[ContentRecord, ...]:
        if account_id < 1:
            raise ValueError("account_id_invalid")
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """SELECT i.asset_id, i.brand_id, a.platform, i.content_id,
                              i.content_type, i.permalink, i.message, i.media_url,
                              i.created_time, i.likes_count, i.comments_count,
                              i.shares_count, i.views_count, i.reach_count,
                              i.cover_url, i.thumbnail_url, i.cover_candidates,
                              i.thumbnail_candidates, i.media_url_candidates,
                              i.full_video_watched_rate, i.total_time_watched,
                              i.average_time_watched, i.interactions_count,
                              i.replies_count, i.saves_count, i.sticker_taps,
                              i.profile_visits, i.follows_count,
                              i.taps_forward, i.taps_back, i.swipe_forward,
                              i.exits, i.navigation_count, i.completion_rate
                       FROM content_items AS i
                       JOIN assets AS a ON a.id=i.asset_id
                       WHERE i.asset_id=:account_id
                       ORDER BY i.content_id"""
                ),
                {"account_id": account_id},
            ).mappings()
            return tuple(
                ContentRecord(
                    platform=normalize_platform(row["platform"]),
                    account_id=int(row["asset_id"]),
                    brand_id=int(row["brand_id"]),
                    external_content_id=str(row["content_id"]),
                    content_type=str(row["content_type"]),
                    permalink=str(row["permalink"]),
                    message=str(row["message"]),
                    media_url=str(row["media_url"]),
                    published_at=row["created_time"],
                    likes_count=int(row["likes_count"]),
                    comments_count=int(row["comments_count"]),
                    shares_count=int(row["shares_count"]),
                    views_count=_optional_float(row["views_count"]),
                    reach_count=_optional_float(row["reach_count"]),
                    cover_url=row["cover_url"],
                    thumbnail_url=row["thumbnail_url"],
                    cover_candidates=_string_tuple(row["cover_candidates"]),
                    thumbnail_candidates=_string_tuple(row["thumbnail_candidates"]),
                    media_url_candidates=_string_tuple(row["media_url_candidates"]),
                    full_video_watched_rate=_optional_float(row["full_video_watched_rate"]),
                    total_time_watched=_optional_float(row["total_time_watched"]),
                    average_time_watched=_optional_float(row["average_time_watched"]),
                    interactions_count=_optional_float(row["interactions_count"]),
                    replies_count=_optional_float(row["replies_count"]),
                    saves_count=_optional_float(row["saves_count"]),
                    sticker_taps=_optional_float(row["sticker_taps"]),
                    profile_visits=_optional_float(row["profile_visits"]),
                    follows_count=_optional_float(row["follows_count"]),
                    taps_forward=_optional_float(row["taps_forward"]),
                    taps_back=_optional_float(row["taps_back"]),
                    swipe_forward=_optional_float(row["swipe_forward"]),
                    exits=_optional_float(row["exits"]),
                    navigation_count=_optional_float(row["navigation_count"]),
                    completion_rate=_optional_float(row["completion_rate"]),
                )
                for row in rows
            )


def _optional_float(value: object) -> float | None:
    return float(cast(Any, value)) if value is not None else None


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if isinstance(item, str) and item)


__all__ = ["SocialContentStore"]
