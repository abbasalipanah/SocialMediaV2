import { useQuery } from "@tanstack/react-query";

import { apiQuery, connectionsSchema, queryString } from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";

export function useIntegrationsData() {
  const { selectedBrandId, rollup } = useBrandScope();
  const scope = queryString({ brand_id: selectedBrandId, rollup: false });

  const connections = useQuery({
    enabled: !rollup,
    staleTime: 15_000,
    queryKey: ["integrations", "authorizations", selectedBrandId],
    queryFn: ({ signal }) => apiQuery(
      `/api/integrations/status/connections${scope}`,
      connectionsSchema,
      signal,
    ),
  });

  return { connections };
}
