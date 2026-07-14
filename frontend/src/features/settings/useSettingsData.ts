import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
  apiQuery,
  brandLinksSchema,
  connectionsSchema,
  queryString,
  readinessSchema,
  settingsBrandsSchema,
  socialAccountsSchema,
  syncJobsSchema,
} from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";

function hasRunningJobs(value: unknown): boolean {
  const parsed = syncJobsSchema.safeParse(value);
  return parsed.success && parsed.data.items.some((item) => ["pending", "running"].includes(item.status));
}

export function useSettingsData() {
  const { selectedBrandId, rollup } = useBrandScope();
  const queryCache = useQueryClient();
  const [completionMessage, setCompletionMessage] = useState("");
  const previouslyRunning = useRef(false);
  const scope = queryString({ brand_id: selectedBrandId, rollup });
  const common = { staleTime: 15_000 };

  const brands = useQuery({
    ...common,
    queryKey: ["settings", "brands", selectedBrandId, rollup],
    queryFn: ({ signal }) => apiQuery(`/api/settings/brands${scope}`, settingsBrandsSchema, signal),
  });
  const accounts = useQuery({
    ...common,
    queryKey: ["settings", "accounts", selectedBrandId, rollup],
    queryFn: ({ signal }) => apiQuery(`/api/settings/social-accounts${scope}`, socialAccountsSchema, signal),
  });
  const links = useQuery({
    ...common,
    queryKey: ["settings", "links", selectedBrandId, rollup],
    queryFn: ({ signal }) => apiQuery(`/api/settings/brand-links${scope}`, brandLinksSchema, signal),
  });
  const connections = useQuery({
    ...common,
    queryKey: ["settings", "connections", selectedBrandId, rollup],
    queryFn: ({ signal }) => apiQuery(`/api/settings/connections${scope}`, connectionsSchema, signal),
  });
  const jobs = useQuery({
    queryKey: ["settings", "jobs", selectedBrandId, rollup],
    queryFn: ({ signal }) => apiQuery(`/api/settings/sync-jobs${scope}`, syncJobsSchema, signal),
    refetchInterval: (query) => hasRunningJobs(query.state.data) ? 3_000 : false,
  });
  const readiness = useQuery({
    ...common,
    queryKey: ["operations", "readiness", selectedBrandId, rollup],
    queryFn: ({ signal }) => apiQuery(`/api/operations/readiness${scope}`, readinessSchema, signal),
  });

  useEffect(() => {
    const running = jobs.data?.items.some((item) => ["pending", "running"].includes(item.status)) ?? false;
    if (previouslyRunning.current && !running && jobs.isFetchedAfterMount) {
      setCompletionMessage("Sync activity completed. Reporting views were refreshed.");
      void queryCache.invalidateQueries({ queryKey: ["dashboard"] });
      void queryCache.invalidateQueries({ queryKey: ["settings"] });
    }
    previouslyRunning.current = running;
  }, [jobs.data, jobs.isFetchedAfterMount, queryCache]);

  return {
    brands,
    accounts,
    links,
    connections,
    jobs,
    readiness,
    completionMessage,
    dismissCompletion: () => setCompletionMessage(""),
  };
}
