import { useState } from "react";

import { useBrandScope } from "../../app/BrandScopeProvider";
import {
  CommunitySection,
  ContentSection,
  HealthSection,
  MetricBand,
  TrendSection,
} from "../dashboard/DashboardCards";
import {
  CoverageNotice,
  DashboardError,
  DashboardHeader,
  DashboardLoading,
} from "../dashboard/DashboardFrame";
import { InsightsSection } from "../dashboard/InsightsSection";
import type { RangeKey } from "../dashboard/catalog";
import { useInsights, useOverviewDashboard } from "../dashboard/useDashboard";

export default function OverviewPage() {
  const [range, setRange] = useState<RangeKey>("last_30_days");
  const { selectedBrand } = useBrandScope();
  const query = useOverviewDashboard(range);
  const insights = useInsights(query.data?.meta.date_range.start_on, query.data?.meta.date_range.end_on);

  if (query.isPending) return <DashboardLoading title="Overview" />;
  if (query.isError || !query.data) return <DashboardError retry={() => void query.refetch()} />;
  const data = query.data;
  return (
    <main className="page-shell dashboard-page">
      <DashboardHeader
        description="Cross-channel performance for the selected Brand scope."
        exportSubtitle={`${selectedBrand?.name ?? "Selected Brand"} · ${data.meta.date_range.start_on} to ${data.meta.date_range.end_on}`}
        freshness={data.meta.freshness}
        lastSync={data.meta.last_sync_at}
        metrics={data.metrics}
        onRange={setRange}
        range={range}
        status={data.meta.data_status}
        title="Overview"
      />
      <CoverageNotice status={data.meta.data_status} warnings={data.meta.warnings} />
      <MetricBand data={data} scope="overview" />
      <TrendSection data={data} />
      <HealthSection data={data} />
      <ContentSection content={data.content} />
      <CommunitySection data={data} />
      <InsightsSection error={insights.isError} insights={insights.data?.items ?? []} loading={insights.isPending} />
    </main>
  );
}
