import { expect, test, type Page } from "@playwright/test";

const auth = { authenticated: true, user_id: "product-user", email: "owner@example.test", source_system: "accumulate", brand_id: "hotel-1", role: "agency_admin", access_mode: "write", settings_visible: true, is_internal_staff: true, expires_at: "2026-07-14T22:00:00Z", revoked: false };
const scope = { requested_brand_id: "hotel-1", rollup: false, resolved_brand_ids: ["hotel-1"] };
const workspace = {
  default_brand_id: "hotel-1",
  brands: [
    { brand_id: "group-1", name: "Coastal Hotels", parent_brand_id: null, visibility: "hidden_parent", access_mode: null, role: null },
    { brand_id: "hotel-1", name: "Coastal One", parent_brand_id: "group-1", visibility: "active", access_mode: "write", role: "agency_admin" },
  ],
  families: [{ root_brand_id: "group-1", brand_ids: ["group-1", "hotel-1"] }],
  scope,
};
const capabilities = {
  scope,
  platforms: [
    { platform: "facebook", linked_account_count: 1, navigation_available: true, capabilities: [{ platform: "facebook", capability: "profile", status: "available", reason: "linked" }, { platform: "facebook", capability: "audience", status: "available", reason: "linked" }] },
    { platform: "instagram", linked_account_count: 0, navigation_available: false, capabilities: [{ platform: "instagram", capability: "profile", status: "not_configured", reason: "not_configured" }] },
    { platform: "tiktok", linked_account_count: 0, navigation_available: false, capabilities: [{ platform: "tiktok", capability: "profile", status: "manual_activation_required", reason: "owner_activation_required" }] },
  ],
  permissions: { settings_visible: true, internal_audit_visible: true, rollup_available: true, operation_mutation_available: false },
  runtime: { mode: "dormant", writes_enabled: false, automated_schedule_available: false },
};
const account = { account_id: 31, brand_id: "hotel-1", platform: "facebook", external_id: "page-31", display_name: "Coastal Facebook", status: "active", connection_state: "connected", health_status: "healthy", backfill_status: "complete", nightly_enabled: true, last_synced_at: "2026-07-14T11:00:00Z" };
const dashboard = {
  meta: { dashboard_id: "facebook", platform: "facebook", requested_brand_id: "hotel-1", rollup: false, resolved_brand_ids: ["hotel-1"], resolved_account_ids: [31], date_range: { start_on: "2026-06-15", end_on: "2026-07-14", key: "last_30_days" }, generated_at: "2026-07-14T12:00:00Z", last_sync_at: "2026-07-14T11:00:00Z", freshness: "fresh", observed_days: 30, expected_days: 30, data_status: "available", warnings: [] },
  metrics: [
    { metric_id: "followers", value: 1200, previous_value: 1100, delta_pct: 9.1, semantic_type: "snapshot", unit: "count", data_status: "available" },
    { metric_id: "interactions", value: null, previous_value: null, delta_pct: null, semantic_type: "flow", unit: "count", data_status: "unavailable" },
  ],
  series: [{ metric_id: "followers", semantic_type: "snapshot", points: [{ observed_on: "2026-06-15", value: 1100 }, { observed_on: "2026-07-14", value: 1200 }] }],
  breakdowns: [],
  content: [],
  community: { total_comments: 0, answered_comments: 0, unanswered_comments: 0, comment_likes: 0, data_status: "available" },
};

async function mockProductApi(page: Page) {
  await page.route(/^http:\/\/127\.0\.0\.1:3010\/api\//, async (route) => {
    const path = new URL(route.request().url()).pathname;
    const responses: Record<string, unknown> = {
      "/api/auth/me": auth,
      "/api/workspace/brands": workspace,
      "/api/workspace/capabilities": capabilities,
      "/api/platforms/facebook/accounts": { meta: scope, platform: "facebook", accounts: [account] },
      "/api/dashboards/facebook": dashboard,
      "/api/settings/brands": { meta: scope, items: workspace.brands.map((brand, index) => ({ ...brand, linked_account_count: index, last_sync_at: index ? account.last_synced_at : null })) },
      "/api/settings/social-accounts": { meta: scope, items: [account] },
      "/api/settings/brand-links": { meta: scope, items: [{ brand_id: "hotel-1", platform: "facebook", account_id: 31, external_id: "page-31", display_name: "Coastal Facebook", link_status: "active" }] },
      "/api/settings/connections": { meta: scope, items: [] },
      "/api/settings/sync-jobs": { meta: scope, items: [] },
      "/api/operations/readiness": { status: "ready", runtime_mode: "dormant", writes_enabled: false, database_configured: true, scope, platforms: [{ platform: "facebook", account_count: 1, last_sync_at: account.last_synced_at, pending_job_count: 0 }] },
    };
    if (path === "/api/settings/tiktok/activation-readiness") {
      await route.fulfill({ status: 403, json: { detail: "tiktok_owner_launch_required" } });
    } else if (path in responses) {
      await route.fulfill({ json: responses[path] });
    } else {
      await route.abort("blockedbyclient");
    }
  });
}

test("dashboard tabs, honest values and PNG export work on desktop", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("desktop"), "desktop product assertion");
  await mockProductApi(page);
  await page.goto("/facebook");
  await expect(page.getByRole("heading", { name: "Facebook", exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Cover" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Page" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Content" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Audience" })).toBeVisible();
  await page.getByRole("tab", { name: "Page" }).click();
  const indicators = page.getByLabel("Key performance indicators");
  await expect(indicators.getByText("1.2K")).toBeVisible();
  await expect(indicators.getByText("Unavailable", { exact: true })).toBeVisible();

  const pendingDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export PNG" }).click();
  const report = await pendingDownload;
  expect(report.suggestedFilename()).toBe("facebook-report.png");
});

test("Settings is table-first and the setup drawer stays social-only", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("desktop"), "desktop product assertion");
  await mockProductApi(page);
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(page.getByRole("cell", { name: /Coastal One/ })).toBeVisible();
  await page.getByRole("tab", { name: "Social Accounts" }).click();
  await expect(page.getByText("Coastal Facebook")).toBeVisible();
  await page.getByRole("button", { name: "Brand Setup" }).click();
  const drawer = page.getByRole("dialog", { name: "Brand Setup" });
  await expect(drawer).toBeVisible();
  await drawer.getByRole("button", { name: /Social Accounts/ }).click();
  await expect(drawer.getByText("Facebook")).toBeVisible();
  await expect(drawer.getByText("Instagram")).toBeVisible();
  await expect(drawer.getByText("TikTok")).toBeVisible();
  await expect(drawer.getByText("Google Ads")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect(page.getByRole("button", { name: "Brand Setup" })).toBeFocused();
});

test("direct TikTok activation is denied without a fresh signed owner launch", async ({ page }) => {
  const methods: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/settings/tiktok/activation-readiness")) methods.push(request.method());
  });
  await mockProductApi(page);
  await page.goto("/settings/tiktok/connect");
  await expect(page.getByText("Fresh owner launch required")).toBeVisible();
  expect(methods.length).toBeGreaterThan(0);
  expect(methods.every((method) => method === "GET")).toBe(true);
});
