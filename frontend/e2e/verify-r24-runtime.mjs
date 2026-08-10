import assert from "node:assert/strict";
import { createHmac, randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

import { chromium } from "@playwright/test";

const [envPath, baseUrl = "http://127.0.0.1:3026"] = process.argv.slice(2);
if (!envPath) throw new Error("runtime_env_path_required");

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
  expiresIn = 3600,
  jti = `r24-${role}-${randomUUID()}`,
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
    jti,
    exp: Math.floor(issuedAt.getTime() / 1000) + expiresIn,
    sso_contract: contract,
  };
  const headerPart = base64url({ alg: "HS256", typ: "JWT" });
  const payloadPart = base64url(payload);
  const signature = createHmac("sha256", secret)
    .update(`${headerPart}.${payloadPart}`)
    .digest("base64url");
  return { jti, token: `${headerPart}.${payloadPart}.${signature}` };
}

async function fetchResult(page, path, options = {}) {
  return page.evaluate(async ({ url, init }) => {
    const response = await fetch(url, {
      headers: { Accept: "application/json", ...(init.headers ?? {}) },
      ...init,
    });
    const text = await response.text();
    let body = null;
    try { body = text ? JSON.parse(text) : null; } catch { body = text; }
    return { status: response.status, body };
  }, { url: path, init: options });
}

async function fetchJson(page, path) {
  const result = await fetchResult(page, path);
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
    if (url.pathname.startsWith("/api/") && response.status() >= 500) {
      failures.push(`api:${response.status()}:${url.pathname}`);
    }
  });
  const signed = signedToken(identity);
  await page.goto(`${baseUrl}/sso/consume?token=${encodeURIComponent(signed.token)}`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForFunction(() => !window.location.pathname.includes("sso/consume"));
  return { page, signed };
}

async function assertOverview(page, brandName) {
  await page.goto(`${baseUrl}/overview`);
  await page.getByRole("heading", { name: "Social Media Overview", exact: true }).waitFor();
  await page.getByText(brandName, { exact: true }).first().waitFor();
  assert.equal(await page.getByRole("link", { name: "Home", exact: true }).count(), 1);
  assert.equal(await page.getByRole("link", { name: "Overview", exact: true }).count(), 0);
  assert.equal(await page.locator(".overview-kpi-card").count(), 5);
}

async function logout(page) {
  const response = await fetchResult(page, "/api/auth/logout", {
    method: "POST",
    headers: { Origin: baseUrl },
  });
  assert.equal(response.status, 204, "logout_failed");
  const me = await fetchResult(page, "/api/auth/me");
  assert.equal(me.status, 401, "logout_session_still_active");
}

function expectedRange(key) {
  return {
    last_7_days: ["2026-08-03", "2026-08-09"],
    last_30_days: ["2026-07-11", "2026-08-09"],
    last_90_days: ["2026-05-12", "2026-08-09"],
    last_365_days: ["2025-08-10", "2026-08-09"],
  }[key];
}

