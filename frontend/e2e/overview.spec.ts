import { expect, test } from "@playwright/test";

import { mockR5Api } from "./r5-fixtures";

test("Overview matches the approved executive information architecture with three supported platforms", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("desktop"), "desktop overview assertion");
  await mockR5Api(page);
  await page.goto("/overview");

  await expect(page.getByRole("heading", { name: "Social Media Overview" })).toBeVisible();
  await expect(page.locator(".social-kpi-label")).toHaveText([
    "Overall Organic Health",
    "Total Audience",
    "Total Reach",
    "Total Impressions",
    "Total Interactions",
    "Avg. Engagement",
  ]);
  await expect(page.locator(".social-kpi-card")).toHaveCount(6);
  await expect(page.locator(".social-platform-card")).toHaveCount(3);

  for (const heading of [
    "What Changed?",
    "Channel Health",
    "Performance Trend",
    "Content Snapshot",
    "Top Performing Content",
    "AI Summary",
  ]) {
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }

  const performanceChart = page.getByRole("img", { name: "Performance trend by platform" });
  await expect(performanceChart.locator(".overview-performance-area")).toHaveCount(3);
  await expect(performanceChart.locator(".overview-performance-line")).toHaveCount(3);
  await expect(performanceChart.locator('.overview-performance-line[data-series="instagram"]')).toHaveAttribute("stroke", "#ec4899");
  await expect(performanceChart.locator('.overview-performance-line[data-series="facebook"]')).toHaveAttribute("stroke", "#2563eb");
  await expect(performanceChart.locator('.overview-performance-line[data-series="tiktok"]')).toHaveAttribute("stroke", "#111827");
  await expect(performanceChart.locator(".overview-performance-line").first()).toHaveAttribute("stroke-width", "1.25");

  await expect(page.getByText("No AI Summary has been generated for this Brand yet.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Open", exact: true })).toBeVisible();

  const visualTheme = await page.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    const body = getComputedStyle(document.body);
    return {
      background: root.getPropertyValue("--sm-bg").trim(),
      copy: root.getPropertyValue("--sm-copy").trim(),
      muted: root.getPropertyValue("--sm-muted").trim(),
      primary: root.getPropertyValue("--sm-primary").trim(),
      bodyColor: body.color,
      bodyFont: body.fontFamily,
    };
  });
  expect(visualTheme).toEqual({
    background: "#f8fafc",
    copy: "#172033",
    muted: "#78849a",
    primary: "#5b4cf0",
    bodyColor: "rgb(23, 32, 51)",
    bodyFont: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  });

  const sidebar = page.getByRole("complementary", { name: "Primary navigation" });
  await expect(sidebar.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
  await expect(sidebar.getByRole("link", { name: "Overview" })).toHaveCount(0);
});
