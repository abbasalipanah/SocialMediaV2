import { describe, expect, it } from "vitest";

import {
  oauthChannelLinkResponseSchema,
  oauthChannelReadinessSchema,
  oauthChannelStartSchema,
  oauthChannelUnlinkResponseSchema,
} from "../api";

describe("OAuth channel API contracts", () => {
  it("parses a YouTube readiness response without discarding account identity", () => {
    const response = oauthChannelReadinessSchema.parse({
      brand_id: "42",
      platform: "youtube",
      can_manage: true,
      connection_state: "pending_verification",
      linked_account_count: 1,
      linked_accounts: [{
        connection_id: 8,
        external_id: "UC-linked",
        display_name: "Linked channel",
        state: "linked",
      }],
      available_accounts: [{
        connection_id: 9,
        external_id: "UC-available",
        display_name: "Available channel",
        state: "available",
      }],
      oauth_start_available: true,
      reason: "self_service_available",
      runtime_mode: "development",
      writes_enabled: true,
      checked_at: "2026-09-01T10:00:00Z",
    });

    expect(response.available_accounts[0]).toMatchObject({
      connection_id: 9,
      external_id: "UC-available",
    });
  });

  it("parses the start, link and unlink command responses", () => {
    expect(oauthChannelStartSchema.parse({
      authorization_url: "https://accounts.example.test/oauth",
      expires_at: "2026-09-01T10:10:00Z",
    }).authorization_url).toContain("accounts.example.test");
    expect(oauthChannelLinkResponseSchema.parse({
      connection_id: 9,
      linked_count: 1,
      connection_state: "connected",
    }).linked_count).toBe(1);
    expect(oauthChannelUnlinkResponseSchema.parse({
      brand_id: "42",
      platform: "youtube",
      external_id: "UC-linked",
      connection_state: "disconnected",
    }).connection_state).toBe("disconnected");
  });

  it("rejects an unregistered channel platform", () => {
    const result = oauthChannelReadinessSchema.safeParse({
      brand_id: "42",
      platform: "tiktok",
      can_manage: false,
      connection_state: "disconnected",
      linked_account_count: 0,
      linked_accounts: [],
      available_accounts: [],
      oauth_start_available: false,
      reason: "provider_activation_not_configured",
      runtime_mode: "development",
      writes_enabled: false,
      checked_at: "2026-09-01T10:00:00Z",
    });

    expect(result.success).toBe(false);
  });
});
