import { useState } from "react";

import { useBrandScope } from "../../app/BrandScopeProvider";
import {
  DashboardError,
  DashboardLoading,
} from "../dashboard/DashboardFrame";
import type { RangeKey } from "../dashboard/catalog";
import { useInsights, useOverviewDashboard } from "../dashboard/useDashboard";
import { AccumulateSocialOverview } from "./AccumulateSocialOverview";

export default function OverviewPage() {
  const [range, setRange] = useState<RangeKey>("last_30_days");
  const { selectedBrand } = useBrandScope();
  const query = useOverviewDashboard(range);
  const insights = useInsights();

  if (query.isPending) return <DashboardLoading title="Social Media Overview" />;
  if (query.isError || !query.data) return <DashboardError retry={() => void query.refetch()} />;
  const data = query.data;
  return (
    <AccumulateSocialOverview
      brandName={selectedBrand?.name ?? "Selected Brand"}
      data={data}
      insights={insights.data?.items ?? []}
      insightsError={insights.isError}
      insightsLoading={insights.isPending}
      onRange={setRange}
      range={range}
    />
  );
}
