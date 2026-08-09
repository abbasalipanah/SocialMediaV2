import { expect, test } from "@playwright/test";

import { mockR5Api } from "./r5-fixtures";

test("dashboard tabs, URL state, ranges and raw JSON export follow the R1 contract", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("desktop"), "desktop product assertion");
  await mockR5Api(page);
  await page.goto("/facebook?tab=content");

  await expect(page.getByRole("heading", { name: "Facebook Dashboard", exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Content" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "All Performing Content" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Content Winners by Objective" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Unanswered Comments Queue" })).toHaveCount(0);

  await page.getByRole("tab", { name: "Audience" }).click();
  await expect(page).toHaveURL(/\/facebook\?tab=audience$/);
  await page.goBack();
  await expect(page.getByRole("tab", { name: "Content" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Cover" }).click();
  await expect(page).toHaveURL(/\/facebook$/);

  await expect(page.getByLabel("Date period").locator("option")).toHaveText([
    "Last 7 Days", "Last 30 Days", "Last 90 Days", "Last 365 Days",
  ]);
  const pendingDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download dashboard data" }).click();
  const report = await pendingDownload;
  expect(report.suggestedFilename()).toBe("facebook-dashboard-2026-07-14.json");
});

test("Settings keeps the Performance-style table-first workspace", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("desktop"), "desktop product assertion");
  await mockR5Api(page);
  await page.goto("/settings");

  await expect(page.getByRole("heading", { name: "Brand Setup and Account Mapping" })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Primary navigation" })).toBeVisible();
  await expect(page.getByRole("tab")).toHaveText([
    "Brands", "Platform Accounts", "Mappings", "Sync & Backfill",
  ]);
  await expect(page.getByRole("columnheader")).toHaveText([
    "#", "ID", "Brand", "Status", "Access", "Linked", "Last sync", "Actions",
  ]);
  await page.getByPlaceholder("Search by name or ID").fill("Coastal One");
  const brandRow = page.getByRole("row", { name: /Coastal One/ });
  await expect(brandRow).toBeVisible();
  await expect(brandRow.getByRole("button", { name: "Edit" })).toBeVisible();
});

test("direct TikTok activation remains GET-only without a signed owner launch", async ({ page }) => {
  const methods: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/settings/tiktok/activation-readiness")) methods.push(request.method());
  });
  await mockR5Api(page);
  await page.goto("/settings/tiktok/connect");
  await expect(page.getByText("Fresh owner launch required")).toBeVisible();
  expect(methods.length).toBeGreaterThan(0);
  expect(methods.every((method) => method === "GET")).toBe(true);
});
