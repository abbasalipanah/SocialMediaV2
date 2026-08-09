"""Brand-scoped AI Summary orchestration with a rolling weekly allowance."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.application.ports import (
    AiSummaryError,
    AiSummaryLimitStatus,
    AiSummaryProvider,
    AiSummaryRepository,
    ReportingStore,
)
from app.application.ports.reporting import ReportingInsight
from app.application.queries import (
    DashboardQuery,
    build_overview_dashboard,
    resolve_reporting_range,
)
from app.domain.metrics import MetricCatalog, MetricId
from app.domain.reporting import OverviewDashboard


class AiSummaryCoordinator:
    def __init__(
        self,
        *,
        repository: AiSummaryRepository,
        reporting_store: ReportingStore,
        metric_catalog: MetricCatalog,
        provider: AiSummaryProvider | None,
    ) -> None:
        self._repository = repository
        self._reporting_store = reporting_store
        self._metric_catalog = metric_catalog
        self._provider = provider

    @property
    def provider_configured(self) -> bool:
        return self._provider is not None

    def limit_status(self, *, brand_id: str) -> AiSummaryLimitStatus:
        return self._repository.limit_status(
            brand_id=brand_id,
            now=datetime.now(UTC),
            provider_configured=self.provider_configured,
        )

    async def generate(
        self,
        *,
        brand_id: str,
        user_sub: str,
        range_key: str,
        start_on: date | None = None,
        end_on: date | None = None,
    ) -> ReportingInsight:
        if self._provider is None:
            raise AiSummaryError("provider_not_configured")
        try:
            reporting_range = resolve_reporting_range(
                range_key=range_key,
                start_on=start_on,
                end_on=end_on,
            )
        except ValueError as exc:
            raise AiSummaryError(str(exc)) from exc
        dashboard = build_overview_dashboard(
            store=self._reporting_store,
            catalog=self._metric_catalog,
            query=DashboardQuery(
                requested_brand_id=brand_id,
                resolved_brand_ids=(brand_id,),
                rollup=False,
                date_range=reporting_range,
            ),
        )
        if not dashboard.meta.resolved_account_ids:
            raise AiSummaryError("ai_summary_data_unavailable")
        now = datetime.now(UTC)
        insight_id = self._repository.claim(
            brand_id=brand_id,
            date_from=reporting_range.start_on,
            date_to=reporting_range.end_on,
            created_by_user_sub=user_sub,
            now=now,
        )
        try:
            output = await self._provider.generate(_summary_snapshot(dashboard))
            return self._repository.complete(
                insight_id=insight_id,
                output=output,
                completed_at=datetime.now(UTC),
            )
        except AiSummaryError as exc:
            self._repository.fail(
                insight_id=insight_id,
                error_code=exc.code,
                failed_at=datetime.now(UTC),
            )
            raise
        except Exception as exc:
            self._repository.fail(
                insight_id=insight_id,
                error_code="ai_summary_generation_failed",
                failed_at=datetime.now(UTC),
            )
            raise AiSummaryError("ai_summary_generation_failed") from exc


def _summary_snapshot(dashboard: OverviewDashboard) -> dict[str, object]:
    account_platform = {
        account_id: platform.meta.platform.value
        for platform in dashboard.platforms
        if platform.meta.platform is not None
        for account_id in platform.meta.resolved_account_ids
    }

    def metric_rows(metrics) -> list[dict[str, object]]:
        return [
            {
                "metric": item.metric_id.value,
                "value": item.value,
                "previous_value": item.previous_value,
                "change_percent": item.delta_pct,
                "availability": item.data_status.value,
            }
            for item in metrics
        ]

    platforms = [
        {
            "platform": item.meta.platform.value if item.meta.platform else "unknown",
            "data_status": item.meta.data_status.value,
            "metrics": metric_rows(item.metrics),
        }
        for item in dashboard.platforms
    ]
    ranked_content = sorted(
        dashboard.content,
        key=lambda item: item.interactions,
        reverse=True,
    )[:5]
    return {
        "reporting_period": {
            "start": dashboard.meta.date_range.start_on.isoformat(),
            "end": dashboard.meta.date_range.end_on.isoformat(),
            "data_status": dashboard.meta.data_status.value,
        },
        "aggregate_metrics": metric_rows(dashboard.metrics),
        "platforms": platforms,
        "top_content": [
            {
                "platform": account_platform.get(item.account_id, "unknown"),
                "content_type": item.content_type,
                "published_on": item.published_at.date().isoformat()
                if item.published_at
                else None,
                MetricId.INTERACTIONS.value: item.interactions,
                MetricId.REACH.value: item.reach,
                MetricId.VIEWS.value: item.views,
            }
            for item in ranked_content
        ],
        "privacy_note": (
            "Only aggregate metrics and de-identified content statistics are supplied. "
            "Unavailable values are null."
        ),
    }


__all__ = ["AiSummaryCoordinator"]
