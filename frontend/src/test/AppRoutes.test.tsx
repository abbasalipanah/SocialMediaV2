import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../auth";
import { SOCIAL_NAVIGATION_LABELS } from "../layout/Sidebar";
import { AppRoutes } from "../routes";

const auth = {
  authenticated: true,
  user_id: "user-1",
  email: "owner@example.test",
  source_system: "accumulate",
  brand_id: "child-1",
  role: "agency_admin",
  access_mode: "write",
  settings_visible: true,
  is_internal_staff: true,
  expires_at: "2026-07-14T18:00:00+00:00",
  revoked: false,
};

const workspace = {
  default_brand_id: "child-1",
  brands: [
    {
      brand_id: "parent",
      name: "Parent Group",
      parent_brand_id: null,
      visibility: "hidden_parent",
      access_mode: null,
      role: null,
    },
    {
      brand_id: "child-1",
      name: "Hotel One",
      parent_brand_id: "parent",
      visibility: "active",
      access_mode: "write",
      role: "agency_admin",
    },
    {
      brand_id: "child-2",
      name: "Hotel Two",
      parent_brand_id: "parent",
      visibility: "active",
      access_mode: "read",
      role: "viewer",
    },
  ],
  families: [{ root_brand_id: "parent", brand_ids: ["child-1", "child-2", "parent"] }],
  scope: { requested_brand_id: "child-1", rollup: false, resolved_brand_ids: ["child-1"] },
};

function capabilities(settingsVisible = true) {
  return {
    scope: { requested_brand_id: "child-1", rollup: false, resolved_brand_ids: ["child-1"] },
    platforms: [
      {
        platform: "facebook",
        linked_account_count: 1,
        navigation_available: true,
        capabilities: [
          { platform: "facebook", capability: "profile", status: "available", reason: "linked" },
        ],
      },
      {
        platform: "instagram",
        linked_account_count: 0,
        navigation_available: false,
        capabilities: [
          {
            platform: "instagram",
            capability: "profile",
            status: "not_configured",
            reason: "provider_not_configured",
          },
        ],
      },
      {
        platform: "tiktok",
        linked_account_count: 0,
        navigation_available: false,
        capabilities: [
          {
            platform: "tiktok",
            capability: "profile",
            status: "manual_activation_required",
            reason: "owner_activation_required",
          },
        ],
      },
    ],
    permissions: {
      settings_visible: settingsVisible,
      internal_audit_visible: settingsVisible,
      rollup_available: true,
      operation_mutation_available: false,
    },
    runtime: {
      mode: "dormant",
      writes_enabled: false,
      automated_schedule_available: false,
    },
  };
}

const accounts = {
  meta: { requested_brand_id: "child-1", rollup: false, resolved_brand_ids: ["child-1"] },
  platform: "facebook",
  accounts: [
    {
      account_id: 17,
      brand_id: "child-1",
      platform: "facebook",
      external_id: "page-17",
      display_name: "Facebook Main",
      status: "active",
      connection_state: "connected",
      health_status: "healthy",
      backfill_status: "complete",
      nightly_enabled: true,
      last_synced_at: null,
    },
  ],
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockApi(options: { authenticated?: boolean; settingsVisible?: boolean } = {}) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/api/auth/me")) {
      return options.authenticated === false ? json({ detail: "session_invalid" }, 401) : json(auth);
    }
    if (url.includes("/api/auth/logout") && init?.method === "POST") return new Response(null, { status: 204 });
    if (url.includes("/api/workspace/brands")) return json(workspace);
    if (url.includes("/api/workspace/capabilities")) return json(capabilities(options.settingsVisible));
    if (url.includes("/api/platforms/facebook/accounts")) return json(accounts);
    throw new Error(`Unexpected request: ${url}`);
  });
}

