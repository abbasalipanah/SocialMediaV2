import assert from "node:assert/strict";
import { createHmac, randomUUID } from "node:crypto";
import { copyFileSync, readFileSync } from "node:fs";

import { chromium } from "@playwright/test";

const [envPath, baseUrl = "http://127.0.0.1:3026", pngArtifactPath] = process.argv.slice(2);
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
  let consumeResponse = null;
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
    if (url.pathname === "/sso/consume") consumeResponse = response;
    if (url.pathname.startsWith("/api/") && response.status() >= 500) {
      failures.push(`api:${response.status()}:${url.pathname}`);
    }
  });
  const signed = signedToken(identity);
  await page.goto(`${baseUrl}/sso/consume?token=${encodeURIComponent(signed.token)}`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForFunction(() => !window.location.pathname.includes("sso/consume"));
  assert.equal(consumeResponse?.status(), 303, "sso_consume_status");
  const consumeHeaders = consumeResponse?.headers() ?? {};
  assert.equal(consumeHeaders["cache-control"], "no-store", "sso_cache_control");
  assert.equal(consumeHeaders["referrer-policy"], "no-referrer", "sso_referrer_policy");
  const sessionCookie = (await context.cookies()).find(
    (cookie) => cookie.name === "social_media_session",
  );
  assert.ok(sessionCookie, "sso_session_cookie_missing");
  assert.equal(sessionCookie.httpOnly, true, "sso_session_cookie_not_http_only");
  assert.equal(sessionCookie.secure, true, "sso_session_cookie_not_secure");
  assert.equal(sessionCookie.sameSite, "Lax", "sso_session_cookie_same_site");
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

async function assertOverviewLayoutAndPng(page) {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto(`${baseUrl}/overview`);
  await page.getByRole("heading", { name: "Social Media Overview", exact: true }).waitFor();
  const channelSummary = page.locator(".overview-platform-summary");
  await channelSummary.waitFor();
  assert.equal(
    await channelSummary.evaluate((element) => (
      getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/u).length
    )),
    4,
    "overview_desktop_channel_column_count",
  );
  const channelCards = channelSummary.locator(":scope > .overview-platform-card");
  assert.equal(await channelCards.count(), 4, "overview_channel_card_count");
  const cardWidths = await channelCards.evaluateAll((elements) => (
    elements.map((element) => element.getBoundingClientRect().width)
  ));
  assert.ok(
    Math.max(...cardWidths) - Math.min(...cardWidths) < 1,
    `overview_channel_cards_not_equal:${cardWidths.join(",")}`,
  );

  const captureRoot = page.locator(".route-content > main");
  const captureSize = await captureRoot.evaluate((element) => ({
    height: Math.max(element.scrollHeight, element.clientHeight),
    scrollWidth: element.scrollWidth,
    width: Math.max(element.clientWidth, element.getBoundingClientRect().width),
  }));
  assert.equal(await captureRoot.locator(".app-sidebar").count(), 0, "overview_png_contains_sidebar");
  assert.equal(await captureRoot.locator(".app-topbar").count(), 0, "overview_png_contains_topbar");
  await page.getByRole("button", { name: "Download report" }).click();
  const exportDialog = page.getByRole("dialog", { name: "Download report" });
  await exportDialog.getByText("Main dashboard screenshot", { exact: true }).waitFor();
  const [download] = await Promise.all([
    page.waitForEvent("download", { timeout: 60_000 }),
    exportDialog.getByRole("button", { name: /PNG snapshot/iu }).click(),
  ]);
  const downloadPath = await download.path();
  assert.ok(downloadPath, "overview_png_download_path_missing");
  const png = readFileSync(downloadPath);
  assert.deepEqual(
    [...png.subarray(0, 8)],
    [137, 80, 78, 71, 13, 10, 26, 10],
    "overview_png_signature_invalid",
  );
  const pngWidth = png.readUInt32BE(16);
  const pngHeight = png.readUInt32BE(20);
  const widthScale = pngWidth / captureSize.width;
  const heightScale = pngHeight / captureSize.height;
  assert.ok(
    Math.abs(widthScale - heightScale) < 0.02,
    `overview_png_not_main_geometry:${pngWidth}x${pngHeight}:${captureSize.width}x${captureSize.height}`,
  );
  assert.ok(
    Math.abs((pngWidth / widthScale) - captureSize.width) < 1,
    `overview_png_uses_overflow_width:${pngWidth}:${captureSize.width}:${captureSize.scrollWidth}`,
  );
  assert.equal(await exportDialog.count(), 0, "overview_export_dialog_captured_state_visible");
}

