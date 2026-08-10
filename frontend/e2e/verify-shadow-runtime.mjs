import assert from "node:assert/strict";
import { createHmac, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

import { chromium } from "@playwright/test";

const [envPath, baseUrl = "http://127.0.0.1:3027"] = process.argv.slice(2);
if (!envPath) throw new Error("shadow_env_path_required");

function parseEnv(path) {
  const values = {};
  for (const rawLine of readFileSync(path, "utf8").split(/\r?\n/u)) {
    let line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    if (line.startsWith("export ")) line = line.slice(7).trimStart();
    const separator = line.indexOf("=");
    if (separator < 1) continue;
    const key = line.slice(0, separator);
    let value = line.slice(separator + 1).trim();
    if (
      value.length >= 2
      && ((value.startsWith('"') && value.endsWith('"'))
        || (value.startsWith("'") && value.endsWith("'")))
    ) value = value.slice(1, -1);
    values[key] = value;
  }
  return values;
}

const runtimeEnv = parseEnv(envPath);
const secret = runtimeEnv.SOCIAL_SSO_HS256_SECRET;
assert.ok(secret && Buffer.byteLength(secret) >= 32, "sso_secret_unavailable");
for (const key of [
  "SOCIAL_META_ACCOUNT_ENABLED",
  "SOCIAL_META_COLLECTION_ENABLED",
  "SOCIAL_TIKTOK_ACCOUNT_ENABLED",
  "SOCIAL_TIKTOK_COLLECTION_ENABLED",
  "SOCIAL_WORKER_SCHEDULE_ENABLED",
]) assert.equal(runtimeEnv[key], "false", `${key}_must_remain_disabled`);

function base64url(value) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

function signedToken({
  userId,
  brandId,
  brandName,
  role,
  appRole = null,
  brandScope = null,
}) {
  const issuedAt = new Date();
  const effectiveRole = appRole ?? role;
  const accessMode = ["super_admin", "agency_admin", "agency_operator"].includes(role)
    ? "write"
    : "read";
  const contract = {
    version: "v1",
    issued_at: issuedAt.toISOString(),
    user_id: userId,
    email: `${userId}@example.test`,
    brand_id: String(brandId),
    brand_name: brandName,
    brand_status: "active",
    role,
    platform_role: role,
    effective_role: effectiveRole,
    app_id: "social_media",
    entitlement_status: "enabled",
    access_mode: accessMode,
    access_start_at: null,
    access_expires_at: null,
    allowed_apps: ["social_media"],
    is_internal_staff: role !== "viewer",
    settings_visible: ["super_admin", "agency_admin"].includes(role),
    platform_branch_scope_mode: "all",
    platform_branches: [],
  };
  if (appRole) contract.app_role = appRole;
  if (brandScope) contract.brand_scope = brandScope;
  const payload = {
    iss: "accumulate",
    sub: userId,
    aud: "social_media",
    token_type: "app_sso",
    jti: `shadow-e2e-${role}-${randomUUID()}`,
    exp: Math.floor(issuedAt.getTime() / 1000) + 3600,
    sso_contract: contract,
  };
  const headerPart = base64url({ alg: "HS256", typ: "JWT" });
  const payloadPart = base64url(payload);
  const signature = createHmac("sha256", secret)
    .update(`${headerPart}.${payloadPart}`)
    .digest("base64url");
  return `${headerPart}.${payloadPart}.${signature}`;
}

async function fetchJson(page, path) {
  const result = await page.evaluate(async (url) => {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    return { status: response.status, body: await response.json() };
  }, path);
  assert.equal(result.status, 200, `api_status:${path}:${result.status}`);
  return result.body;
}

async function consume(context, identity, failures) {
  const page = await context.newPage();
  page.setDefaultTimeout(30_000);
  page.on("console", (message) => {
    if (
      message.type() === "error"
      && !message.text().startsWith("Failed to load resource:")
    ) failures.push(`console:${message.text()}`);
  });
  page.on("requestfailed", (request) => {
    const errorText = request.failure()?.errorText ?? "unknown";
    if (errorText === "net::ERR_ABORTED") return;
    const url = new URL(request.url());
    if (url.origin === new URL(baseUrl).origin) {
      failures.push(`requestfailed:${request.method()}:${url.pathname}:${errorText}`);
    }
  });
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (url.pathname.startsWith("/api/") && response.status() >= 400) {
      failures.push(`api:${response.status()}:${url.pathname}`);
    }
  });
  const token = signedToken(identity);
  await page.goto(`${baseUrl}/sso/consume?token=${encodeURIComponent(token)}`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForFunction(() => !window.location.pathname.includes("sso/consume"));
  return page;
}

