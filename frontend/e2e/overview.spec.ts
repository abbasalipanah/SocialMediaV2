import { expect, test } from "@playwright/test";

import { mockR5Api } from "./r5-fixtures";

test("Overview matches the Accumulate information architecture with three supported platforms", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("desktop"), "desktop overview assertion");
  await mockR5Api(page);
  await page.goto("/overview");

  await expect(page.getByRole("heading", { name: "Social Media Overview" })).toBeVisible();
  await expect(page.locator(".social-kpi-label")).toHaveText([
    "Total Audience",
    "Total Reach",
    "Total Impressions",
    "Total Interactions",
    "Avg. Engagement",
    "Activity Score",
  ]);
  await expect(page.locator(".social-kpi-card")).toHaveCount(6);
  await expect(page.locator(".social-platform-card")).toHaveCount(3);

  for (const heading of [
    "Audience Growth",
    "Cross-Channel",
    "Content Type",
    "AI Insights",
    "Action Breakdown",
    "Top Performing Posts",
    "Platform Breakdown",
  ]) {
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }

  await page.getByRole("button", { name: "Open AI Insights" }).click();
  await expect(page.getByRole("dialog", { name: "AI Insights" })).toBeVisible();
  await expect(page.getByText("No generated insight exists for this Brand and date range.")).toBeVisible();
  await page.getByRole("dialog", { name: "AI Insights" }).getByRole("button", { name: "Close" }).click();

  const sidebar = page.getByRole("complementary", { name: "Primary navigation" });
  await expect(sidebar.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
  await expect(sidebar.getByRole("link", { name: "Overview" })).toHaveAttribute("href", "/overview");
});