async function assertInstagramPngGeometry(page) {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto(`${baseUrl}/instagram`);
  await page.getByRole("heading", { name: "Instagram Dashboard", exact: true }).waitFor();
  const captureRoot = page.locator(".route-content > main");
  const captureSize = await captureRoot.evaluate((element) => ({
    height: Math.max(element.scrollHeight, element.clientHeight),
    scrollWidth: element.scrollWidth,
    width: Math.max(element.clientWidth, element.getBoundingClientRect().width),
  }));
  const firstCard = page.locator(".facebook-pulse-card").first();
  const cardWidthBefore = await firstCard.evaluate((element) => element.getBoundingClientRect().width);
  const chartGeometry = await page.locator(".facebook-rechart").evaluateAll((charts) => (
    charts.map((chart) => {
      const chartRect = chart.getBoundingClientRect();
      const wrapper = chart.querySelector(".recharts-wrapper");
      const wrapperRect = wrapper?.getBoundingClientRect();
      return {
        chartWidth: chartRect.width,
        overflowRight: wrapperRect ? wrapperRect.right - chartRect.right : 0,
        wrapperWidth: wrapperRect?.width ?? 0,
      };
    })
  ));
  assert.ok(chartGeometry.length > 0, "instagram_chart_geometry_missing");
  for (const [index, geometry] of chartGeometry.entries()) {
    assert.ok(geometry.wrapperWidth <= geometry.chartWidth + 1, `instagram_chart_too_wide:${index}`);
    assert.ok(geometry.overflowRight <= 1, `instagram_chart_overflow_right:${index}`);
  }
  if (pngArtifactPath) {
    await captureRoot.screenshot({ animations: "disabled", path: `${pngArtifactPath}.native.png` });
  }
  await page.getByRole("button", { name: "Download report" }).click();
  const exportDialog = page.getByRole("dialog", { name: "Download report" });
  const [download] = await Promise.all([
    page.waitForEvent("download", { timeout: 60_000 }),
    exportDialog.getByRole("button", { name: /PNG snapshot/iu }).click(),
  ]);
  const downloadPath = await download.path();
  assert.ok(downloadPath, "instagram_png_download_path_missing");
  if (pngArtifactPath) copyFileSync(downloadPath, pngArtifactPath);
  const png = readFileSync(downloadPath);
  const pngWidth = png.readUInt32BE(16);
  const pngHeight = png.readUInt32BE(20);
  const scale = pngWidth / captureSize.width;
  assert.ok(
    Math.abs((pngHeight / scale) - captureSize.height) < 4,
    `instagram_png_main_geometry_changed:${pngWidth}x${pngHeight}:${captureSize.width}x${captureSize.height}`,
  );
  assert.ok(
    Math.abs((pngWidth / scale) - captureSize.width) < 1,
    `instagram_png_uses_svg_overflow_width:${pngWidth}:${captureSize.width}:${captureSize.scrollWidth}`,
  );
  assert.ok(
    Math.abs(await firstCard.evaluate((element) => element.getBoundingClientRect().width) - cardWidthBefore) < 1,
    "instagram_card_width_changed_after_png",
  );
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
  const days = {
    last_7_days: 7,
    last_30_days: 30,
    last_90_days: 90,
    last_365_days: 365,
  }[key];
  assert.ok(days, `unknown_range:${key}`);
  const end = new Date();
  end.setUTCHours(0, 0, 0, 0);
  end.setUTCDate(end.getUTCDate() - 1);
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - days + 1);
  return [start.toISOString().slice(0, 10), end.toISOString().slice(0, 10)];
}

