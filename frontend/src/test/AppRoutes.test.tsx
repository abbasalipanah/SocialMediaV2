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
  app_role: null,
  access_mode: "write",
  settings_visible: true,
  integrations_visible: true,
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

function capabilities(settingsVisible = true, integrationsVisible = true) {
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
      integrations_visible: integrationsVisible,
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

const overviewDashboard = {
  meta: { ...dashboard.meta, dashboard_id: "overview", platform: null },
  metrics: dashboard.metrics,
  platforms: (["facebook", "instagram", "tiktok"] as const).map((platform) => ({
    ...dashboard,
    meta: { ...dashboard.meta, dashboard_id: platform, platform },
  })),
  content: dashboard.content,
  community: dashboard.community,
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

function mockApi(options: { authenticated?: boolean; integrationsVisible?: boolean; operator?: boolean; settingsVisible?: boolean } = {}) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/api/auth/me")) {
      return options.authenticated === false
        ? json({ detail: "session_invalid" }, 401)
        : json({
          ...auth,
          ...(options.operator ? { role: "viewer", app_role: "operator", access_mode: "read" } : {}),
          settings_visible: options.settingsVisible ?? true,
          integrations_visible: options.integrationsVisible ?? true,
        });
    }
    if (url.includes("/api/auth/logout") && init?.method === "POST") return new Response(null, { status: 204 });
    if (url.includes("/api/workspace/brands")) return json(workspace);
    if (url.includes("/api/workspace/capabilities")) return json(capabilities(
      options.settingsVisible,
      options.integrationsVisible,
    ));
    if (url.includes("/api/dashboards/overview")) return json(overviewDashboard);
    if (url.includes("/api/dashboards/")) {
      const platform = (["facebook", "instagram", "tiktok"] as const)
        .find((item) => url.includes(`/api/dashboards/${item}`)) ?? "facebook";
      return json({ ...dashboard, meta: { ...dashboard.meta, dashboard_id: platform, platform } });
    }
    if (url.includes("/api/platforms/facebook/accounts")) return json(accounts);
    if (url.includes("/api/insights/limit")) return json({
      provider_configured: true,
      can_generate: true,
      reason: "available",
      weekly_limit: 1,
      used: 0,
      remaining: 1,
      window_days: 7,
      last_generated_at: null,
      next_available_at: null,
      generation_in_progress: false,
    });
    if (url.includes("/api/insights/generate") && init?.method === "POST") return json({
      insight_id: 9,
      brand_id: "child-1",
      status: "completed",
      date_from: "2026-06-15",
      date_to: "2026-07-14",
      summary: "New generated summary.",
      recommendations: "[]",
      connector_analysis: "[]",
      anomalies: "[]",
      platform_evaluations: "[]",
      model: "test-model",
      error_message: null,
      created_by_user_sub: "user-1",
      created_at: "2026-07-14T12:00:00Z",
      completed_at: "2026-07-14T12:00:01Z",
    });
    if (url.includes("/api/insights")) return json({ meta: settingsMeta, items: [] });
    if (url.includes("/api/settings/social-accounts")) return json(socialAccounts);
    if (url.includes("/api/settings/brand-links")) return json(brandLinks);
    if (url.includes("/api/settings/connections")) return json(connections);
    if (url.includes("/api/settings/sync-jobs")) return json(syncJobs);
    if (url.includes("/api/settings/brands")) return json(settingsBrands);
    if (url.includes("/api/integrations/status/social-accounts")) return json(socialAccounts);
    if (url.includes("/api/integrations/status/connections")) return json(connections);
    if (url.includes("/api/integrations/status/sync-jobs")) return json(syncJobs);
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
      "Integrations",
    ]);
  });

  it("restores a real route and renders only capability-driven navigation", async () => {
    renderApp("/facebook");

    expect(await screen.findByRole("heading", { name: "Facebook Dashboard" }, { timeout: 3_000 })).toBeInTheDocument();
    const primary = screen.getByRole("complementary", { name: "Primary navigation" });
    expect(within(primary).getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
    expect(within(primary).getByText("Analytics")).toBeInTheDocument();
    expect(within(primary).getByText("Social Media")).toBeInTheDocument();
    expect(within(primary).queryByRole("link", { name: "Overview" })).not.toBeInTheDocument();
    await waitFor(() =>
      expect(within(primary).getByRole("link", { name: "Facebook" })).toHaveAttribute(
        "href",
        "/facebook",
      ),
    );
    // A channel the Brand has not connected keeps its place, locked, so the
    // navigation reads the same for every Brand instead of silently varying.
    for (const unconnected of ["Instagram", "TikTok"]) {
      expect(within(primary).queryByRole("link", { name: unconnected })).not.toBeInTheDocument();
      const locked = within(primary).getByTitle(`${unconnected} is not connected for this Brand`);
      expect(locked).toHaveAttribute("aria-disabled", "true");
      expect(locked).toHaveTextContent(unconnected);
    }
    expect(within(primary).getAllByRole("link", { name: "Settings" })).toHaveLength(1);
    expect(within(primary).getByRole("link", { name: "Integrations" })).toHaveAttribute("href", "/integrations");
    expect(within(primary).queryByText("Support")).not.toBeInTheDocument();
    // The shell is reached through Accumulate's signed launch, so the way back is
    // an explicit link out rather than any V2 route.
    expect(within(primary).getByRole("link", { name: "Back to Accumulate AI" })).toHaveAttribute(
      "href",
      "https://app.theaccumulate.com",
    );
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

  it("clears a remembered Brand and account when the authenticated scope changes", async () => {
    window.localStorage.setItem("social-media-v2:selected-brand:user-1", "legacy-brand");
    window.localStorage.setItem("social-media-v2:selected-account:user-1:facebook", "999");

    renderApp("/facebook");

    expect(await screen.findByRole("heading", { name: "Facebook Dashboard" })).toBeInTheDocument();
    await waitFor(() =>
      expect(window.localStorage.getItem("social-media-v2:selected-brand:user-1")).toBe("child-1"),
    );
    expect(window.localStorage.getItem("social-media-v2:selected-account:user-1:facebook")).toBeNull();
    expect(buttonContaining("Account group")).toHaveTextContent("Hotel One");
  });

  it("redirects a direct Settings route when the backend permission is absent", async () => {
    renderApp("/settings", mockApi({ settingsVisible: false }));
    expect(await screen.findByRole("heading", { name: "Social Media Overview" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();
  });

  it("renders root and unknown authenticated routes inside the standalone shell", async () => {
    const { unmount } = renderApp("/");
    expect(await screen.findByRole("heading", { name: "Social Media Overview" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Primary navigation" })).toBeInTheDocument();
    unmount();

    renderApp("/not-a-dashboard-route");
    expect(await screen.findByRole("heading", { name: "Social Media Overview" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Primary navigation" })).toBeInTheDocument();
  });

  it("never shows an old overview delta under a newly selected date period", async () => {
    const user = userEvent.setup();
    const followerMetric = (value: number, previousValue: number) => ({
      metric_id: "followers",
      value,
      previous_value: previousValue,
      delta_pct: ((value - previousValue) / previousValue) * 100,
      semantic_type: "snapshot",
      unit: "count",
      data_status: "available",
      methodology: "provider_reported",
      availability_reason: null,
    });
    const overviewFor = (key: "last_7_days" | "last_30_days", value: number, previousValue: number) => ({
      ...overviewDashboard,
      meta: {
        ...overviewDashboard.meta,
        date_range: key === "last_7_days"
          ? { start_on: "2026-07-08", end_on: "2026-07-14", key }
          : { start_on: "2026-06-15", end_on: "2026-07-14", key },
      },
      metrics: [followerMetric(value, previousValue)],
    });
    let resolveSeven!: (response: Response) => void;
    const sevenResponse = new Promise<Response>((resolve) => { resolveSeven = resolve; });
    const fallback = mockApi();
    const request = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/dashboards/overview")) {
        return url.includes("range=last_7_days")
          ? sevenResponse
          : Promise.resolve(json(overviewFor("last_30_days", 300, 200)));
      }
      return fallback(input, init);
    });
    renderApp("/", request);

    expect(await screen.findByText("300", { selector: ".overview-kpi-card > strong" })).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Date period" }), "last_7_days");
    expect(await screen.findByRole("main", { name: "Loading Social Media Overview" })).toBeInTheDocument();
    expect(screen.queryByText("300", { selector: ".overview-kpi-card > strong" })).not.toBeInTheDocument();

    resolveSeven(json(overviewFor("last_7_days", 700, 350)));
    expect(await screen.findByText("700", { selector: ".overview-kpi-card > strong" })).toBeInTheDocument();
  });

  it("never shows an old platform delta under a newly selected date period", async () => {
    const user = userEvent.setup();
    const platformFor = (key: "last_7_days" | "last_30_days", value: number, previousValue: number) => ({
      ...dashboard,
      meta: {
        ...dashboard.meta,
        date_range: key === "last_7_days"
          ? { start_on: "2026-07-08", end_on: "2026-07-14", key }
          : { start_on: "2026-06-15", end_on: "2026-07-14", key },
      },
      metrics: [{
        metric_id: "followers",
        value,
        previous_value: previousValue,
        delta_pct: ((value - previousValue) / previousValue) * 100,
        semantic_type: "snapshot",
        unit: "count",
        data_status: "available",
        methodology: "provider_reported",
        availability_reason: null,
      }],
    });
    let resolveSeven!: (response: Response) => void;
    const sevenResponse = new Promise<Response>((resolve) => { resolveSeven = resolve; });
    const fallback = mockApi();
    const request = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/dashboards/facebook")) {
        return url.includes("range=last_7_days")
          ? sevenResponse
          : Promise.resolve(json(platformFor("last_30_days", 300, 200)));
      }
      return fallback(input, init);
    });
    renderApp("/facebook", request);

    expect(await screen.findAllByText("300", { selector: ".facebook-pulse-kpi > strong" })).not.toHaveLength(0);
    await user.selectOptions(screen.getByRole("combobox", { name: "Date period" }), "last_7_days");
    expect(await screen.findByRole("main", { name: "Loading Facebook" })).toBeInTheDocument();
    expect(screen.queryAllByText("300", { selector: ".facebook-pulse-kpi > strong" })).toHaveLength(0);

    resolveSeven(json(platformFor("last_7_days", 700, 350)));
    expect(await screen.findAllByText("700", { selector: ".facebook-pulse-kpi > strong" })).not.toHaveLength(0);
  });

  it("shows weekly AI Summary generation only to the Accumulate viewer operator", async () => {
    window.localStorage.clear();
    const request = mockApi({ operator: true });
    renderApp("/", request);
    expect(await screen.findByRole("heading", { name: "AI Summary" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^Open$/ }));
    expect(await screen.findByRole("button", { name: "Generate summary" })).toBeEnabled();
    expect(screen.getByText(/One new summary is available/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Generate summary" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith(
      expect.stringContaining("/api/insights/generate"),
      expect.objectContaining({ method: "POST" }),
    ));
  });

  it("keeps one footer Settings link and renders the Performance-style workspace in the shell", async () => {
    renderApp("/settings");
    expect(await screen.findByRole("heading", { name: "Brand Setup and Account Mapping" })).toBeInTheDocument();
    const primary = screen.getByRole("complementary", { name: "Primary navigation" });
    expect(within(primary).getAllByRole("link", { name: "Settings" })).toHaveLength(1);
    expect(await screen.findByRole("tab", { name: "Brands" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Platform Accounts" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Mappings" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Sync & Backfill" })).toBeInTheDocument();
  });

  it("allows Integrations without exposing Settings when only the integration capability exists", async () => {
    renderApp("/integrations", mockApi({ settingsVisible: false, integrationsVisible: true }));
    expect(await screen.findByRole("heading", { name: "Integrations" })).toBeInTheDocument();
    const primary = screen.getByRole("complementary", { name: "Primary navigation" });
    expect(within(primary).queryByRole("link", { name: "Settings" })).not.toBeInTheDocument();
    expect(within(primary).getByRole("link", { name: "Integrations" })).toBeInTheDocument();
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