async function assertPineDataMatrix(page) {
  const platforms = ["facebook", "instagram", "tiktok"];
  const ranges = ["last_7_days", "last_30_days", "last_90_days", "last_365_days"];
  const primaryMetrics = {
    facebook: ["followers", "new_followers", "reach", "views", "interactions", "engagement_rate"],
    instagram: ["followers", "new_followers", "reach", "views", "interactions", "engagement_rate"],
    tiktok: ["followers", "video_views_total", "video_likes_total", "video_comments_total", "video_shares_total", "video_engagement_rate"],
  };
  for (const range of ranges) {
    const [start, end] = expectedRange(range);
    const overview = await fetchJson(
      page,
      `/api/dashboards/overview?brand_id=18&rollup=false&range=${range}`,
    );
    assert.equal(overview.meta.date_range.start_on, start);
    assert.equal(overview.meta.date_range.end_on, end);
    assert.equal(overview.meta.requested_brand_id, "18");
    assert.deepEqual(overview.meta.resolved_brand_ids, ["18"]);
    assert.ok(overview.metrics.length >= 5, `overview_metrics_empty:${range}`);
    for (const platform of platforms) {
      const data = await fetchJson(
        page,
        `/api/dashboards/${platform}?brand_id=18&rollup=false&range=${range}&tab=cover`,
      );
      assert.equal(data.meta.date_range.start_on, start);
      assert.equal(data.meta.date_range.end_on, end);
      assert.equal(data.meta.data_status, "available");
      const metrics = new Map(data.metrics.map((item) => [item.metric_id, item.value]));
      for (const metric of primaryMetrics[platform]) {
        assert.notEqual(metrics.get(metric), null, `${platform}:${range}:${metric}:empty`);
      }
      const series = new Map(data.series.map((item) => [item.metric_id, item.points]));
      for (const metric of ["follows", "unfollows", "followers_net"]) {
        assert.ok(series.get(metric)?.length > 0, `${platform}:${range}:${metric}:trend_empty`);
      }
      if (platform === "tiktok" && range === "last_30_days") {
        assert.equal(series.get("views")?.length, 30, "tiktok_views_period_mismatch");
        assert.equal(series.get("reach")?.length, 30, "tiktok_reach_period_mismatch");
      }
    }
  }

  const accountIds = {};
  for (const platform of platforms) {
    const accounts = await fetchJson(
      page,
      `/api/platforms/${platform}/accounts?brand_id=18&rollup=false`,
    );
    assert.ok(accounts.accounts.length > 0, `${platform}_accounts_empty`);
    accountIds[platform] = accounts.accounts[0].account_id;
    const scoped = await fetchJson(
      page,
      `/api/dashboards/${platform}?brand_id=18&rollup=false&range=last_30_days&tab=cover&account_id=${accountIds[platform]}`,
    );
    assert.deepEqual(scoped.meta.resolved_account_ids, [accountIds[platform]]);
  }
  const denied = await fetchResult(
    page,
    `/api/dashboards/facebook?brand_id=18&range=last_30_days&account_id=${accountIds.instagram}`,
  );
  assert.equal(denied.status, 403, "cross_platform_account_scope_allowed");

  const instagramContent = await fetchJson(
    page,
    "/api/dashboards/instagram?brand_id=18&range=last_30_days&tab=content",
  );
  assert.ok(instagramContent.content.length > 0, "instagram_content_empty");
  assert.ok(
    instagramContent.content.every((item) => item.content_type.toLowerCase() !== "story"),
    "instagram_content_contains_story",
  );
  assert.ok(
    instagramContent.content_summary.by_type.every((item) => item.name.toLowerCase() !== "story"),
    "instagram_content_summary_contains_story",
  );
  const stories = await fetchJson(
    page,
    "/api/dashboards/instagram?brand_id=18&range=last_30_days&tab=stories",
  );
  assert.ok(stories.content.length > 0, "instagram_stories_empty");
  assert.ok(stories.content.every((item) => item.content_type.toLowerCase() === "story"));
}

