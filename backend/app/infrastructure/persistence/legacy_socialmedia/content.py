"""Schema-compatible content persistence."""

from __future__ import annotations

from sqlalchemy import Engine, text

from app.application.ports.persistence import ContentRecord
from app.core.write_policy import WritePolicy

from .base import LegacyStoreBase
from .platforms import normalize_legacy_platform


class LegacyContentStore(LegacyStoreBase):
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
                        comments_count, shares_count, created_at
                    ) VALUES (
                        :account_id, :brand_id, :content_id, :content_type, :permalink,
                        :message, :media_url, :published_at, :likes_count,
                        :comments_count, :shares_count, now()
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
                        shares_count=EXCLUDED.shares_count"""
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
                              i.shares_count
                       FROM content_items AS i
                       JOIN assets AS a ON a.id=i.asset_id
                       WHERE i.asset_id=:account_id
                       ORDER BY i.content_id"""
                ),
                {"account_id": account_id},
            ).mappings()
            return tuple(
                ContentRecord(
                    platform=normalize_legacy_platform(row["platform"]),
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
                )
                for row in rows
            )


__all__ = ["LegacyContentStore"]
