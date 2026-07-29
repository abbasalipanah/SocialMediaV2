"""V2 media metadata persistence."""

from __future__ import annotations

from sqlalchemy import Engine, text

from app.application.ports.persistence import MediaRecord
from app.core.write_policy import WritePolicy

from .base import SocialStoreBase
from .platforms import normalize_platform


class SocialMediaStore(SocialStoreBase):
    def __init__(self, engine: Engine, write_policy: WritePolicy) -> None:
        super().__init__(engine, write_policy)

    def upsert(self, record: MediaRecord) -> None:
        self._assert_mutation("media.upsert")
        with self.engine.begin() as connection:
            self._assert_account_scope(
                connection,
                account_id=record.account_id,
                platform=record.platform,
                brand_id=record.brand_id,
            )
            connection.execute(
                text(
                    """INSERT INTO media_assets (
                        brand_id, asset_id, content_id, platform, media_kind,
                        storage_path, source_url, source_status, mime_type,
                        size_bytes, checksum, last_verified_at, created_at, updated_at
                    ) VALUES (
                        :brand_id, :account_id, :content_id, :platform, :media_kind,
                        :storage_path, :source_url, :source_status, :mime_type,
                        :size_bytes, :checksum, :verified_at, now(), now()
                    )
                    ON CONFLICT (asset_id, content_id, media_kind) DO UPDATE SET
                        brand_id=EXCLUDED.brand_id,
                        platform=EXCLUDED.platform,
                        storage_path=EXCLUDED.storage_path,
                        source_url=EXCLUDED.source_url,
                        source_status=EXCLUDED.source_status,
                        mime_type=EXCLUDED.mime_type,
                        size_bytes=EXCLUDED.size_bytes,
                        checksum=EXCLUDED.checksum,
                        last_verified_at=EXCLUDED.last_verified_at,
                        updated_at=now()"""
                ),
                {
                    "brand_id": record.brand_id,
                    "account_id": record.account_id,
                    "content_id": record.external_content_id,
                    "platform": record.platform.value,
                    "media_kind": record.media_kind,
                    "storage_path": record.storage_path,
                    "source_url": record.source_url,
                    "source_status": record.source_status,
                    "mime_type": record.mime_type,
                    "size_bytes": record.size_bytes,
                    "checksum": record.checksum,
                    "verified_at": record.verified_at,
                },
            )

    def get(
        self, account_id: int, external_content_id: str, media_kind: str
    ) -> MediaRecord | None:
        if account_id < 1 or not external_content_id or not media_kind:
            raise ValueError("media_query_invalid")
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """SELECT brand_id, asset_id, content_id, platform, media_kind,
                                  storage_path, source_url, source_status, mime_type,
                                  size_bytes, checksum, last_verified_at
                           FROM media_assets
                           WHERE asset_id=:account_id
                             AND content_id=:content_id
                             AND media_kind=:media_kind"""
                    ),
                    {
                        "account_id": account_id,
                        "content_id": external_content_id,
                        "media_kind": media_kind,
                    },
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        return MediaRecord(
            platform=normalize_platform(row["platform"]),
            account_id=int(row["asset_id"]),
            brand_id=int(row["brand_id"]),
            external_content_id=str(row["content_id"]),
            media_kind=str(row["media_kind"]),
            storage_path=str(row["storage_path"]),
            source_url=str(row["source_url"]),
            source_status=row["source_status"],
            mime_type=str(row["mime_type"]),
            size_bytes=int(row["size_bytes"]),
            checksum=str(row["checksum"]),
            verified_at=row["last_verified_at"],
        )


__all__ = ["SocialMediaStore"]
