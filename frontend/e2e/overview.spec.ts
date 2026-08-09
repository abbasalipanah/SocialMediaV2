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

  await expect(page.getByText("No AI Summary has been generated for this Brand yet.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Open", exact: true })).toBeVisible();

  const sidebar = page.getByRole("complementary", { name: "Primary navigation" });
  await expect(sidebar.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
  await expect(sidebar.getByRole("link", { name: "Overview" })).toHaveCount(0);
});
