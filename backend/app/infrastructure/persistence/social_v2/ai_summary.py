"""PostgreSQL repository for Brand-scoped weekly AI Summary generation."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import Engine, text

from app.application.ports.ai_summary import (
    AiSummaryError,
    AiSummaryLimitStatus,
    AiSummaryOutput,
)
from app.application.ports.reporting import ReportingInsight

WINDOW = timedelta(days=7)
PENDING_TTL = timedelta(minutes=15)


class SocialAiSummaryRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def limit_status(self, *, brand_id, now, provider_configured):
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """SELECT
                         max(completed_at) FILTER (WHERE status='completed') AS last_completed,
                         bool_or(status='pending' AND created_at >= :pending_cutoff) AS pending
                       FROM brand_ai_insights
                       WHERE CAST(brand_id AS text)=:brand_id"""
                ),
                {"brand_id": brand_id, "pending_cutoff": now - PENDING_TTL},
            ).mappings().one()
        last_completed = row["last_completed"]
        in_progress = bool(row["pending"])
        within_window = bool(last_completed and last_completed > now - WINDOW)
        if not provider_configured:
            reason = "provider_not_configured"
        elif in_progress:
            reason = "generation_in_progress"
        elif within_window:
            reason = "weekly_limit_reached"
        else:
            reason = "available"
        return AiSummaryLimitStatus(
            provider_configured=provider_configured,
            can_generate=reason == "available",
            reason=reason,
            weekly_limit=1,
            used=1 if within_window else 0,
            remaining=0 if within_window else 1,
            window_days=7,
            last_generated_at=last_completed,
            next_available_at=last_completed + WINDOW if within_window else None,
            generation_in_progress=in_progress,
        )

    def claim(
        self,
        *,
        brand_id,
        date_from,
        date_to,
        created_by_user_sub,
        now,
    ) -> int:
        with self.engine.begin() as connection:
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": f"ai-summary:{brand_id}"},
            )
            last_completed = connection.execute(
                text(
                    """SELECT completed_at
                       FROM brand_ai_insights
                       WHERE CAST(brand_id AS text)=:brand_id
                         AND status='completed' AND completed_at IS NOT NULL
                       ORDER BY completed_at DESC, id DESC LIMIT 1"""
                ),
                {"brand_id": brand_id},
            ).scalar_one_or_none()
            if last_completed and last_completed > now - WINDOW:
                raise AiSummaryError(
                    "weekly_limit_reached",
                    next_available_at=last_completed + WINDOW,
                )
            pending = connection.execute(
                text(
                    """SELECT id FROM brand_ai_insights
                       WHERE CAST(brand_id AS text)=:brand_id
                         AND status='pending' AND created_at >= :pending_cutoff
                       ORDER BY created_at DESC, id DESC LIMIT 1"""
                ),
                {"brand_id": brand_id, "pending_cutoff": now - PENDING_TTL},
            ).scalar_one_or_none()
            if pending is not None:
                raise AiSummaryError("generation_in_progress")
            connection.execute(
                text(
                    """UPDATE brand_ai_insights
                       SET status='failed', error_message='generation_timeout'
                       WHERE CAST(brand_id AS text)=:brand_id
                         AND status='pending' AND created_at < :pending_cutoff"""
                ),
                {"brand_id": brand_id, "pending_cutoff": now - PENDING_TTL},
            )
            return int(
                connection.execute(
                    text(
                        """INSERT INTO brand_ai_insights
                                  (brand_id, status, date_from, date_to,
                                   created_by_user_sub, created_at)
                           VALUES (CAST(:brand_id AS bigint), 'pending', :date_from,
                                   :date_to, :created_by_user_sub, :created_at)
                           RETURNING id"""
                    ),
                    {
                        "brand_id": brand_id,
                        "date_from": date_from,
                        "date_to": date_to,
                        "created_by_user_sub": created_by_user_sub,
                        "created_at": now,
                    },
                ).scalar_one()
            )

    def complete(self, *, insight_id, output, completed_at):
        assert isinstance(output, AiSummaryOutput)
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """UPDATE brand_ai_insights
                       SET status='completed', strategic_summary=:strategic_summary,
                           connector_analysis=:connector_analysis, anomalies=:anomalies,
                           action_recommendations=:action_recommendations,
                           platform_evaluations=:platform_evaluations,
                           llm_model=:llm_model, error_message=NULL,
                           completed_at=:completed_at
                       WHERE id=:insight_id AND status='pending'
                       RETURNING id, CAST(brand_id AS text) AS brand_id, status,
                                 date_from, date_to, strategic_summary,
                                 action_recommendations, connector_analysis, anomalies,
                                 platform_evaluations, llm_model, error_message,
                                 created_by_user_sub, created_at, completed_at"""
                ),
                {
                    "insight_id": insight_id,
                    "strategic_summary": output.strategic_summary,
                    "connector_analysis": output.connector_analysis,
                    "anomalies": output.anomalies,
                    "action_recommendations": output.action_recommendations,
                    "platform_evaluations": output.platform_evaluations,
                    "llm_model": output.model,
                    "completed_at": completed_at,
                },
            ).mappings().one_or_none()
        if row is None:
            raise AiSummaryError("generation_state_conflict")
        return _reporting_insight(row)

    def fail(self, *, insight_id, error_code, failed_at):
        del failed_at
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """UPDATE brand_ai_insights
                       SET status='failed', error_message=:error_code
                       WHERE id=:insight_id AND status='pending'"""
                ),
                {"insight_id": insight_id, "error_code": error_code[:128]},
            )


def _reporting_insight(row) -> ReportingInsight:
    return ReportingInsight(
        insight_id=int(row["id"]),
        brand_id=str(row["brand_id"]),
        status=str(row["status"]),
        date_from=row["date_from"],
        date_to=row["date_to"],
        summary=row["strategic_summary"],
        recommendations=row["action_recommendations"],
        connector_analysis=row["connector_analysis"],
        anomalies=row["anomalies"],
        platform_evaluations=row["platform_evaluations"],
        model=row["llm_model"],
        error_message=row["error_message"],
        created_by_user_sub=row["created_by_user_sub"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


__all__ = ["SocialAiSummaryRepository"]