function previousRange(startOn, endOn) {
  const start = new Date(`${startOn}T00:00:00Z`);
  const end = new Date(`${endOn}T00:00:00Z`);
  const days = Math.round((end.getTime() - start.getTime()) / 86_400_000) + 1;
  const previousEnd = new Date(start);
  previousEnd.setUTCDate(previousEnd.getUTCDate() - 1);
  const previousStart = new Date(previousEnd);
  previousStart.setUTCDate(previousStart.getUTCDate() - days + 1);
  return [
    previousStart.toISOString().slice(0, 10),
    previousEnd.toISOString().slice(0, 10),
  ];
}

function assertPreviousPeriodMetrics(current, previous, context) {
  const previousMetrics = new Map(previous.metrics.map((item) => [item.metric_id, item]));
  assert.equal(current.meta.date_range.key === "custom", false, `${context}:current_not_canonical`);
  assert.equal(previous.meta.date_range.key, "custom", `${context}:previous_not_custom`);
  for (const metric of current.metrics) {
    const previousMetric = previousMetrics.get(metric.metric_id);
    assert.ok(previousMetric, `${context}:${metric.metric_id}:previous_metric_missing`);
    assert.equal(
      metric.previous_value,
      previousMetric.value,
      `${context}:${metric.metric_id}:previous_value_period_mismatch`,
    );
    const expectedDelta = metric.value !== null
      && previousMetric.value !== null
      && previousMetric.value !== 0
      ? ((metric.value - previousMetric.value) / Math.abs(previousMetric.value)) * 100
      : null;
    if (expectedDelta === null) {
      assert.equal(metric.delta_pct, null, `${context}:${metric.metric_id}:delta_should_be_null`);
    } else {
      assert.ok(
        Math.abs(metric.delta_pct - expectedDelta) < 1e-9,
        `${context}:${metric.metric_id}:delta_formula_mismatch`,
      );
    }
  }
}

