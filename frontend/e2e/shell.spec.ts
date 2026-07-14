import { expect, test, type Page } from "@playwright/test";

const auth = {
  authenticated: true,
  user_id: "e2e-user",
  email: "owner@example.test",
  source_system: "accumulate",
  brand_id: "hotel-1",
  role: "agency_admin",
  access_mode: "write",
  settings_visible: true,
  is_internal_staff: true,
  expires_at: "2026-07-14T22:00:00+00:00",
  revoked: false,
};

const workspace = {
  default_brand_id: "hotel-1",
  brands: [
    {
      brand_id: "group-1",
      name: "Coastal Hotels",
      parent_brand_id: null,
      visibility: "hidden_parent",
      access_mode: null,
      role: null,
    },
    {
      brand_id: "hotel-1",
      name: "Coastal One",
      parent_brand_id: "group-1",
      visibility: "active",
      access_mode: "write",
      role: "agency_admin",
    },
    {
      brand_id: "hotel-2",
      name: "Coastal Two",
      parent_brand_id: "group-1",
      visibility: "active",
      access_mode: "read",
      role: "viewer",
    },
  ],
  families: [{ root_brand_id: "group-1", brand_ids: ["group-1", "hotel-1", "hotel-2"] }],
  scope: { requested_brand_id: "hotel-1", rollup: false, resolved_brand_ids: ["hotel-1"] },
};

const capabilities = {
  scope: workspace.scope,
  platforms: [
    {
      platform: "facebook",
      linked_account_count: 1,
      navigation_available: true,
      capabilities: [
        { platform: "facebook", capability: "profile", status: "not_configured", reason: "stored_account" },
      ],
    },
    {
      platform: "instagram",
      linked_account_count: 0,
      navigation_available: false,
      capabilities: [
        { platform: "instagram", capability: "profile", status: "not_configured", reason: "provider_not_configured" },
      ],
    },
    {
      platform: "tiktok",
      linked_account_count: 0,
      navigation_available: false,
      capabilities: [
        { platform: "tiktok", capability: "profile", status: "manual_activation_required", reason: "owner_activation_required" },
      ],
    },
  ],
  permissions: {
    settings_visible: true,
    internal_audit_visible: true,
    rollup_available: true,
    operation_mutation_available: false,
  },
  runtime: { mode: "dormant", writes_enabled: false, automated_schedule_available: false },
};

async function mockApi(page: Page, authenticated = true) {
  await page.route(/^http:\/\/127\.0\.0\.1:3010\/api\//, async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/auth/me") {
      await route.fulfill({ status: authenticated ? 200 : 401, json: authenticated ? auth : { detail: "session_invalid" } });
      return;
    }
    if (url.pathname === "/api/workspace/brands") {
      await route.fulfill({ json: workspace });
      return;
    }
    if (url.pathname === "/api/workspace/capabilities") {
      await route.fulfill({ json: capabilities });
      return;
    }
    if (url.pathname === "/api/platforms/facebook/accounts") {
      await route.fulfill({
        json: {
          meta: workspace.scope,
          platform: "facebook",
          accounts: [
            {
              account_id: 31,
              brand_id: "hotel-1",
              platform: "facebook",
              external_id: "page-31",
              display_name: "Coastal Facebook",
              status: "active",
              connection_state: "connected",
              health_status: "healthy",
              backfill_status: "complete",
              nightly_enabled: true,
              last_synced_at: null,
            },
          ],
        },
      });
      return;
    }
    await route.abort("blockedbyclient");
  });
}

test("desktop shell preserves a reloaded social route and capability navigation", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("desktop"), "desktop viewport assertion");
  await mockApi(page);
  await page.goto("/facebook");
  await expect(page.getByRole("heading", { name: "Facebook" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Facebook" })).toHaveAttribute("href", "/facebook");
  await expect(page.locator(".sidebar-link.locked").filter({ hasText: "Instagram" })).toHaveAttribute(
    "aria-disabled",
    "true",
  );
  await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();
  await expect(page.getByText("owner@example.test").first()).toBeVisible();
  await expect(page.getByText("Google Ads")).toHaveCount(0);

  await page.reload();
  await expect(page).toHaveURL(/\/facebook$/);
  await expect(page.getByRole("heading", { name: "Facebook" })).toBeVisible();
});

test("mobile shell uses a drawer and full-width selector grid", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("mobile"), "mobile viewport assertion");
  await mockApi(page);
  await page.goto("/overview");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.locator(".app-sidebar")).toHaveClass(/open/);
  await expect(page.locator(".sidebar-backdrop")).toHaveClass(/visible/);
  await page.locator(".sidebar-backdrop").click({ position: { x: 360, y: 400 } });
  await expect(page.locator(".app-sidebar")).not.toHaveClass(/open/);

  const selectorWidth = await page.locator(".topbar-selectors").evaluate((element) => element.getBoundingClientRect().width);
  expect(selectorWidth).toBeGreaterThan(300);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("unauthenticated route lands on the SSO-first screen", async ({ page }) => {
  await mockApi(page, false);
  await page.goto("/overview");
  await expect(page.getByRole("heading", { name: "Social Media" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Continue with Accumulate/ })).toBeVisible();
  await expect(page.getByText(/No local password/)).toBeVisible();
});
