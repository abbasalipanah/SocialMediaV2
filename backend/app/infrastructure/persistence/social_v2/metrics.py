"""V2 metric persistence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta

from sqlalchemy import Engine, bindparam, text

from app.application.ports.persistence import MetricPoint
from app.application.queries.metrics import MetricQuery
from app.core.write_policy import WritePolicy
from app.domain.metrics import MetricCatalog, MetricCatalogError, MetricId
from app.domain.platforms import PlatformId

from .base import SocialStoreBase


class SocialMetricStore(SocialStoreBase):
    def __init__(
        self,
        engine: Engine,
        write_policy: WritePolicy,
        metric_catalog: MetricCatalog,
    ) -> None:
        super().__init__(engine, write_policy)
        self._metric_catalog = metric_catalog

    def upsert(self, point: MetricPoint) -> None:
        self._assert_mutation("metric.upsert")
        definition = self._metric_catalog.get(point.platform, point.metric_id)
        self._metric_catalog.validate_values(
            platform=point.platform,
            capability=definition.required_capability,
            values={point.metric_id: point.value},
        )
        self._assert_breakdown(definition.allowed_breakdowns, point.breakdown_key)
        if point.breakdown_key is None:
            conflict = """ON CONFLICT (asset_id, date, metric_id)
                WHERE breakdown_key IS NULL AND breakdown_value IS NULL"""
        else:
            conflict = """ON CONFLICT (
                    asset_id, date, metric_id, breakdown_key, breakdown_value
                ) WHERE breakdown_key IS NOT NULL AND breakdown_value IS NOT NULL"""
        with self.engine.begin() as connection:
            self._assert_account_scope(
                connection,
                account_id=point.account_id,
                platform=point.platform,
                brand_id=point.brand_id,
            )
            connection.execute(
                text(
                    f"""INSERT INTO metrics_daily (
                        asset_id, brand_id, date, metric_id, value_numeric,
                        breakdown_key, breakdown_value
                    ) VALUES (
                        :account_id, :brand_id, :observed_on, :metric_id, :value,
                        :breakdown_key, :breakdown_value
                    )
                    {conflict}
                    DO UPDATE SET
                        brand_id=EXCLUDED.brand_id,
                        value_numeric=EXCLUDED.value_numeric"""
                ),
                {
                    "account_id": point.account_id,
                    "brand_id": point.brand_id,
                    "observed_on": point.observed_on,
                    "metric_id": point.metric_id.value,
                    "value": float(point.value),
                    "breakdown_key": point.breakdown_key,
                    "breakdown_value": point.breakdown_value,
                },
            )

    def replace_breakdown(
        self,
        *,
        platform: PlatformId,
        account_id: int,
        brand_id: int,
        observed_on: date,
        metric_id: MetricId,
        breakdown_key: str,
        values: Mapping[str, float | int],
    ) -> None:
        self._assert_mutation("metric.replace_breakdown")
        definition = self._metric_catalog.get(platform, metric_id)
        self._assert_breakdown(definition.allowed_breakdowns, breakdown_key)
        normalized: dict[str, float] = {}
        for breakdown_value, value in values.items():
            self._metric_catalog.validate_values(
                platform=platform,
                capability=definition.required_capability,
                values={metric_id: value},
            )
            if not breakdown_value.strip() or len(breakdown_value.encode("utf-8")) > 128:
                raise MetricCatalogError("metric_breakdown_value_invalid")
            normalized[breakdown_value] = float(value)
        with self.engine.begin() as connection:
            self._assert_account_scope(
                connection,
                account_id=account_id,
                platform=platform,
                brand_id=brand_id,
            )
            connection.execute(
                text(
                    """DELETE FROM metrics_daily
                       WHERE asset_id=:account_id AND date=:observed_on
                         AND metric_id=:metric_id AND breakdown_key=:breakdown_key"""
                ),
                {
                    "account_id": account_id,
                    "observed_on": observed_on,
                    "metric_id": metric_id.value,
                    "breakdown_key": breakdown_key,
                },
            )
            for breakdown_value, value in normalized.items():
                connection.execute(
                    text(
                        """INSERT INTO metrics_daily (
                            asset_id, brand_id, date, metric_id, value_numeric,
                            breakdown_key, breakdown_value
                        ) VALUES (
                            :account_id, :brand_id, :observed_on, :metric_id, :value,
                            :breakdown_key, :breakdown_value
                        )"""
                    ),
                    {
                        "account_id": account_id,
                        "brand_id": brand_id,
                        "observed_on": observed_on,
                        "metric_id": metric_id.value,
                        "value": value,
                        "breakdown_key": breakdown_key,
                        "breakdown_value": breakdown_value,
                    },
                )

    @staticmethod
    def _assert_breakdown(allowed_breakdowns: tuple[str, ...], breakdown_key: str | None) -> None:
        if breakdown_key is not None and breakdown_key not in allowed_breakdowns:
            raise MetricCatalogError("metric_breakdown_not_allowed")

    def read(
        self,
        *,
        account_id: int,
        start_on: date,
        end_on: date,
        query: MetricQuery,
    ) -> tuple[MetricPoint, ...]:
        if account_id < 1 or end_on < start_on:
            raise ValueError("metric_query_range_invalid")
        statement = text(
            """SELECT asset_id, brand_id, date, metric_id, value_numeric,
                      breakdown_key, breakdown_value
               FROM metrics_daily
               WHERE asset_id=:account_id
                 AND date BETWEEN :start_on AND :end_on
                 AND metric_id IN :metric_ids
               ORDER BY date, metric_id, breakdown_key, breakdown_value"""
        ).bindparams(bindparam("metric_ids", expanding=True))
        with self.engine.connect() as connection:
            self._assert_account_scope(
                connection,
                account_id=account_id,
                platform=query.platform,
            )
            rows = connection.execute(
                statement,
                {
                    "account_id": account_id,
                    "start_on": start_on,
                    "end_on": end_on,
                    "metric_ids": tuple(metric_id.value for metric_id in query.metric_ids),
                },
            ).mappings()
            return tuple(
                MetricPoint(
                    platform=query.platform,
                    account_id=int(row["asset_id"]),
                    brand_id=int(row["brand_id"]),
                    observed_on=row["date"],
                    metric_id=MetricId(str(row["metric_id"])),
                    value=float(row["value_numeric"]),
                    breakdown_key=row["breakdown_key"],
                    breakdown_value=row["breakdown_value"],
                )
                for row in rows
            )

    def earliest_daily_gap(
        self,
        *,
        platform: PlatformId,
        account_id: int,
        metric_ids: tuple[MetricId, ...],
        start_on: date,
        end_on: date,
    ) -> date | None:
        """Return the earliest interior/tail gap among observed daily metrics.

        This is a bootstrap hint for accounts imported before daily collection
        watermarks existed. Unsupported metrics have no rows and are ignored.
        Each observed metric is expected only from its own first stored day, so
        a metric introduced later does not create synthetic historical gaps.
        Returning ``end_on`` when no gap exists gives the first watermarked run
        the same one-day overlap as subsequent routine refreshes.
        """
        if account_id < 1 or not metric_ids or end_on < start_on:
            raise ValueError("metric_watermark_scope_invalid")
        statement = text(
            """SELECT metric_id, date
               FROM metrics_daily
               WHERE asset_id=:account_id
                 AND date BETWEEN :start_on AND :end_on
                 AND breakdown_key IS NULL
                 AND breakdown_value IS NULL
                 AND metric_id IN :metric_ids
               ORDER BY metric_id, date"""
        ).bindparams(bindparam("metric_ids", expanding=True))
        with self.engine.connect() as connection:
            self._assert_account_scope(
                connection,
                account_id=account_id,
                platform=platform,
            )
            rows = connection.execute(
                statement,
                {
                    "account_id": account_id,
                    "start_on": start_on,
                    "end_on": end_on,
                    "metric_ids": tuple(metric_id.value for metric_id in metric_ids),
                },
            ).all()
        dates_by_metric: dict[str, set[date]] = {}
        for metric_id, observed_on in rows:
            dates_by_metric.setdefault(str(metric_id), set()).add(observed_on)
        if not dates_by_metric:
            return None
        gaps: list[date] = []
        for dates in dates_by_metric.values():
            cursor = min(dates)
            while cursor <= end_on:
                if cursor not in dates:
                    gaps.append(cursor)
                    break
                cursor += timedelta(days=1)
        return min(gaps) if gaps else end_on


__all__ = ["SocialMetricStore"]
