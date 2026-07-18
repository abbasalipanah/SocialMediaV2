"""Schema-compatible comment persistence."""

from __future__ import annotations

from sqlalchemy import Engine, text

from app.application.ports.persistence import CommentRecord
from app.core.write_policy import WritePolicy

from .base import LegacyStoreBase
from .platforms import normalize_legacy_platform


class LegacyCommentStore(LegacyStoreBase):
    def __init__(self, engine: Engine, write_policy: WritePolicy) -> None:
        super().__init__(engine, write_policy)

    def upsert(self, record: CommentRecord) -> None:
        self._assert_mutation("comment.upsert")
        with self.engine.begin() as connection:
            self._assert_account_scope(
                connection,
                account_id=record.account_id,
                platform=record.platform,
            )
            connection.execute(
                text(
                    """INSERT INTO content_comments (
                        asset_id, content_id, platform, comment_id, user_id, user_name,
                        text, like_count, reply_count, answered, attachment_type,
                        attachment_media_type, attachment_url, commented_at,
                        created_at, updated_at
                    ) VALUES (
                        :account_id, :content_id, :platform, :comment_id, :author_id,
                        :author_name, :text, :like_count, :reply_count, :answered,
                        :attachment_type, :attachment_media_type, :attachment_url,
                        :commented_at, now(), now()
                    )
                    ON CONFLICT (asset_id, comment_id) DO UPDATE SET
                        content_id=EXCLUDED.content_id,
                        platform=EXCLUDED.platform,
                        user_id=EXCLUDED.user_id,
                        user_name=EXCLUDED.user_name,
                        text=EXCLUDED.text,
                        like_count=EXCLUDED.like_count,
                        reply_count=EXCLUDED.reply_count,
                        answered=EXCLUDED.answered,
                        attachment_type=EXCLUDED.attachment_type,
                        attachment_media_type=EXCLUDED.attachment_media_type,
                        attachment_url=EXCLUDED.attachment_url,
                        commented_at=EXCLUDED.commented_at,
                        updated_at=now()"""
                ),
                {
                    "account_id": record.account_id,
                    "content_id": record.external_content_id,
                    "platform": record.platform.value,
                    "comment_id": record.external_comment_id,
                    "author_id": record.author_id,
                    "author_name": record.author_name,
                    "text": record.text,
                    "like_count": record.like_count,
                    "reply_count": record.reply_count,
                    "answered": record.answered,
                    "attachment_type": record.attachment_type,
                    "attachment_media_type": record.attachment_media_type,
                    "attachment_url": record.attachment_url,
                    "commented_at": record.commented_at,
                },
            )

    def list_for_content(
        self, account_id: int, external_content_id: str
    ) -> tuple[CommentRecord, ...]:
        if account_id < 1 or not external_content_id:
            raise ValueError("comment_query_invalid")
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """SELECT asset_id, content_id, platform, comment_id, user_id,
                              user_name, text, like_count, reply_count, answered,
                              attachment_type, attachment_media_type, attachment_url,
                              commented_at
                       FROM content_comments
                       WHERE asset_id=:account_id AND content_id=:content_id
                       ORDER BY commented_at NULLS LAST, comment_id"""
                ),
                {"account_id": account_id, "content_id": external_content_id},
            ).mappings()
            return tuple(
                CommentRecord(
                    platform=normalize_legacy_platform(row["platform"]),
                    account_id=int(row["asset_id"]),
                    external_content_id=str(row["content_id"]),
                    external_comment_id=str(row["comment_id"]),
                    author_id=row["user_id"],
                    author_name=row["user_name"],
                    text=str(row["text"]),
                    like_count=int(row["like_count"]),
                    reply_count=int(row["reply_count"]),
                    answered=bool(row["answered"]),
                    attachment_type=row["attachment_type"],
                    attachment_media_type=row["attachment_media_type"],
                    attachment_url=row["attachment_url"],
                    commented_at=row["commented_at"],
                )
                for row in rows
            )


__all__ = ["LegacyCommentStore"]