async function assertEveryProductSurface(page) {
  await assertOverview(page, "Pine Beach Belek");
  const surfaces = {
    facebook: ["cover", "page", "content", "audience"],
    instagram: ["cover", "page", "content", "stories", "audience"],
    tiktok: ["cover", "account", "content", "audience"],
  };
  for (const [platform, tabs] of Object.entries(surfaces)) {
    for (const tab of tabs) {
      const query = tab === "cover" ? "" : `?tab=${tab}`;
      await page.goto(`${baseUrl}/${platform}${query}`);
      const platformName = platform === "tiktok"
        ? "TikTok"
        : `${platform[0].toUpperCase()}${platform.slice(1)}`;
      const heading = platform === "instagram" && tab === "stories"
        ? "Instagram Stories"
        : `${platformName} Dashboard`;
      await page.getByRole("heading", { name: heading, exact: true }).waitFor();
      assert.equal(await page.locator(".dashboard-error").count(), 0);
      if (tab === "stories") {
        assert.ok(await page.locator(".instagram-story-gallery button").count() > 0);
        assert.ok(await page.locator(".instagram-story-history tbody tr").count() > 0);
      } else {
        assert.equal(
          await page.locator(".facebook-pulse-kpi-grid").first()
            .locator(".facebook-pulse-kpi").count(),
          6,
          `${platform}:${tab}:kpi_count`,
        );
      }
      if (tab === "content" || tab === "cover") {
        await page.getByRole("heading", { name: "All Performing Content", exact: true }).waitFor();
        assert.ok(
          await page.getByRole("heading", { name: "All Performing Content", exact: true })
            .locator("xpath=ancestor::article[1]").getByRole("link").count() > 0,
          `${platform}:${tab}:content_links_empty`,
        );
      }
    }
  }
}

async function assertRole(page, expected) {
  const me = await fetchJson(page, "/api/auth/me");
  assert.equal(me.role, expected.role);
  assert.equal(me.app_role, expected.appRole);
  assert.equal(me.settings_visible, expected.settings);
  assert.equal(me.integrations_visible, expected.integrations);
  await page.getByRole("link", { name: "Home", exact: true }).waitFor();
  if (expected.settings) {
    await page.getByRole("link", { name: "Settings", exact: true }).waitFor();
  }
  if (expected.integrations) {
    await page.getByRole("link", { name: "Integrations", exact: true }).waitFor();
  }
  assert.equal(
    await page.getByRole("link", { name: "Settings", exact: true }).count(),
    expected.settings ? 1 : 0,
  );
  assert.equal(
    await page.getByRole("link", { name: "Integrations", exact: true }).count(),
    expected.integrations ? 1 : 0,
  );
  const settings = await fetchResult(page, "/api/settings/brands?brand_id=18&rollup=false");
  assert.equal(settings.status, expected.settings ? 200 : 403);
  const integrations = await fetchResult(
    page,
    "/api/integrations/status/social-accounts?brand_id=18&rollup=false",
  );
  assert.equal(integrations.status, expected.integrations ? 200 : 403);
  const limit = await fetchResult(page, "/api/insights/limit?brand_id=18&rollup=false");
  assert.equal(limit.status, expected.operator ? 200 : 403);
  if (expected.operator) {
    assert.equal(limit.body.weekly_limit, 1);
    assert.equal(limit.body.window_days, 7);
    assert.equal(limit.body.provider_configured, true);
  }
}

