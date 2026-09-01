import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OAuthChannelConnectionModal } from "../features/integrations/OAuthChannelConnectionModal";

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

const readiness = {
  brand_id: "42",
  platform: "youtube",
  can_manage: true,
  connection_state: "pending_verification",
  linked_account_count: 1,
  linked_accounts: [{
    connection_id: 12,
    external_id: "UC-linked",
    display_name: "Linked channel",
    state: "linked",
  }],
  available_accounts: [{
    connection_id: 12,
    external_id: "UC-new",
    display_name: "New channel",
    state: "available",
  }],
  oauth_start_available: true,
  reason: "self_service_available",
  runtime_mode: "development",
  writes_enabled: true,
  checked_at: "2026-09-01T10:00:00Z",
};

describe("OAuthChannelConnectionModal", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("links one authorization group and requires confirmation before unlinking", async () => {
    const requests: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      requests.push({ url, init });
      if (url.includes("/self-service/readiness")) return json(readiness);
      if (url.includes("/accounts/link")) return json({
        connection_id: 12,
        linked_count: 2,
        connection_state: "connected",
      });
      if (url.includes("/accounts/unlink")) return json({
        brand_id: "42",
        platform: "youtube",
        external_id: "UC-linked",
        connection_state: "disconnected",
      });
      throw new Error(`Unexpected request: ${url}`);
    }));
    const onChanged = vi.fn();
    const queryCache = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={queryCache}>
        <OAuthChannelConnectionModal
          brandId="42"
          brandName="Channel Brand"
          onChanged={onChanged}
          onClose={vi.fn()}
          provider="youtube"
        />
      </QueryClientProvider>,
    );

    const dialog = await screen.findByRole("dialog", { name: "Manage YouTube channels" });
    expect(await within(dialog).findByRole("checkbox", { name: /Linked channel/ })).toBeChecked();
    await userEvent.click(within(dialog).getByRole("checkbox", { name: /New channel/ }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Save selection (2)" }));

    await waitFor(() => expect(requests.some((request) => (
      request.url === "/api/integrations/youtube/accounts/link?brand_id=42"
      && request.init?.method === "POST"
      && request.init.body === JSON.stringify({
        connection_id: 12,
        external_ids: ["UC-linked", "UC-new"],
      })
    ))).toBe(true));

    const linkedSection = within(dialog).getByRole("region", { name: "Linked YouTube channels" });
    await userEvent.click(within(linkedSection).getByRole("button", { name: "Unlink" }));
    expect(within(linkedSection).getByRole("button", { name: "Confirm unlink" })).toBeEnabled();
    await userEvent.click(within(linkedSection).getByRole("button", { name: "Confirm unlink" }));

    await waitFor(() => expect(requests.some((request) => (
      request.url === "/api/integrations/youtube/accounts/unlink?brand_id=42&external_id=UC-linked"
      && request.init?.method === "DELETE"
    ))).toBe(true));
    expect(onChanged).toHaveBeenCalledTimes(2);
  });
});