async function assertOverview(page, brandName) {
  await page.goto(`${baseUrl}/overview`);
  await page.getByRole("heading", { name: "Social Media Overview", exact: true }).waitFor();
  await page.getByText(brandName, { exact: true }).first().waitFor();
  assert.equal(await page.getByRole("link", { name: "Home", exact: true }).count(), 1);
  assert.equal(await page.getByRole("link", { name: "Overview", exact: true }).count(), 0);
}

async function logout(page) {
  const status = await page.evaluate(async () => (
    await fetch("/api/auth/logout", { method: "POST" })
  ).status);
  assert.equal(status, 204, "logout_failed");
}

const browser = await chromium.launch({ headless: true });
const failures = [];
try {
  {
    const context = await browser.newContext();
    const page = await consume(context, {
      userId: "shadow-viewer-operator",
      brandId: 18,
      brandName: "Pine Beach Belek",
      role: "viewer",
      appRole: "operator",
    }, failures);
    await assertOverview(page, "Pine Beach Belek");
    const me = await fetchJson(page, "/api/auth/me");
    assert.equal(me.role, "viewer");
    assert.equal(me.app_role, "operator");
    assert.equal(me.settings_visible, false);
    assert.equal(me.integrations_visible, true);
    assert.equal(await page.getByRole("link", { name: "Settings", exact: true }).count(), 0);
    assert.equal(await page.getByRole("link", { name: "Integrations", exact: true }).count(), 1);

    const overview = await fetchJson(
      page,
      "/api/dashboards/overview?brand_id=18&rollup=false&range=last_30_days",
    );
    assert.ok(overview.metrics.length > 0, "pine_overview_metrics_empty");
    const insights = await fetchJson(page, "/api/insights?brand_id=18&rollup=false");
    assert.ok(insights.items.length >= 1, "pine_ai_history_empty");
    const limit = await fetchJson(page, "/api/insights/limit?brand_id=18&rollup=false");
    assert.equal(limit.weekly_limit, 1);
    assert.equal(limit.window_days, 7);
    assert.equal(limit.provider_configured, true);
    await page.getByText("AI Summary", { exact: true }).first().waitFor();

    for (const platform of ["facebook", "instagram", "tiktok"]) {
      await page.goto(`${baseUrl}/${platform}`);
      const platformName = platform === "tiktok"
        ? "TikTok"
        : `${platform[0].toUpperCase()}${platform.slice(1)}`;
      await page.getByRole("heading", {
        name: `${platformName} Dashboard`,
        exact: true,
      }).waitFor();
      assert.equal(
        await page.locator(".facebook-pulse-kpi-grid").first()
          .locator(".facebook-pulse-kpi").count(),
        6,
        `${platform}_cover_kpi_count`,
      );
      await page.getByRole("heading", { name: "All Performing Content", exact: true }).waitFor();
    }
    await page.goto(`${baseUrl}/instagram?tab=stories`);
    await page.getByRole("heading", { name: "Instagram Stories", exact: true }).waitFor();
    await page.getByRole("heading", { name: "History", exact: true }).waitFor();
    assert.ok(await page.locator(".instagram-story-gallery").count() >= 1, "story_gallery_missing");

    await page.goto(`${baseUrl}/settings`);
    await page.waitForURL(/\/overview$/u);
    await page.goto(`${baseUrl}/integrations`);
    await page.getByRole("heading", { name: "Integrations", exact: true }).waitFor();
    await logout(page);
    await context.close();
  }

  {
    const context = await browser.newContext();
    const brandScope = {
      version: "v1",
      default_brand_id: "19",
      brands: [
        { brand_id: "19", name: "Hilton", parent_brand_id: null, role: "agency_admin", access_mode: "write" },
        { brand_id: "28", name: "Hilton Garden Inn Mardin", parent_brand_id: "19", role: "agency_admin", access_mode: "write" },
        { brand_id: "29", name: "Hilton Garden Inn Şanlıurfa", parent_brand_id: "19", role: "agency_admin", access_mode: "write" },
        { brand_id: "30", name: "Hilton Garden Inn Kütahya", parent_brand_id: "19", role: "agency_admin", access_mode: "write" },
      ],
    };
    const page = await consume(context, {
      userId: "shadow-agency-admin",
      brandId: 19,
      brandName: "Hilton",
      role: "agency_admin",
      brandScope,
    }, failures);
    await page.getByRole("heading", { name: "Brand Setup and Account Mapping", exact: true }).waitFor();
    assert.equal(await page.getByRole("link", { name: "Settings", exact: true }).count(), 1);
    assert.equal(await page.getByRole("link", { name: "Integrations", exact: true }).count(), 1);
    const workspace = await fetchJson(
      page,
      "/api/workspace/brands?selected_brand_id=19&rollup=true",
    );
    assert.equal(workspace.scope.rollup, true);
    assert.deepEqual(workspace.scope.resolved_brand_ids.map(String).sort(), ["19", "28", "29", "30"]);
    await assertOverview(page, "Hilton");
    await page.goto(`${baseUrl}/settings`);
    await page.getByRole("heading", { name: "Brand Setup and Account Mapping", exact: true }).waitFor();
    await page.goto(`${baseUrl}/integrations`);
    await page.getByRole("heading", { name: "Integrations", exact: true }).waitFor();
    await logout(page);
    await context.close();
  }

  {
    const context = await browser.newContext();
    const page = await consume(context, {
      userId: "shadow-super-admin",
      brandId: 18,
      brandName: "Pine Beach Belek",
      role: "super_admin",
    }, failures);
    await page.getByRole("heading", { name: "Brand Setup and Account Mapping", exact: true }).waitFor();
    assert.equal(await page.getByRole("link", { name: "Settings", exact: true }).count(), 1);
    assert.equal(await page.getByRole("link", { name: "Integrations", exact: true }).count(), 1);
    await logout(page);
    await context.close();
  }

  {
    const context = await browser.newContext();
    const page = await consume(context, {
      userId: "shadow-empty-viewer-operator",
      brandId: 26,
      brandName: "test 1",
      role: "viewer",
      appRole: "operator",
    }, failures);
    await assertOverview(page, "test 1");
    const overview = await fetchJson(
      page,
      "/api/dashboards/overview?brand_id=26&rollup=false&range=last_30_days",
    );
    assert.equal(overview.content.length, 0);
    assert.equal(await page.getByRole("link", { name: "Settings", exact: true }).count(), 0);
    assert.equal(await page.getByRole("link", { name: "Integrations", exact: true }).count(), 1);
    await logout(page);
    await context.close();
  }

  assert.deepEqual(failures, [], `browser_failures:${failures.join("|")}`);
  console.log("shadow_browser_roles=viewer_operator,agency_admin,super_admin");
  console.log("shadow_browser_brands=data,parent_rollup,empty");
  console.log("shadow_browser_platforms=facebook,instagram_stories,tiktok");
  console.log("shadow_browser_ai=history_and_weekly_limit_verified");
  console.log("shadow_browser_console_and_api_errors=0");
  console.log("shadow_browser_e2e=verified");
} finally {
  await browser.close();
}