function renderApp(route: string, fetchMock = mockApi()) {
  vi.stubGlobal("fetch", fetchMock);
  const queryCache = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return {
    fetchMock,
    ...render(
      <QueryClientProvider client={queryCache}>
        <MemoryRouter initialEntries={[route]}>
          <AuthProvider>
            <AppRoutes />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

function buttonContaining(text: string): HTMLButtonElement {
  const copy = screen.getByText(text);
  const button = copy.closest("button");
  if (!button) throw new Error(`No button contains ${text}`);
  return button;
}

describe("Phase 7 application shell", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("keeps the canonical page catalog limited to the three social channels", () => {
    expect(SOCIAL_NAVIGATION_LABELS).toEqual([
      "Overview",
      "Facebook",
      "Instagram",
      "TikTok",
    ]);
  });

  it("restores a real route and renders only capability-driven navigation", async () => {
    renderApp("/facebook");

    expect(await screen.findByRole("heading", { name: "Facebook" })).toBeInTheDocument();
    const primary = screen.getByRole("complementary", { name: "Primary navigation" });
    expect(within(primary).getByRole("link", { name: "Overview" })).toHaveAttribute("href", "/overview");
    await waitFor(() =>
      expect(within(primary).getByRole("link", { name: "Facebook" })).toHaveAttribute(
        "href",
        "/facebook",
      ),
    );
    expect(within(primary).getByText("Instagram").closest("div")).toHaveAttribute("aria-disabled", "true");
    expect(within(primary).getByText("TikTok").closest("div")).toHaveAttribute("aria-disabled", "true");
    expect(within(primary).getByRole("link", { name: "Settings" })).toBeInTheDocument();
    expect(within(primary).queryByText("Google Ads")).not.toBeInTheDocument();
  });

  it("opens the mobile drawer, closes on backdrop and signs out to the SSO-first login", async () => {
    const user = userEvent.setup();
    const { fetchMock } = renderApp("/overview");
    await screen.findByRole("heading", { name: "Social Media Overview" });

    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    const sidebar = screen.getByRole("complementary", { name: "Primary navigation" });
    expect(sidebar).toHaveClass("open");
    await user.click(screen.getAllByRole("button", { name: "Close navigation" })[0]!);
    expect(sidebar).not.toHaveClass("open");

    await user.click(within(sidebar).getByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("heading", { name: "Social Media" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Continue with Accumulate/ })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/logout",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });

  it("persists child scope, remembers an account, then resets it on Brand change", async () => {
    const user = userEvent.setup();
    renderApp("/facebook");
    await screen.findByRole("heading", { name: "Facebook" });

    await user.click(buttonContaining("Facebook Page"));
    await user.click(screen.getByRole("option", { name: /Facebook Main/ }));
    expect(window.localStorage.getItem("social-media-v2:selected-account:user-1:facebook")).toBe("17");

    await user.click(buttonContaining("Account group"));
    await user.click(screen.getByRole("option", { name: "Hotel Two" }));
    expect(window.localStorage.getItem("social-media-v2:selected-brand:user-1")).toBe("child-2");
    expect(window.localStorage.getItem("social-media-v2:selected-account:user-1:facebook")).toBeNull();
  });

  it("keeps a valid per-platform account selection while its account query is loading", async () => {
    window.localStorage.setItem("social-media-v2:selected-account:user-1:facebook", "17");
    renderApp("/facebook");
    await screen.findByRole("heading", { name: "Facebook" });
    await waitFor(() =>
      expect(buttonContaining("Facebook Page")).toHaveTextContent("Facebook Main"),
    );
    expect(window.localStorage.getItem("social-media-v2:selected-account:user-1:facebook")).toBe("17");
  });

  it("redirects a direct Settings route when the backend permission is absent", async () => {
    renderApp("/settings", mockApi({ settingsVisible: false }));
    expect(await screen.findByRole("heading", { name: "Social Media Overview" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();
  });

  it("shows the SSO-first login after an unauthenticated session check", async () => {
    renderApp("/overview", mockApi({ authenticated: false }));
    expect(await screen.findByRole("heading", { name: "Social Media" })).toBeInTheDocument();
    expect(screen.getByText(/No local password/)).toBeInTheDocument();
  });
});
