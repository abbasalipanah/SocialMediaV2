import { describe, expect, it } from "vitest";

import type { ReportingAccount, ReportingConnection } from "../api";
import { buildSocialIntegrations } from "../features/integrations";

const account: ReportingAccount = {
  account_id: 17,
  brand_id: "brand-1",
  platform: "facebook",
  external_id: "page-17",
  display_name: "Coastal Facebook",
  status: "active",
  connection_state: "connected",
  health_status: "healthy",
  backfill_status: "complete",
  link_status: "active",
  nightly_enabled: true,
  last_synced_at: null,
};

const connections: ReportingConnection[] = [
  {
    connection_id: 1,
    brand_id: "brand-1",
    platform: "facebook",
    state: "superseded",
    expires_at: null,
    projected_at: "2026-08-19T10:00:00Z",
  },
  {
    connection_id: 2,
    brand_id: "brand-1",
    platform: "facebook",
    state: "connected",
    expires_at: null,
    projected_at: "2026-08-20T10:00:00Z",
  },
];

describe("buildSocialIntegrations", () => {
  it("uses the newest provider connection after Meta is reauthorized", () => {
    const facebook = buildSocialIntegrations({
      accounts: [account],
      connections,
      jobs: [],
      readiness: undefined,
      capabilities: null,
    }).find((item) => item.platform === "facebook");

    expect(facebook?.connection?.connection_id).toBe(2);
    expect(facebook?.status).toBe("connected");
  });
});
