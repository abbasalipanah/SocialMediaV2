import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
import type { DashboardTab, RangeKey } from "./catalog";

export function useOverviewDashboard(range: RangeKey) {
  const { selectedBrandId, rollup } = useBrandScope();
  return useQuery({
    queryKey: ["dashboard", "overview", selectedBrandId, rollup, range],
    queryFn: ({ signal }) =>
      apiQuery(
        `/api/dashboards/overview${queryString({
          brand_id: selectedBrandId,
          rollup,
          range,
        })}`,
        overviewDashboardSchema,
        signal,
      ),
    placeholderData: keepPreviousData,
    refetchInterval: () => document.visibilityState === "visible" ? 60_000 : false,
  });
}

export function useChannelDashboard(
  platform: Platform,
  range: RangeKey,
  tab: DashboardTab["id"],
) {
  const { selectedBrandId, rollup } = useBrandScope();
  const accountState = usePlatformAccounts(platform);
  const accountId = accountState.selectedAccountId === "all" ? undefined : accountState.selectedAccountId;
  return useQuery({
    enabled: !accountState.isLoading,
    queryKey: ["dashboard", platform, selectedBrandId, rollup, accountId ?? "all", range, tab],
    queryFn: ({ signal }) =>
      apiQuery(
        `/api/dashboards/${platform}${queryString({
          brand_id: selectedBrandId,
          rollup,
          range,
          account_id: accountId,
          tab,
        })}`,
        platformDashboardSchema,
        signal,
      ),
    placeholderData: keepPreviousData,
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
    mutationFn: (range: RangeKey) =>
      apiMutation(
        `/api/insights/generate${queryString({
          brand_id: selectedBrandId,
          rollup,
          range,
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