const browser = await chromium.launch({ headless: true });
const failures = [];
try {
  {
    const context = await browser.newContext();
    const { page } = await consume(context, {
      userId: "r24-viewer-operator",
      brandId: 18,
      brandName: "Pine Beach Belek",
      role: "viewer",
      appRole: "operator",
    }, failures);
    await assertRole(page, {
      role: "viewer", appRole: "operator", settings: false, integrations: true, operator: true,
    });
    await assertPineDataMatrix(page);
    await assertEveryProductSurface(page);
    const insights = await fetchJson(page, "/api/insights?brand_id=18&rollup=false");
    assert.ok(insights.items.length >= 1, "pine_ai_history_empty");
    await page.goto(`${baseUrl}/settings`);
    await page.waitForURL(/\/overview$/u);
    await page.goto(`${baseUrl}/integrations`);
    await page.getByRole("heading", { name: "Integrations", exact: true }).waitFor();
    await logout(page);
    await context.close();
  }

  for (const identity of [
    {
      userId: "r24-viewer",
      brandId: 18,
      brandName: "Pine Beach Belek",
      role: "viewer",
      expected: {
        role: "viewer", appRole: null, settings: false, integrations: false, operator: false,
      },
    },
    {
      userId: "r24-agency-admin",
      brandId: 18,
      brandName: "Pine Beach Belek",
      role: "agency_admin",
      expected: {
        role: "agency_admin", appRole: null, settings: true, integrations: true, operator: false,
      },
    },
    {
      userId: "r24-super-admin",
      brandId: 18,
      brandName: "Pine Beach Belek",
      role: "super_admin",
      expected: {
        role: "super_admin", appRole: null, settings: true, integrations: true, operator: false,
      },
    },
  ]) {
    const context = await browser.newContext();
    const { page } = await consume(context, identity, failures);
    await assertOverview(page, "Pine Beach Belek");
    await assertRole(page, identity.expected);
    if (identity.expected.settings) {
      await page.goto(`${baseUrl}/settings`);
      await page.getByRole("heading", { name: "Brand Setup and Account Mapping", exact: true }).waitFor();
    } else {
      await page.goto(`${baseUrl}/settings`);
      await page.waitForURL(/\/overview$/u);
    }
    if (identity.expected.integrations) {
      await page.goto(`${baseUrl}/integrations`);
      await page.getByRole("heading", { name: "Integrations", exact: true }).waitFor();
    } else {
      await page.goto(`${baseUrl}/integrations`);
      await page.waitForURL(/\/overview$/u);
    }
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
    const { page } = await consume(context, {
      userId: "r24-rollup-agency-admin",
      brandId: 19,
      brandName: "Hilton",
      role: "agency_admin",
      brandScope,
    }, failures);
    const workspace = await fetchJson(
      page,
      "/api/workspace/brands?selected_brand_id=19&rollup=true",
    );
    assert.equal(workspace.scope.rollup, true);
    assert.deepEqual(workspace.scope.resolved_brand_ids.map(String).sort(), ["19", "28", "29", "30"]);
    const rollup = await fetchJson(
      page,
      "/api/dashboards/overview?brand_id=19&rollup=true&range=last_30_days",
    );
    assert.equal(rollup.meta.rollup, true);
    assert.deepEqual(rollup.meta.resolved_brand_ids.map(String).sort(), ["19", "28", "29", "30"]);
    const child = await fetchJson(
      page,
      "/api/dashboards/overview?brand_id=28&rollup=false&range=last_30_days",
    );
    assert.deepEqual(child.meta.resolved_brand_ids, ["28"]);
    const denied = await fetchResult(
      page,
      "/api/dashboards/overview?brand_id=18&rollup=false&range=last_30_days",
    );
    assert.equal(denied.status, 403, "cross_brand_scope_allowed");
    await logout(page);
    await context.close();
  }

  {
    const context = await browser.newContext();
    const page = await context.newPage();
    const expired = signedToken({
      userId: "r24-expired",
      brandId: 18,
      brandName: "Pine Beach Belek",
      role: "viewer",
      expiresIn: -60,
    });
    const response = await page.goto(
      `${baseUrl}/sso/consume?token=${encodeURIComponent(expired.token)}`,
      { waitUntil: "domcontentloaded" },
    );
    assert.equal(response?.status(), 401, "expired_sso_accepted");
    assert.equal((await context.cookies()).length, 0, "expired_sso_cookie_created");
    await context.close();
  }

  assert.deepEqual(failures, [], `browser_failures:${failures.join("|")}`);
  console.log("r24_runtime_roles=super_admin,agency_admin,viewer,viewer_operator");
  console.log("r24_runtime_ranges=last_7,last_30,last_90,last_365");
  console.log("r24_runtime_surfaces=overview,facebook_4,instagram_5,tiktok_4");
  console.log("r24_runtime_scope=account,brand,child,rollup,cross_scope_denied");
  console.log("r24_runtime_flows=settings,integrations,ai_history_limit,sso_expiry_logout");
  console.log("r24_runtime_console_request_server_errors=0");
  console.log("r24_runtime_e2e=verified");
} finally {
  await browser.close();
}
