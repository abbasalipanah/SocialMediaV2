import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MetaConnectionModal } from "../features/integrations/MetaConnectionModal";

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("MetaConnectionModal", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("automatically loads every available account through saved access without opening OAuth", async () => {
    const initialReadiness = {
      brand_id: "286272",
      can_manage: true,
      connection_state: "connected",
      facebook_linked_count: 1,
      instagram_linked_count: 1,
      linked_accounts: [
        { platform: "facebook", external_id: "705375969509557", display_name: "Aquamice" },
        { platform: "instagram", external_id: "17841409478093251", display_name: "aquamice_turkey" },
      ],
      discoveries: [
        { connection_id: 71, platform: "facebook", external_id: "705375969509557", display_name: "Aquamice", status: "linked" },
        { connection_id: 71, platform: "instagram", external_id: "17841409478093251", display_name: "aquamice_turkey", status: "linked" },
      ],
      oauth_start_available: true,
      reason: "self_service_available",
      runtime_mode: "active",
      writes_enabled: true,
      checked_at: "2026-08-20T20:00:00Z",
    };
    let refreshed = false;
    let tiktokLinked = true;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/integrations/tiktok/self-service/readiness")) {
        return json({
          brand_id: "286272",
          can_manage: true,
          connection_state: tiktokLinked ? "pending_verification" : "disconnected",
          linked_account_count: tiktokLinked ? 1 : 0,
          linked_accounts: tiktokLinked
            ? [{ external_id: "tt-44", display_name: "AquaMICE TikTok", state: "pending_verification" }]
            : [],
          oauth_start_available: true,
          reason: "self_service_available",
          runtime_mode: "active",
          writes_enabled: true,
          checked_at: "2026-08-21T07:00:00Z",
        });
      }
      if (url.includes("/api/integrations/tiktok/accounts/unlink") && init?.method === "DELETE") {
        tiktokLinked = false;
        return json({ brand_id: "286272", external_id: "tt-44", state: "disconnected" });
      }
      if (url.includes("/api/integrations/meta/self-service/readiness")) {
        return json(refreshed ? {
          ...initialReadiness,
          discoveries: [
            ...initialReadiness.discoveries,
            { connection_id: 71, platform: "facebook", external_id: "30003", display_name: "Mountain Page", status: "available" },
          ],
        } : initialReadiness);
      }
      if (url.includes("/api/integrations/meta/accounts/refresh") && init?.method === "POST") {
        refreshed = true;
        return json({
          connection_id: 71,
          facebook_count: 2,
          instagram_count: 1,
          discovered_count: 3,
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const open = vi.spyOn(window, "open");
    const manageTikTok = vi.fn();
    const queryCache = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={queryCache}>
        <MetaConnectionModal
          brandId="286272"
          brandName="AquaMICE"
          focusPlatform="facebook"
          onClose={vi.fn()}
          onConnected={vi.fn()}
          onManageTikTok={manageTikTok}
          tiktokAccounts={[{
            account_id: 9,
            brand_id: "286272",
            platform: "tiktok",
            external_id: "tt-44",
            display_name: "AquaMICE TikTok",
            status: "active",
            connection_state: "connected",
            health_status: "healthy",
            backfill_status: "complete",
            link_status: "linked",
            nightly_enabled: true,
            last_synced_at: "2026-08-21T07:00:00Z",
          }]}
        />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/integrations/meta/accounts/refresh"),
      expect.objectContaining({ method: "POST" }),
    ));
    expect(await screen.findByText(/3 Meta accounts loaded/)).toBeVisible();
    expect(await screen.findByText("Mountain Page")).toBeVisible();
    const catalog = screen.getByRole("region", { name: "Social accounts for AquaMICE" });
    expect(catalog).toBeVisible();
    expect(screen.queryByRole("button", { name: "Load available accounts" })).not.toBeInTheDocument();
    expect(screen.queryByText("Accounts load automatically")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Instagram/ }));
    expect(await within(catalog).findByText("aquamice_turkey")).toBeVisible();
    expect(within(catalog).queryByText("Mountain Page")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /TikTok/ }));
    expect(await within(catalog).findByText("AquaMICE TikTok")).toBeVisible();
    expect(within(catalog).getByText("pending verification")).toBeVisible();
    await userEvent.click(within(catalog).getByRole("button", { name: "Unlink" }));
    await userEvent.click(within(catalog).getByRole("button", { name: "Confirm unlink" }));
    expect(await screen.findByText("TikTok account unlinked from AquaMICE.")).toBeVisible();
    expect(within(catalog).queryByText("AquaMICE TikTok")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Connect TikTok" }));
    expect(manageTikTok).toHaveBeenCalledOnce();
    expect(open).not.toHaveBeenCalled();
  });
});
