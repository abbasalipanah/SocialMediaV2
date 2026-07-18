"""Read-only compatibility adapter for dashboard and operations queries."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import Engine, bindparam, text

from app.application.ports.reporting import (
    ReportingAccount,
    ReportingComment,
    ReportingConnection,
    ReportingContent,
    ReportingInsight,
    ReportingMedia,
    ReportingMetric,
    ReportingSyncJob,
)
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId

from .platforms import normalize_legacy_platform


def _expanded(statement: str, parameter: str):
    return text(statement).bindparams(bindparam(parameter, expanding=True))


class LegacyReportingStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def list_accounts(
        self,
        *,
        brand_ids: tuple[str, ...],
        platform: PlatformId | None = None,
    ) -> tuple[ReportingAccount, ...]:
        if not brand_ids:
            return ()
        platform_clause = "AND a.platform IN :platform_values" if platform else ""
        statement = _expanded(
            f"""SELECT a.id, CAST(a.brand_id AS text) AS brand_id, a.platform,
                       a.external_id, a.display_name, a.status,
                       COALESCE(pc.status, la.status, 'disconnected') AS connection_state,
                       COALESCE(la.health_status, 'unknown') AS health_status,
                       COALESCE(la.backfill_status, 'pending') AS backfill_status,
                       COALESCE(la.nightly_enabled, false) AS nightly_enabled,
                       COALESCE(la.last_synced_at, ss.last_synced_at) AS last_synced_at
                FROM assets AS a
                LEFT JOIN linked_social_accounts AS la ON la.asset_id=a.id
                LEFT JOIN platform_connections AS pc ON pc.id=la.connection_id
                LEFT JOIN asset_sync_state AS ss ON ss.asset_id=a.id
                WHERE CAST(a.brand_id AS text) IN :brand_ids
                  {platform_clause}
                ORDER BY a.platform, a.display_name, a.id""",
            "brand_ids",
        )
        if platform:
            statement = statement.bindparams(bindparam("platform_values", expanding=True))
        parameters: dict[str, object] = {"brand_ids": brand_ids}
        if platform:
            parameters["platform_values"] = _platform_values(platform)
        with self.engine.connect() as connection:
            rows = connection.execute(statement, parameters).mappings()
            return tuple(
                ReportingAccount(
                    account_id=int(row["id"]),
                    brand_id=str(row["brand_id"]),
                    platform=normalize_legacy_platform(row["platform"]),
                    external_id=str(row["external_id"]),
                    display_name=str(row["display_name"]),
                    status=str(row["status"]),
                    connection_state=str(row["connection_state"]),
                    health_status=str(row["health_status"]),
                    backfill_status=str(row["backfill_status"]),
                    nightly_enabled=bool(row["nightly_enabled"]),
                    last_synced_at=row["last_synced_at"],
                )
                for row in rows
            )

    def list_metrics(
        self,
        *,
        account_ids: tuple[int, ...],
        start_on: date,
        end_on: date,
    ) -> tuple[ReportingMetric, ...]:
        if not account_ids:
            return ()
        _validate_range(start_on, end_on)
        statement = _expanded(
            """SELECT m.asset_id, CAST(m.brand_id AS text) AS brand_id, a.platform,
                      m.date, m.metric_id, m.value_numeric,
                      m.breakdown_key, m.breakdown_value
               FROM metrics_daily AS m
               JOIN assets AS a ON a.id=m.asset_id
               WHERE m.asset_id IN :account_ids
                 AND m.date BETWEEN :start_on AND :end_on
               ORDER BY m.date, m.metric_id, m.breakdown_key, m.breakdown_value""",
            "account_ids",
        )
        with self.engine.connect() as connection:
            rows = connection.execute(
                statement,
                {"account_ids": account_ids, "start_on": start_on, "end_on": end_on},
            ).mappings()
            return tuple(
                ReportingMetric(
                    account_id=int(row["asset_id"]),
                    brand_id=str(row["brand_id"]),
                    platform=normalize_legacy_platform(row["platform"]),
                    observed_on=row["date"],
                    metric_id=MetricId(str(row["metric_id"])),
                    value=float(row["value_numeric"]),
                    breakdown_key=row["breakdown_key"],
                    breakdown_value=row["breakdown_value"],
                )
                for row in rows
            )

    def list_content(
        self,
        *,
        account_ids: tuple[int, ...],
        start_on: date,
        end_on: date,
        content_type: str | None = None,
    ) -> tuple[ReportingContent, ...]:
        if not account_ids:
            return ()
        _validate_range(start_on, end_on)
        type_clause = "AND i.content_type=:content_type" if content_type else ""
        statement = _expanded(
            f"""SELECT i.asset_id, CAST(i.brand_id AS text) AS brand_id, a.platform,
                       i.content_id, i.content_type, i.permalink, i.message, i.media_url,
                       i.created_time, i.likes_count, i.comments_count, i.shares_count
                FROM content_items AS i
                JOIN assets AS a ON a.id=i.asset_id
                WHERE i.asset_id IN :account_ids
                  AND i.created_time >= :start_at
                  AND i.created_time < (:end_on + 1)
                  {type_clause}
                ORDER BY i.created_time DESC NULLS LAST, i.content_id""",
            "account_ids",
        )
        parameters: dict[str, object] = {
            "account_ids": account_ids,
            "start_at": start_on,
            "end_on": end_on,
        }
        if content_type:
            parameters["content_type"] = content_type
        with self.engine.connect() as connection:
            rows = connection.execute(statement, parameters).mappings()
            return tuple(
                ReportingContent(
                    account_id=int(row["asset_id"]),
                    brand_id=str(row["brand_id"]),
                    platform=normalize_legacy_platform(row["platform"]),
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

    def list_comments(
        self,
        *,
        account_ids: tuple[int, ...],
        start_on: date,
        end_on: date,
    ) -> tuple[ReportingComment, ...]:
        if not account_ids:
            return ()
        _validate_range(start_on, end_on)
        statement = _expanded(
            """SELECT c.asset_id, c.platform, c.content_id, c.comment_id,
                      c.user_name, c.text, c.like_count, c.reply_count,
                      c.answered, c.commented_at
               FROM content_comments AS c
               WHERE c.asset_id IN :account_ids
                 AND c.commented_at >= :start_at
                 AND c.commented_at < (:end_on + 1)
               ORDER BY c.commented_at DESC NULLS LAST, c.comment_id""",
            "account_ids",
        )
        with self.engine.connect() as connection:
            rows = connection.execute(
                statement,
                {"account_ids": account_ids, "start_at": start_on, "end_on": end_on},
            ).mappings()
            return tuple(
                ReportingComment(
                    account_id=int(row["asset_id"]),
                    platform=normalize_legacy_platform(row["platform"]),
                    external_content_id=str(row["content_id"]),
                    external_comment_id=str(row["comment_id"]),
                    author_name=row["user_name"],
                    text=str(row["text"]),
                    like_count=int(row["like_count"]),
                    reply_count=int(row["reply_count"]),
                    answered=bool(row["answered"]),
                    commented_at=row["commented_at"],
                )
                for row in rows
            )

    def find_media(
        self,
        *,
        brand_ids: tuple[str, ...],
        platform: PlatformId,
        external_content_id: str,
        account_id: int | None = None,
    ) -> ReportingMedia | None:
        if not brand_ids or not external_content_id.strip():
            return None
        account_clause = "AND m.asset_id=:account_id" if account_id is not None else ""
        statement = _expanded(
            f"""SELECT m.asset_id, CAST(m.brand_id AS text) AS brand_id, m.platform,
                       m.content_id, m.media_kind, m.storage_path, m.mime_type,
                       m.size_bytes, m.checksum
                FROM media_assets AS m
                WHERE CAST(m.brand_id AS text) IN :brand_ids
                  AND m.platform IN :platform_values
                  AND m.content_id=:content_id
                  {account_clause}
                ORDER BY CASE WHEN m.media_kind='cover' THEN 0 ELSE 1 END, m.asset_id
                LIMIT 1""",
            "brand_ids",
        ).bindparams(bindparam("platform_values", expanding=True))
        parameters: dict[str, object] = {
            "brand_ids": brand_ids,
            "platform_values": _platform_values(platform),
            "content_id": external_content_id,
        }
        if account_id is not None:
            parameters["account_id"] = account_id
        with self.engine.connect() as connection:
            row = connection.execute(statement, parameters).mappings().one_or_none()
        if row is None:
            return None
        return ReportingMedia(
            account_id=int(row["asset_id"]),
            brand_id=str(row["brand_id"]),
            platform=normalize_legacy_platform(row["platform"]),
            external_content_id=str(row["content_id"]),
            media_kind=str(row["media_kind"]),
            storage_path=Path(str(row["storage_path"])),
            mime_type=str(row["mime_type"]),
            size_bytes=int(row["size_bytes"]),
            checksum=str(row["checksum"]),
        )

    def list_connections(
        self, *, brand_ids: tuple[str, ...]
    ) -> tuple[ReportingConnection, ...]:
        if not brand_ids:
            return ()
        statement = _expanded(
            """SELECT id, CAST(brand_id AS text) AS brand_id, platform, status,
                      expires_at, projected_at
               FROM platform_connections
               WHERE CAST(brand_id AS text) IN :brand_ids
               ORDER BY brand_id, platform, id""",
            "brand_ids",
        )
        with self.engine.connect() as connection:
            rows = connection.execute(statement, {"brand_ids": brand_ids}).mappings()
            return tuple(
                ReportingConnection(
                    connection_id=int(row["id"]),
                    brand_id=str(row["brand_id"]),
                    platform=normalize_legacy_platform(row["platform"]),
                    state=str(row["status"]),
                    expires_at=row["expires_at"],
                    projected_at=row["projected_at"],
                )
                for row in rows
            )

    def list_sync_jobs(
        self, *, brand_ids: tuple[str, ...]
    ) -> tuple[ReportingSyncJob, ...]:
        if not brand_ids:
            return ()
        statement = _expanded(
            """SELECT id, CAST(brand_id AS text) AS brand_id, asset_id, platform,
                      stage, status, scheduled_for, started_at, finished_at, error_code
               FROM social_backfill_jobs
               WHERE CAST(brand_id AS text) IN :brand_ids
               ORDER BY scheduled_for DESC, id DESC""",
            "brand_ids",
        )
        with self.engine.connect() as connection:
            rows = connection.execute(statement, {"brand_ids": brand_ids}).mappings()
            return tuple(
                ReportingSyncJob(
                    job_id=int(row["id"]),
                    brand_id=str(row["brand_id"]),
                    account_id=int(row["asset_id"]) if row["asset_id"] is not None else None,
                    platform=normalize_legacy_platform(row["platform"]),
                    stage=str(row["stage"]),
                    status=str(row["status"]),
                    scheduled_for=row["scheduled_for"],
                    started_at=row["started_at"],
                    finished_at=row["finished_at"],
                    error_code=row["error_code"],
                )
                for row in rows
            )

    def list_insights(
        self,
        *,
        brand_ids: tuple[str, ...],
        start_on: date | None = None,
        end_on: date | None = None,
    ) -> tuple[ReportingInsight, ...]:
        if not brand_ids:
            return ()
        range_clause = ""
        if start_on is not None or end_on is not None:
            if start_on is None or end_on is None:
                raise ValueError("insight_range_incomplete")
            _validate_range(start_on, end_on)
            range_clause = "AND date_from <= :end_on AND date_to >= :start_on"
        statement = _expanded(
            f"""SELECT id, CAST(brand_id AS text) AS brand_id, status,
                       date_from, date_to, strategic_summary, action_recommendations,
                       created_at, completed_at
                FROM brand_ai_insights
                WHERE CAST(brand_id AS text) IN :brand_ids
                  {range_clause}
                ORDER BY created_at DESC, id DESC""",
            "brand_ids",
        )
        parameters: dict[str, object] = {"brand_ids": brand_ids}
        if start_on is not None and end_on is not None:
            parameters.update({"start_on": start_on, "end_on": end_on})
        with self.engine.connect() as connection:
            rows = connection.execute(statement, parameters).mappings()
            return tuple(
                ReportingInsight(
                    insight_id=int(row["id"]),
                    brand_id=str(row["brand_id"]),
                    status=str(row["status"]),
                    date_from=row["date_from"],
                    date_to=row["date_to"],
                    summary=row["strategic_summary"],
                    recommendations=row["action_recommendations"],
                    created_at=row["created_at"],
                    completed_at=row["completed_at"],
                )
                for row in rows
            )


def _validate_range(start_on: date, end_on: date) -> None:
    if end_on < start_on or (end_on - start_on).days > 365:
        raise ValueError("reporting_range_invalid")


def _platform_values(platform: PlatformId) -> tuple[str, ...]:
    return (platform.value, f"{platform.value}_organic")


__all__ = ["LegacyReportingStore"]
