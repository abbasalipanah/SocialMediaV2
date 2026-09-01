import { describe, expect, it } from "vitest";

import type { ReportingConnection } from "../api";
import { buildAuthorizationProviders } from "../features/integrations";

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
  {
    connection_id: 3,
    brand_id: "brand-1",
    platform: "tiktok",
    state: "pending_verification",
    expires_at: null,
    projected_at: "2026-08-21T10:00:00Z",
  },
  {
    connection_id: 4,
    brand_id: "brand-1",
    platform: "x",
    state: "connected",
    expires_at: null,
    projected_at: "2026-08-22T10:00:00Z",
  },
];

describe("buildAuthorizationProviders", () => {
  it("derives provider-level OAuth status without requiring account rows", () => {
    const providers = buildAuthorizationProviders(connections);

    expect(providers).toHaveLength(4);
    expect(providers.find((item) => item.provider === "meta")).toMatchObject({
      status: "authorized",
      connection: { connection_id: 2 },
    });
    expect(providers.find((item) => item.provider === "tiktok")).toMatchObject({
      status: "pending",
      connection: { connection_id: 3 },
    });
    expect(providers.find((item) => item.provider === "youtube")).toMatchObject({
      status: "not_authorized",
      connection: null,
    });
    expect(providers.find((item) => item.provider === "x")).toMatchObject({
      status: "authorized",
      connection: { connection_id: 4 },
    });
  });
});
