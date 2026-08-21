import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SetupDrawer } from "../features/settings/SetupDrawer";

vi.mock("../app/BrandScopeProvider", () => ({
  useBrandScope: () => ({
    rollup: true,
    capabilities: {
      permissions: {
        meta_connection_manage: true,
        tiktok_connection_manage: false,
      },
    },
  }),
}));

const scope = {
  requested_brand_id: "286272",
  rollup: false,
  resolved_brand_ids: ["286272"],
};

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("Brand Setup account editing", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("opens Meta editing for the exact Brand even while the page is a roll-up", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/settings/social-accounts")) {
        return json({
          meta: scope,
          items: [{
            account_id: 71,
            brand_id: "286272",
            platform: "facebook",
            external_id: "705375969509557",
            display_name: "Aquamice",
            status: "active",
            connection_state: "connected",
            health_status: "healthy",
            backfill_status: "complete",
            link_status: "connected",
            nightly_enabled: true,
            last_synced_at: "2026-08-21T04:40:00Z",
          }],
        });
      }
      if (url.includes("/api/settings/connections")) {
        return json({ meta: scope, items: [] });
      }
      if (url.includes("/api/settings/sync-jobs")) {
        return json({ meta: scope, items: [] });
      }
      if (url.includes("/api/integrations/meta/self-service/readiness")) {
        return json({
          brand_id: "286272",
          can_manage: true,
          connection_state: "connected",
          facebook_linked_count: 1,
          instagram_linked_count: 0,
          linked_accounts: [{
            platform: "facebook",
            external_id: "705375969509557",
            display_name: "Aquamice",
          }],
          discoveries: [],
          oauth_start_available: true,
          reason: "self_service_available",
          runtime_mode: "active",
          writes_enabled: true,
          checked_at: "2026-08-21T07:00:00Z",
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    }));

    const queryCache = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryCache}>
        <SetupDrawer
          accounts={[]}
          brand={{
            brand_id: "286272",
            name: "AquaMICE",
            parent_brand_id: null,
            visibility: "active",
            access_mode: "write",
            role: "agency_admin",
            linked_account_count: 1,
            last_sync_at: "2026-08-21T04:40:00Z",
          }}
          connections={[]}
          jobs={[]}
          mutationAvailable={false}
          onClose={vi.fn()}
          open
          readiness={undefined}
        />
      </QueryClientProvider>,
    );

    const setup = await screen.findByRole("dialog", { name: "Brand Setup" });
    await within(setup).findByText("Aquamice");
    const facebookRow = within(setup).getByText("Facebook").closest("article");
    if (!facebookRow) throw new Error("Facebook setup row was not rendered");
    const edit = within(facebookRow).getByRole("button", { name: "Edit" });
    expect(edit).toBeEnabled();
    await userEvent.click(edit);

    expect(await screen.findByRole("dialog", { name: "Manage social accounts" })).toBeVisible();

    const tiktokRow = within(setup).getByText("TikTok").closest("article");
    if (!tiktokRow) throw new Error("TikTok setup row was not rendered");
    expect(within(tiktokRow).getByRole("button", { name: "Connect" })).toBeDisabled();
  });
});
