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

    def upsert(self, record: ContentRecord, *, preserve_insights: bool = False) -> None:
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
                        reposts_count, quotes_count, link_clicks, profile_clicks,
                        video_views_count, video_playback_0_count,
                        video_playback_25_count, video_playback_50_count,
                        video_playback_75_count, video_playback_100_count,
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
                        :reposts_count, :quotes_count, :link_clicks, :profile_clicks,
                        :video_views_count, :video_playback_0_count,
                        :video_playback_25_count, :video_playback_50_count,
                        :video_playback_75_count, :video_playback_100_count,
                        now()
                    )
                    ON CONFLICT (asset_id, content_id) DO UPDATE SET
                        brand_id=EXCLUDED.brand_id,
                        content_type=EXCLUDED.content_type,
                        permalink=EXCLUDED.permalink,
                        message=EXCLUDED.message,
                        media_url=EXCLUDED.media_url,
                        created_time=EXCLUDED.created_time,
                        likes_count=CASE WHEN :preserve_insights
                            THEN content_items.likes_count ELSE EXCLUDED.likes_count END,
                        comments_count=CASE WHEN :preserve_insights
                            THEN content_items.comments_count ELSE EXCLUDED.comments_count END,
                        shares_count=CASE WHEN :preserve_insights
                            THEN content_items.shares_count ELSE EXCLUDED.shares_count END,
                        views_count=CASE WHEN :preserve_insights
                            THEN content_items.views_count ELSE EXCLUDED.views_count END,
                        reach_count=CASE WHEN :preserve_insights
                            THEN content_items.reach_count ELSE EXCLUDED.reach_count END,
                        cover_url=EXCLUDED.cover_url,
                        thumbnail_url=EXCLUDED.thumbnail_url,
                        cover_candidates=EXCLUDED.cover_candidates,
                        thumbnail_candidates=EXCLUDED.thumbnail_candidates,
                        media_url_candidates=EXCLUDED.media_url_candidates,
                        full_video_watched_rate=CASE WHEN :preserve_insights
                            THEN content_items.full_video_watched_rate
                            ELSE EXCLUDED.full_video_watched_rate END,
                        total_time_watched=CASE WHEN :preserve_insights
                            THEN content_items.total_time_watched
                            ELSE EXCLUDED.total_time_watched END,
                        average_time_watched=CASE WHEN :preserve_insights
                            THEN content_items.average_time_watched
                            ELSE EXCLUDED.average_time_watched END,
                        interactions_count=CASE WHEN :preserve_insights
                            THEN content_items.interactions_count
                            ELSE EXCLUDED.interactions_count END,
                        replies_count=CASE WHEN :preserve_insights
                            THEN content_items.replies_count ELSE EXCLUDED.replies_count END,
                        saves_count=CASE WHEN :preserve_insights
                            THEN content_items.saves_count ELSE EXCLUDED.saves_count END,
                        sticker_taps=CASE WHEN :preserve_insights
                            THEN content_items.sticker_taps ELSE EXCLUDED.sticker_taps END,
                        profile_visits=CASE WHEN :preserve_insights
                            THEN content_items.profile_visits ELSE EXCLUDED.profile_visits END,
                        follows_count=CASE WHEN :preserve_insights
                            THEN content_items.follows_count ELSE EXCLUDED.follows_count END,
                        taps_forward=CASE WHEN :preserve_insights
                            THEN content_items.taps_forward ELSE EXCLUDED.taps_forward END,
                        taps_back=CASE WHEN :preserve_insights
                            THEN content_items.taps_back ELSE EXCLUDED.taps_back END,
                        swipe_forward=CASE WHEN :preserve_insights
                            THEN content_items.swipe_forward ELSE EXCLUDED.swipe_forward END,
                        exits=CASE WHEN :preserve_insights
                            THEN content_items.exits ELSE EXCLUDED.exits END,
                        navigation_count=CASE WHEN :preserve_insights
                            THEN content_items.navigation_count
                            ELSE EXCLUDED.navigation_count END,
                        completion_rate=CASE WHEN :preserve_insights
                            THEN content_items.completion_rate
                            ELSE EXCLUDED.completion_rate END,
                        reposts_count=CASE WHEN :preserve_insights
                            THEN content_items.reposts_count ELSE EXCLUDED.reposts_count END,
                        quotes_count=CASE WHEN :preserve_insights
                            THEN content_items.quotes_count ELSE EXCLUDED.quotes_count END,
                        link_clicks=CASE WHEN :preserve_insights
                            THEN content_items.link_clicks ELSE EXCLUDED.link_clicks END,
                        profile_clicks=CASE WHEN :preserve_insights
                            THEN content_items.profile_clicks ELSE EXCLUDED.profile_clicks END,
                        video_views_count=CASE WHEN :preserve_insights
                            THEN content_items.video_views_count
                            ELSE EXCLUDED.video_views_count END,
                        video_playback_0_count=CASE WHEN :preserve_insights
                            THEN content_items.video_playback_0_count
                            ELSE EXCLUDED.video_playback_0_count END,
                        video_playback_25_count=CASE WHEN :preserve_insights
                            THEN content_items.video_playback_25_count
                            ELSE EXCLUDED.video_playback_25_count END,
                        video_playback_50_count=CASE WHEN :preserve_insights
                            THEN content_items.video_playback_50_count
                            ELSE EXCLUDED.video_playback_50_count END,
                        video_playback_75_count=CASE WHEN :preserve_insights
                            THEN content_items.video_playback_75_count
                            ELSE EXCLUDED.video_playback_75_count END,
                        video_playback_100_count=CASE WHEN :preserve_insights
                            THEN content_items.video_playback_100_count
                            ELSE EXCLUDED.video_playback_100_count END,
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
                    "reposts_count": record.reposts_count,
                    "quotes_count": record.quotes_count,
                    "link_clicks": record.link_clicks,
                    "profile_clicks": record.profile_clicks,
                    "video_views_count": record.video_views_count,
                    "video_playback_0_count": record.video_playback_0_count,
                    "video_playback_25_count": record.video_playback_25_count,
                    "video_playback_50_count": record.video_playback_50_count,
                    "video_playback_75_count": record.video_playback_75_count,
                    "video_playback_100_count": record.video_playback_100_count,
                    "preserve_insights": preserve_insights,
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
                              i.exits, i.navigation_count, i.completion_rate,
                              i.reposts_count, i.quotes_count, i.link_clicks,
                              i.profile_clicks, i.video_views_count,
                              i.video_playback_0_count, i.video_playback_25_count,
                              i.video_playback_50_count, i.video_playback_75_count,
                              i.video_playback_100_count
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
                    likes_count=_optional_int(row["likes_count"]),
                    comments_count=_optional_int(row["comments_count"]),
                    shares_count=_optional_int(row["shares_count"]),
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
                    reposts_count=_optional_int(row["reposts_count"]),
                    quotes_count=_optional_int(row["quotes_count"]),
                    link_clicks=_optional_int(row["link_clicks"]),
                    profile_clicks=_optional_int(row["profile_clicks"]),
                    video_views_count=_optional_int(row["video_views_count"]),
                    video_playback_0_count=_optional_int(row["video_playback_0_count"]),
                    video_playback_25_count=_optional_int(row["video_playback_25_count"]),
                    video_playback_50_count=_optional_int(row["video_playback_50_count"]),
                    video_playback_75_count=_optional_int(row["video_playback_75_count"]),
                    video_playback_100_count=_optional_int(row["video_playback_100_count"]),
                )
                for row in rows
            )


def _optional_float(value: object) -> float | None:
    return float(cast(Any, value)) if value is not None else None


def _optional_int(value: object) -> int | None:
    return int(cast(Any, value)) if value is not None else None


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if isinstance(item, str) and item)


__all__ = ["SocialContentStore"]
