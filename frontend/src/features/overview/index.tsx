import { useState } from "react";

import { useBrandScope } from "../../app/BrandScopeProvider";
import { useAuth } from "../../auth";
import {
  DashboardError,
  DashboardLoading,
} from "../dashboard/DashboardFrame";
import type { RangeKey } from "../dashboard/catalog";
import {
  useAiSummaryLimit,
  useGenerateAiSummary,
  useInsights,
  useOverviewDashboard,
} from "../dashboard/useDashboard";
import { AccumulateSocialOverview } from "./AccumulateSocialOverview";

export default function OverviewPage() {
  const [range, setRange] = useState<RangeKey>("last_30_days");
  const { user } = useAuth();
  const { selectedBrand, selectedBrandId, rollup } = useBrandScope();
  const query = useOverviewDashboard(range);
  const insights = useInsights();
  const canGenerateAiSummary = Boolean(
    user
    && ["admin", "operator"].includes(user.app_role ?? "")
    && user.source_system === "accumulate"
    && selectedBrand?.role
    && ["read", "write"].includes(selectedBrand.access_mode ?? "")
    && !rollup,
  );
  const aiSummaryLimit = useAiSummaryLimit(canGenerateAiSummary);
  const generateAiSummary = useGenerateAiSummary();

  if (query.isPending) return <DashboardLoading title="Social Media Overview" />;
  if (query.isError || !query.data) return <DashboardError retry={() => void query.refetch()} />;
  const data = query.data;
  return (
    <AccumulateSocialOverview
      aiSummaryGenerating={generateAiSummary.isPending}
      aiSummaryGenerationError={generateAiSummary.error instanceof Error ? generateAiSummary.error : null}
      aiSummaryLimit={aiSummaryLimit.data}
      aiSummaryLimitLoading={aiSummaryLimit.isPending && canGenerateAiSummary}
      brandName={selectedBrand?.name ?? "Selected Brand"}
      canGenerateAiSummary={canGenerateAiSummary}
      data={data}
      insights={insights.data?.items ?? []}
      insightsError={insights.isError}
      insightsLoading={insights.isPending}
      onGenerateAiSummary={() => generateAiSummary.mutateAsync(range)}
      onRange={setRange}
      range={range}
    />
  );
}
