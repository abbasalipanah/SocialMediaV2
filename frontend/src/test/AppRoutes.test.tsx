import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "../routing";
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
      tiktok_connection_manage: true,
      meta_connection_manage: true,
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

const dashboard = {
  meta: {
    dashboard_id: "facebook",
    platform: "facebook",
    requested_brand_id: "child-1",
    rollup: false,
    resolved_brand_ids: ["child-1"],
    resolved_account_ids: [17],
    date_range: { start_on: "2026-06-15", end_on: "2026-07-14", key: "last_30_days" },
    generated_at: "2026-07-14T12:00:00Z",
    last_sync_at: "2026-07-14T12:00:00Z",
    freshness: "fresh",
    observed_days: 30,
    expected_days: 30,
    data_status: "available",
    warnings: [],
  },
  metrics: [],
  series: [],
  breakdowns: [],
  content: [],
  community: {
    total_comments: 0,
    answered_comments: 0,
    unanswered_comments: 0,
    comment_likes: 0,
    data_status: "unavailable",
    top_commenters: [],
    top_liked_comments: [],
  },
  top_hashtags: [],
  content_summary: { total: 0, by_type: [], reach_by_type: [], views_by_type: [], data_status: "unavailable" },
  source_breakdown: null,
  metric_methodology: { follower_flow: "unavailable", engagement_rate: "unavailable", reach: "unavailable" },
  audience_capabilities: { source: null, geo: "unavailable", age_gender: "unavailable", activity: "unavailable" },
  stories: null,
};

const settingsMeta = {
  requested_brand_id: "child-1",
  rollup: false,
  resolved_brand_ids: ["child-1"],
};

const settingsBrands = {
  meta: settingsMeta,
  items: [{
    brand_id: "child-1",
    name: "Hotel One",
    parent_brand_id: "parent",
    visibility: "active",
    access_mode: "write",
    role: "agency_admin",
    linked_account_count: 1,
    last_sync_at: "2026-07-14T12:00:00Z",
  }],
};

const socialAccounts = { meta: settingsMeta, items: accounts.accounts };
const brandLinks = {
  meta: settingsMeta,
  items: [{
    brand_id: "child-1",
    platform: "facebook",
    account_id: 17,
    external_id: "page-17",
    display_name: "Facebook Main",
    link_status: "active",
  }],
};
const connections = {
  meta: settingsMeta,
  items: [{
    connection_id: 1,
    brand_id: "child-1",
    platform: "facebook",
    state: "connected",
    expires_at: null,
    projected_at: "2026-07-14T12:00:00Z",
  }],
};
const syncJobs = { meta: settingsMeta, items: [] };
const readiness = {
  status: "ready",
  runtime_mode: "dormant",
  writes_enabled: false,
  database_configured: true,
  scope: settingsMeta,
  platforms: [{
    platform: "facebook",
    account_count: 1,
    last_sync_at: "2026-07-14T12:00:00Z",
    pending_job_count: 0,
  }],
};

const tiktokSelfServiceReadiness = {
  brand_id: "child-1",
  can_manage: true,
  connection_state: "disconnected",
  linked_account_count: 0,
  oauth_start_available: false,
  reason: "provider_activation_not_configured",
  runtime_mode: "dormant",
  writes_enabled: false,
  checked_at: "2026-07-14T12:00:00Z",
};

