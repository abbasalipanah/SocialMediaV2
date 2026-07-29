"""V2 metric persistence."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Engine, bindparam, text

from app.application.ports.persistence import MetricPoint
from app.application.queries.metrics import MetricQuery
from app.core.write_policy import WritePolicy
from app.domain.metrics import MetricCatalog, MetricId

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


__all__ = ["SocialMetricStore"]
