"""Catalog-validated metric query contract."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.metrics import MetricCatalog, MetricCatalogError, MetricId
from app.domain.platforms import PlatformId


@dataclass(frozen=True, init=False)
class MetricQuery:
    platform: PlatformId
    metric_ids: tuple[MetricId, ...]

    def __init__(
        self,
        *,
        catalog: MetricCatalog,
        platform: PlatformId,
        metric_ids: tuple[MetricId, ...],
    ) -> None:
        if not metric_ids:
            raise MetricCatalogError("metric_query_empty")
        if len(set(metric_ids)) != len(metric_ids):
            raise MetricCatalogError("metric_query_duplicate")
        for metric_id in metric_ids:
            if not isinstance(metric_id, MetricId):
                raise MetricCatalogError("metric_id_must_be_canonical")
            catalog.get(platform, metric_id)
        object.__setattr__(self, "platform", platform)
        object.__setattr__(self, "metric_ids", metric_ids)


__all__ = ["MetricQuery"]
