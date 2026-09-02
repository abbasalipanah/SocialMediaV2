import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiQuery,
  apiMutation,
  aiSummaryLimitSchema,
  insightsSchema,
  insightSchema,
  overviewDashboardSchema,
  platformDashboardSchema,
  queryString,
  type Platform,
} from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";
import { usePlatformAccounts } from "../../app/usePlatformAccounts";
import {
  reportingPeriodQuery,
  type DashboardTab,
  type ReportingPeriod,
} from "./catalog";

export function useOverviewDashboard(period: ReportingPeriod) {
  const { selectedBrandId, rollup } = useBrandScope();
  return useQuery({
    queryKey: ["dashboard", "overview", selectedBrandId, rollup, period.key, period.startDate, period.endDate],
    queryFn: ({ signal }) =>
      apiQuery(
        `/api/dashboards/overview${queryString({
          brand_id: selectedBrandId,
          rollup,
          ...reportingPeriodQuery(period),
        })}`,
        overviewDashboardSchema,
        signal,
      ),
    refetchInterval: () => document.visibilityState === "visible" ? 60_000 : false,
  });
}

export function useChannelDashboard(
  platform: Platform,
  period: ReportingPeriod,
  tab: DashboardTab["id"],
) {
  const { selectedBrandId, rollup } = useBrandScope();
  const accountState = usePlatformAccounts(platform);
  const accountId = accountState.selectedAccountId === "all" ? undefined : accountState.selectedAccountId;
  return useQuery({
    enabled: !accountState.isLoading,
    queryKey: ["dashboard", platform, selectedBrandId, rollup, accountId ?? "all", period.key, period.startDate, period.endDate, tab],
    queryFn: ({ signal }) =>
      apiQuery(
        `/api/dashboards/${platform}${queryString({
          brand_id: selectedBrandId,
          rollup,
          ...reportingPeriodQuery(period),
          account_id: accountId,
          tab,
        })}`,
        platformDashboardSchema,
        signal,
      ),
    refetchInterval: () => document.visibilityState === "visible" ? 60_000 : false,
  });
}

export function useInsights() {
  const { selectedBrandId, rollup } = useBrandScope();
  return useQuery({
    queryKey: ["insights", selectedBrandId, rollup],
    queryFn: ({ signal }) =>
      apiQuery(
        `/api/insights${queryString({
          brand_id: selectedBrandId,
          rollup,
        })}`,
        insightsSchema,
        signal,
      ),
  });
}

export function useAiSummaryLimit(enabled: boolean) {
  const { selectedBrandId, rollup } = useBrandScope();
  return useQuery({
    enabled: enabled && !rollup,
    queryKey: ["insights", "limit", selectedBrandId],
    queryFn: ({ signal }) =>
      apiQuery(
        `/api/insights/limit${queryString({ brand_id: selectedBrandId, rollup })}`,
        aiSummaryLimitSchema,
        signal,
      ),
  });
}

export function useGenerateAiSummary() {
  const { selectedBrandId, rollup } = useBrandScope();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (period: ReportingPeriod) =>
      apiMutation(
        `/api/insights/generate${queryString({
          brand_id: selectedBrandId,
          rollup,
          ...reportingPeriodQuery(period),
        })}`,
        insightSchema,
        { method: "POST" },
      ),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["insights", selectedBrandId, rollup] }),
        queryClient.invalidateQueries({ queryKey: ["insights", "limit", selectedBrandId] }),
      ]);
    },
  });
}
