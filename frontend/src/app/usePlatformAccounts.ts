import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import {
  apiQuery,
  platformAccountsSchema,
  queryString,
  type Platform,
  type ReportingAccount,
} from "../api";
import { useBrandScope } from "./BrandScopeProvider";

type PlatformAccountsState = {
  accounts: ReportingAccount[];
  selectedAccountId: number | "all";
  isLoading: boolean;
  error: Error | null;
};

export function usePlatformAccounts(platform: Platform | null): PlatformAccountsState {
  const { selectedBrandId, rollup, accountSelections, selectAccount } = useBrandScope();
  const query = useQuery({
    enabled: platform !== null,
    queryKey: ["workspace", "accounts", platform, selectedBrandId, rollup],
    queryFn: ({ signal }) =>
      apiQuery(
        `/api/platforms/${platform}/accounts${queryString({
          brand_id: selectedBrandId,
          rollup,
        })}`,
        platformAccountsSchema,
        signal,
      ),
  });
  const accounts = query.data?.accounts ?? [];
  const remembered = platform ? accountSelections[platform] : undefined;
  const selectedAccountId =
    remembered !== undefined &&
    (remembered === "all" || accounts.some((account) => account.account_id === remembered))
      ? remembered
      : "all";

  useEffect(() => {
    if (
      query.isSuccess &&
      platform &&
      remembered !== undefined &&
      remembered !== selectedAccountId
    ) {
      selectAccount(platform, "all");
    }
  }, [platform, query.isSuccess, remembered, selectAccount, selectedAccountId]);

  return {
    accounts,
    selectedAccountId,
    isLoading: query.isPending,
    error: query.error,
  };
}