const metaSelfServiceReadiness = {
  brand_id: "child-1",
  can_manage: true,
  connection_state: "disconnected",
  facebook_linked_count: 1,
  instagram_linked_count: 0,
  oauth_start_available: false,
  reason: "provider_activation_not_configured",
  runtime_mode: "dormant",
  writes_enabled: false,
  checked_at: "2026-07-14T12:00:00Z",
  discoveries: [],
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
    if (url.includes("/api/dashboards/")) {
      const platform = (["facebook", "instagram", "tiktok"] as const)
        .find((item) => url.includes(`/api/dashboards/${item}`)) ?? "facebook";
      return json({ ...dashboard, meta: { ...dashboard.meta, dashboard_id: platform, platform } });
    }
    if (url.includes("/api/platforms/facebook/accounts")) return json(accounts);
    if (url.includes("/api/settings/social-accounts")) return json(socialAccounts);
    if (url.includes("/api/settings/brand-links")) return json(brandLinks);
    if (url.includes("/api/settings/connections")) return json(connections);
    if (url.includes("/api/settings/sync-jobs")) return json(syncJobs);
    if (url.includes("/api/settings/brands")) return json(settingsBrands);
    if (url.includes("/api/operations/readiness")) return json(readiness);
    if (url.includes("/api/integrations/tiktok/self-service/readiness")) return json(tiktokSelfServiceReadiness);
    if (url.includes("/api/integrations/meta/self-service/readiness")) return json(metaSelfServiceReadiness);
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
      "Home",
      "Analytics",
      "Social Media",
      "Facebook",
      "Instagram",
      "TikTok",
      "Settings",
    ]);
  });

  it("restores a real route and renders only capability-driven navigation", async () => {
    renderApp("/facebook");

    expect(await screen.findByRole("heading", { name: "Facebook Dashboard" }, { timeout: 3_000 })).toBeInTheDocument();
    const primary = screen.getByRole("complementary", { name: "Primary navigation" });
    expect(within(primary).getByRole("link", { name: "Home" })).toHaveAttribute("href", "/facebook");
    expect(within(primary).getByText("Analytics")).toBeInTheDocument();
    expect(within(primary).getByText("Social Media")).toBeInTheDocument();
    await waitFor(() =>
      expect(within(primary).getByRole("link", { name: "Facebook" })).toHaveAttribute(
        "href",
        "/facebook",
      ),
    );
    expect(within(primary).getByRole("link", { name: "Instagram" })).toHaveAttribute("href", "/instagram");
    expect(within(primary).queryByRole("link", { name: "TikTok" })).not.toBeInTheDocument();
    expect(within(primary).getAllByRole("link", { name: "Settings" })).toHaveLength(2);
    expect(within(primary).queryByText("Integrations")).not.toBeInTheDocument();
    expect(within(primary).queryByText("Support")).not.toBeInTheDocument();
    expect(within(primary).queryByText("Back to Accumulate")).not.toBeInTheDocument();
    expect(within(primary).queryByText("Sign out")).not.toBeInTheDocument();
  });

  it("opens the mobile drawer and closes it from the backdrop", async () => {
    const user = userEvent.setup();
    renderApp("/facebook");
    await screen.findByRole("heading", { name: "Facebook Dashboard" });

    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    const sidebar = screen.getByRole("complementary", { name: "Primary navigation" });
    expect(sidebar).toHaveClass("open");
    await user.click(screen.getAllByRole("button", { name: "Close navigation" })[0]!);
    expect(sidebar).not.toHaveClass("open");
  });

  it("persists child scope, remembers an account, then resets it on Brand change", async () => {
    const user = userEvent.setup();
    renderApp("/facebook");
    await screen.findByRole("heading", { name: "Facebook Dashboard" });

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
    await screen.findByRole("heading", { name: "Facebook Dashboard" });
    await waitFor(() =>
      expect(buttonContaining("Facebook Page")).toHaveTextContent("Facebook Main"),
    );
    expect(window.localStorage.getItem("social-media-v2:selected-account:user-1:facebook")).toBe("17");
  });

  it("redirects a direct Settings route when the backend permission is absent", async () => {
    renderApp("/settings", mockApi({ settingsVisible: false }));
    expect(await screen.findByRole("heading", { name: "Facebook Dashboard" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();
  });

  it("renders root and unknown authenticated routes as the standalone Settings surface", async () => {
    const { unmount } = renderApp("/");
    expect(await screen.findByRole("heading", { name: "Social media setup" })).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "Primary navigation" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("columnheader").map((item) => item.textContent)).toEqual([
      "Brand", "Meta Access", "Discovery", "Accounts", "Data", "Backfill", "Collector", "Last Sync", "Nightly", "Action",
    ]);
    unmount();

    renderApp("/not-a-dashboard-route");
    expect(await screen.findByRole("heading", { name: "Social media setup" })).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "Primary navigation" })).not.toBeInTheDocument();
  });

  it("accepts both canonical SSO consume aliases", async () => {
    const { unmount } = renderApp("/auth/sso/consume");
    expect(await screen.findByRole("heading", { name: "The sign-in link is incomplete" })).toBeInTheDocument();
    unmount();
    renderApp("/sso/consume");
    expect(await screen.findByRole("heading", { name: "The sign-in link is incomplete" })).toBeInTheDocument();
  });

  it("shows the SSO-first login after an unauthenticated session check", async () => {
    renderApp("/facebook", mockApi({ authenticated: false }));
    expect(await screen.findByRole("heading", { name: "Social Media" })).toBeInTheDocument();
    expect(screen.getByText(/No local password/)).toBeInTheDocument();
  });
});