function assertCommunityPrivacy(data, context) {
  for (const item of data.community.top_commenters) {
    assert.equal(item.name, "Anonymous", `${context}:top_commenter_identity_exposed`);
  }
  for (const item of data.community.top_liked_comments) {
    assert.equal(item.name, "Anonymous", `${context}:liked_comment_identity_exposed`);
    const withoutMaskedMentions = item.comment.replace(
      /(^|[^\p{L}\p{N}_.%+-])@[\p{L}\p{N}_]\*{3}[\p{L}\p{N}_]/gu,
      "$1",
    );
    assert.equal(
      /(^|[^\p{L}\p{N}_.%+-])@[\p{L}\p{N}_]/u.test(withoutMaskedMentions),
      false,
      `${context}:comment_mention_exposed`,
    );
  }
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
    const [previousStart, previousEnd] = previousRange(start, end);
    const overview = await fetchJson(
      page,
      `/api/dashboards/overview?brand_id=18&rollup=false&range=${range}`,
    );
    const previousOverview = await fetchJson(
      page,
      `/api/dashboards/overview?brand_id=18&rollup=false&start_date=${previousStart}&end_date=${previousEnd}`,
    );
    assert.equal(overview.meta.date_range.start_on, start);
    assert.equal(overview.meta.date_range.end_on, end);
    assert.equal(previousOverview.meta.date_range.start_on, previousStart);
    assert.equal(previousOverview.meta.date_range.end_on, previousEnd);
    assert.equal(overview.meta.requested_brand_id, "18");
    assert.deepEqual(overview.meta.resolved_brand_ids, ["18"]);
    assert.ok(overview.metrics.length >= 5, `overview_metrics_empty:${range}`);
    assertPreviousPeriodMetrics(overview, previousOverview, `overview:${range}`);
    assertCommunityPrivacy(overview, `overview:${range}`);
    for (const platformData of overview.platforms) {
      assertCommunityPrivacy(platformData, `overview:${range}:${platformData.meta.dashboard_id}`);
    }
    for (const platform of platforms) {
      const data = await fetchJson(
        page,
        `/api/dashboards/${platform}?brand_id=18&rollup=false&range=${range}&tab=cover`,
      );
      const previousData = await fetchJson(
        page,
        `/api/dashboards/${platform}?brand_id=18&rollup=false&start_date=${previousStart}&end_date=${previousEnd}&tab=cover`,
      );
      assert.equal(data.meta.date_range.start_on, start);
      assert.equal(data.meta.date_range.end_on, end);
      assert.equal(previousData.meta.date_range.start_on, previousStart);
      assert.equal(previousData.meta.date_range.end_on, previousEnd);
      assert.equal(data.meta.data_status, "available");
      assertPreviousPeriodMetrics(data, previousData, `${platform}:${range}`);
      assertCommunityPrivacy(data, `${platform}:${range}`);
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

async function assertVisibleTrendAreaFills(page, context) {
  const areaCharts = await page.locator(".facebook-rechart").evaluateAll((charts) => (
    charts.flatMap((chart, index) => {
      const curves = [...chart.querySelectorAll(".recharts-area-curve")];
      if (curves.length === 0) return [];
      const areas = [...chart.querySelectorAll(".recharts-area-area")];
      return [{
        areas: areas.length,
        curves: curves.length,
        fills: areas.map((area) => area.getAttribute("fill")),
        index,
      }];
    })
  ));
  for (const chart of areaCharts) {
    assert.equal(chart.areas, chart.curves, `${context}:trend_area_count:${chart.index}`);
    assert.ok(
      chart.fills.every((fill) => fill?.startsWith("url(#")),
      `${context}:trend_area_color_missing:${chart.index}:${chart.fills.join(",")}`,
    );
  }
}

async function assertBarTooltipWithoutHoverCursor(page, platform) {
  const card = page.getByRole("heading", { name: "Performance Trends", exact: true })
    .locator("xpath=ancestor::article[1]");
  const bars = card.locator(".recharts-bar-rectangle");
  let hovered = false;
  for (let index = 0; index < await bars.count(); index += 1) {
    const bar = bars.nth(index);
    const box = await bar.boundingBox();
    if (!box || box.width < 1 || box.height < 1) continue;
    await bar.hover();
    hovered = true;
    break;
  }
  assert.equal(hovered, true, `${platform}:performance_bar_hover_target_missing`);
  await card.locator(".recharts-tooltip-wrapper").waitFor({ state: "visible" });
  assert.equal(
    await card.locator(".recharts-tooltip-cursor").count(),
    0,
    `${platform}:grey_bar_hover_cursor_visible`,
  );
}

async function assertCountryPresentation(page, context) {
  const countryHeading = page.getByRole("heading", { name: "Top Countries", exact: true });
  if (await countryHeading.count()) {
    const table = countryHeading.locator("xpath=ancestor::article[1]");
    const labels = table.locator(".country-table-label");
    if (await labels.count()) {
      const flags = table.locator(".country-flag");
      assert.equal(
        await flags.count(),
        await labels.count(),
        `${context}:country_table_flag_count`,
      );
      const flagGeometry = await flags.first().evaluate((element) => {
        const style = window.getComputedStyle(element);
        return {
          borderRadius: style.borderRadius,
          height: element.getBoundingClientRect().height,
          overflow: style.overflow,
          width: element.getBoundingClientRect().width,
        };
      });
      assert.ok(
        Math.abs(flagGeometry.width - flagGeometry.height) < 0.5
          && flagGeometry.borderRadius === "50%"
          && flagGeometry.overflow === "hidden",
        `${context}:country_table_flag_not_circular`,
      );
      const names = await labels.locator(":scope > span:last-child").allTextContents();
      assert.ok(
        names.every((name) => !/^[A-Z]{2}$/u.test(name.trim())),
        `${context}:country_table_uses_abbreviations:${names.join(",")}`,
      );
    }
  }
  const mapHeading = page.getByRole("heading", { name: "Audience by Country", exact: true });
  if (await mapHeading.count()) {
    const map = mapHeading.locator("xpath=ancestor::article[1]");
    assert.equal(
      await map.locator(".country-flag").count(),
      0,
      `${context}:audience_country_map_contains_flags`,
    );
    const regionNames = await map.locator(".instagram-top-regions p b").allTextContents();
    assert.ok(
      regionNames.every((name) => !/^[A-Z]{2}$/u.test(name.trim())),
      `${context}:audience_country_map_uses_abbreviations:${regionNames.join(",")}`,
    );
  }
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
      await assertVisibleTrendAreaFills(page, `${platform}:${tab}`);
      await assertCountryPresentation(page, `${platform}:${tab}`);
      if (tab === "cover") await assertBarTooltipWithoutHoverCursor(page, platform);
      if (tab === "stories") {
        const storyGallery = page.locator(".instagram-story-gallery");
        assert.ok(await storyGallery.locator("button").count() > 0);
        assert.equal(await page.getByText(/vs previous story/i).count(), 0, "story_comparison_visible");
        assert.equal(
          await storyGallery.evaluate((element) => getComputedStyle(element).gridColumnStart),
          "1",
          "story_gallery_not_left_aligned",
        );
        assert.equal(
          await storyGallery.evaluate((element) => getComputedStyle(element).gridColumnEnd),
          "-1",
          "story_gallery_not_full_width",
        );
        assert.match(
          (await page.locator(".instagram-story-metric").filter({ hasText: "Completion Rate" }).textContent()) ?? "",
          /\d+(?:\.\d+)?%/u,
          "story_completion_rate_missing",
        );
        assert.equal(await page.locator(".instagram-story-navigation-bar").count(), 0, "story_navigation_bar_visible");
        const behaviour = page.getByRole("heading", { name: "Behaviour", exact: true })
          .locator("xpath=ancestor::article[1]");
        const navigationChart = behaviour.getByRole("img", { name: "Story Navigation Split chart" });
        assert.ok(await navigationChart.getByRole("button").count() > 0, "story_navigation_pie_empty");
        const navigationSlice = navigationChart.getByRole("button").first();
        await navigationSlice.focus();
        assert.ok(
          (await navigationSlice.getAttribute("class"))?.includes("is-active"),
          "story_navigation_slice_inactive",
        );
        assert.match(
          (await behaviour.getByRole("status").textContent()) ?? "",
          /\d+(?:\.\d+)?%/u,
          "story_navigation_tooltip_percentage",
        );
        await navigationSlice.evaluate((element) => element.blur());
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
        const contentTable = page.getByRole("heading", { name: "All Performing Content", exact: true })
          .locator("xpath=ancestor::article[1]");
        assert.deepEqual(
          await contentTable.getByRole("columnheader").allTextContents(),
          ["#", "Cover", "Caption", "Date", "Type", "Post Views", "Post Reach", "Likes", "Comments", "Shares", "Engagement"],
          `${platform}:${tab}:content_headers`,
        );
        assert.equal(
          await contentTable.getByRole("button", { name: "Sort by Date" })
            .locator("xpath=ancestor::th[1]").getAttribute("aria-sort"),
          "descending",
          `${platform}:${tab}:default_sort`,
        );
        assert.ok(
          await contentTable.getByRole("link").count() > 0,
          `${platform}:${tab}:content_links_empty`,
        );
        const typeChips = contentTable.locator(".facebook-type-chip");
        assert.ok(await typeChips.count() > 0, `${platform}:${tab}:type_chips_empty`);
        assert.equal(
          await typeChips.locator("svg").count(),
          await typeChips.count(),
          `${platform}:${tab}:type_icons_missing`,
        );
        const engagement = (await contentTable.locator("tbody tr").first().locator("td").last().textContent())?.trim();
        assert.match(engagement ?? "", /^(?:\d+\.\d%|—)$/u, `${platform}:${tab}:engagement_format`);
        const engagementPie = page.getByRole("heading", { name: "Engagement Split", exact: true })
          .locator("xpath=ancestor::article[1]");
        const activeSlice = engagementPie.locator(".facebook-pie-segment").first();
        await activeSlice.focus();
        assert.ok((await activeSlice.getAttribute("class"))?.includes("is-active"), `${platform}:${tab}:pie_slice_inactive`);
        assert.notEqual(
          await activeSlice.getAttribute("transform"),
          "translate(0.00 0.00)",
          `${platform}:${tab}:pie_slice_not_lifted`,
        );
        const pieTooltip = engagementPie.getByRole("status");
        await pieTooltip.waitFor();
        assert.match((await pieTooltip.textContent()) ?? "", /\d+(?:\.\d+)?%/u, `${platform}:${tab}:pie_tooltip_percentage`);
        await activeSlice.evaluate((element) => element.blur());
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
    const { page, signed } = await consume(context, {
      userId: "r24-viewer-operator",
      brandId: 18,
      brandName: "Pine Beach Belek",
      role: "viewer",
      appRole: "operator",
    }, failures);
    await assertRole(page, {
      role: "viewer", appRole: "operator", settings: false, integrations: true, operator: true,
    });
    const replayContext = await browser.newContext();
    const replayPage = await replayContext.newPage();
    const replayResponse = await replayPage.goto(
      `${baseUrl}/sso/consume?token=${encodeURIComponent(signed.token)}`,
      { waitUntil: "domcontentloaded" },
    );
    assert.equal(replayResponse?.status(), 401, "sso_jti_replay_accepted");
    assert.equal((await replayContext.cookies()).length, 0, "replay_sso_cookie_created");
    await replayContext.close();
    await assertPineDataMatrix(page);
    await assertEveryProductSurface(page);
    await assertOverviewLayoutAndPng(page);
    await assertInstagramPngGeometry(page);
    const insights = await fetchJson(page, "/api/insights?brand_id=18&rollup=false");
    assert.ok(insights.items.length >= 1, "pine_ai_history_empty");
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
      default_brand_id: "28",
      brands: [
        {
          brand_id: "19", name: "Hilton", parent_brand_id: null, role: null,
          access_mode: null,
        },
        {
          brand_id: "28", name: "Hilton Garden Inn Mardin", parent_brand_id: "19",
          role: "agency_admin", access_mode: "write",
        },
      ],
    };
    const { page } = await consume(context, {
      userId: "r24-hidden-parent-agency-admin",
      brandId: 28,
      brandName: "Hilton Garden Inn Mardin",
      role: "agency_admin",
      brandScope,
    }, failures);
    const workspace = await fetchJson(
      page,
      "/api/workspace/brands?selected_brand_id=28&rollup=false",
    );
    const hiddenParent = workspace.brands.find((brand) => brand.brand_id === "19");
    assert.equal(hiddenParent?.visibility, "hidden_parent", "hidden_parent_visibility_lost");
    assert.equal(workspace.default_brand_id, "28", "hidden_parent_became_default");
    const hiddenDirect = await fetchResult(
      page,
      "/api/workspace/brands?selected_brand_id=19&rollup=false",
    );
    assert.equal(hiddenDirect.status, 403, "hidden_parent_direct_access_allowed");
    const hiddenRollup = await fetchJson(
      page,
      "/api/workspace/brands?selected_brand_id=19&rollup=true",
    );
    assert.deepEqual(hiddenRollup.scope.resolved_brand_ids, ["28"]);
    await assertOverview(page, "Hilton Garden Inn Mardin");
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
      userId: "r24-agency-operator",
      brandId: 18,
      brandName: "Pine Beach Belek",
      role: "agency_operator",
      expected: {
        role: "agency_operator", appRole: null, settings: false, integrations: false,
        operator: false,
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
  console.log(
    "r24_runtime_roles=super_admin,agency_admin,agency_operator,viewer,viewer_operator",
  );
  console.log("r24_runtime_ranges=last_7,last_30,last_90,last_365");
  console.log("r24_runtime_deltas=adjacent_equal_length_previous_period_verified");
  console.log("r24_runtime_comment_privacy=authors_anonymous_and_mentions_masked");
  console.log("r24_runtime_png=main_layout_without_app_chrome_and_equal_channel_cards_verified");
  console.log("r24_runtime_png_geometry=live_viewport_width_preserved_without_svg_overflow_reflow");
  console.log("r24_runtime_trends=every_visible_line_series_has_zero_baseline_color_fill");
  console.log("r24_runtime_bar_hover=tooltip_visible_without_grey_cursor");
  console.log("r24_runtime_countries=full_names_with_table_only_circular_flags");
  console.log("r24_runtime_surfaces=overview,facebook_4,instagram_5,tiktok_4");
  console.log(
    "r24_runtime_scope=account,brand,child,hidden_parent,rollup,cross_scope_denied",
  );
  console.log("r24_runtime_flows=settings,integrations,ai_history_limit,sso_expiry_logout");
  console.log("r24_runtime_console_request_server_errors=0");
  console.log("r24_runtime_e2e=verified");
} finally {
  await browser.close();
}
