import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TikTokConnectionModal } from "../features/integrations/TikTokConnectionModal";

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("TikTokConnectionModal", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("ends the connecting state when an OAuth error carries the session Brand", async () => {
    const replace = vi.fn();
    const popup = {
      closed: false,
      close: vi.fn(),
      location: { replace },
    } as unknown as Window;
    vi.spyOn(window, "open").mockReturnValue(popup);
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/integrations/tiktok/self-service/readiness")) {
        return json({
          brand_id: "219392",
          can_manage: true,
          connection_state: "disconnected",
          linked_account_count: 0,
          linked_accounts: [],
          available_accounts: [],
          oauth_start_available: true,
          reason: "self_service_available",
          runtime_mode: "active",
          writes_enabled: true,
          checked_at: "2026-08-25T17:00:00Z",
        });
      }
      if (url.includes("/api/integrations/tiktok/oauth/start")) {
        return json({
          authorization_url: "https://www.tiktok.com/v2/auth/authorize/?state=signed",
          expires_at: "2026-08-25T17:15:00Z",
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
    const queryCache = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={queryCache}>
        <TikTokConnectionModal
          brandId="219392"
          brandName="Limak Ambassadore Hotel Ankara"
          onClose={vi.fn()}
          onConnected={vi.fn()}
        />
      </QueryClientProvider>,
    );

    await userEvent.click(await screen.findByRole("button", { name: "Connect TikTok" }));
    await waitFor(() => expect(replace).toHaveBeenCalledOnce());
    expect(screen.getByRole("button", { name: "Connecting…" })).toBeDisabled();

    window.dispatchEvent(new MessageEvent("message", {
      origin: window.location.origin,
      source: popup,
      data: {
        type: "social-media:tiktok-oauth",
        status: "error",
        brandId: "218998",
        connectionId: null,
        linkId: null,
        connectionState: "error",
        errorCode: "tiktok_self_service_account_already_connected",
      },
    }));

    expect(await screen.findByText("This TikTok account is already connected to another Brand. Sign out of TikTok, then authorize the account that belongs to this Brand.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Connect TikTok" })).toBeEnabled();
  });
});
