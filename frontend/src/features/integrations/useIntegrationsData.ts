import { useQuery } from "@tanstack/react-query";

import {
  apiQuery,
  connectionsSchema,
  queryString,
  readinessSchema,
  socialAccountsSchema,
  syncJobsSchema,
} from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";

function hasRunningJobs(value: unknown): boolean {
  const parsed = syncJobsSchema.safeParse(value);
  return parsed.success
    && parsed.data.items.some((item) => ["pending", "running"].includes(item.status));
}

export function useIntegrationsData() {
  const { selectedBrandId, rollup } = useBrandScope();
  const scope = queryString({ brand_id: selectedBrandId, rollup });
  const common = { staleTime: 15_000 };

  const accounts = useQuery({
    ...common,
    queryKey: ["integrations", "accounts", selectedBrandId, rollup],
    queryFn: ({ signal }) => apiQuery(
      `/api/integrations/status/social-accounts${scope}`,
      socialAccountsSchema,
      signal,
    ),
  });
  const connections = useQuery({
    ...common,
    queryKey: ["integrations", "connections", selectedBrandId, rollup],
    queryFn: ({ signal }) => apiQuery(
      `/api/integrations/status/connections${scope}`,
      connectionsSchema,
      signal,
    ),
  });
  const jobs = useQuery({
    queryKey: ["integrations", "jobs", selectedBrandId, rollup],
    queryFn: ({ signal }) => apiQuery(
      `/api/integrations/status/sync-jobs${scope}`,
      syncJobsSchema,
      signal,
    ),
    refetchInterval: (query) => hasRunningJobs(query.state.data) ? 3_000 : false,
  });
  const readiness = useQuery({
    ...common,
    queryKey: ["integrations", "readiness", selectedBrandId, rollup],
    queryFn: ({ signal }) => apiQuery(
      `/api/operations/readiness${scope}`,
      readinessSchema,
      signal,
    ),
  });

  return { accounts, connections, jobs, readiness };
}
