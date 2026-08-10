import { expect, test } from "@playwright/test";

import { mockR5Api } from "./r5-fixtures";

test("dashboard tabs, URL state, ranges and report exports follow the R1 contract", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("desktop"), "desktop product assertion");
  await mockR5Api(page);
  await page.goto("/facebook?tab=content");

  await expect(page.getByRole("heading", { name: "Facebook Dashboard", exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Content" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "All Performing Content" })).toBeVisible();
  const contentTable = page.getByRole("heading", { name: "All Performing Content" }).locator("xpath=ancestor::article[1]");
  await expect(contentTable.getByRole("columnheader")).toHaveText([
    "#", "Cover", "Caption", "Date", "Type", "Post Views", "Post Reach", "Likes", "Comments", "Shares", "Engagement",
  ]);
  await expect(contentTable.getByRole("button", { name: "Sort by Date" }).locator("xpath=ancestor::th[1]"))
    .toHaveAttribute("aria-sort", "descending");
  await expect(contentTable.getByRole("link", { name: /Open content: Coastal sunrise/ })).toHaveAttribute(
    "href",
    "https://example.test/video-1",
  );
  await expect(contentTable.getByRole("link", { name: /Open cover: Coastal sunrise/ })).toHaveAttribute(
    "href",
    "https://example.test/video-1",
  );
  await expect(contentTable.getByText("10.2%")).toBeVisible();
  const videoType = contentTable.getByText("Video");
  await expect(videoType).toHaveClass(/is-video/);
  await expect(videoType.locator("svg")).toBeVisible();
  const engagementPie = page.getByRole("heading", { name: "Engagement Split" })
    .locator("xpath=ancestor::article[1]");
  const engagementSlice = engagementPie.locator(".facebook-pie-segment").first();
  await engagementSlice.hover({ position: { x: 148, y: 78 } });
  await expect(engagementSlice).toHaveClass(/is-active/);
  await expect(engagementSlice).not.toHaveAttribute("transform", "translate(0.00 0.00)");
  await expect(engagementPie.getByRole("status")).toContainText("Likes");
  await expect(engagementPie.getByRole("status")).toContainText("250");
  await expect(engagementPie.getByRole("status")).toContainText("79%");
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
  await page.getByRole("button", { name: "Download report" }).click();
  const exportDialog = page.getByRole("dialog", { name: "Download report" });
  await expect(exportDialog.getByRole("button", { name: /PNG snapshot/i })).toBeVisible();
  await expect(exportDialog.getByRole("button", { name: /Excel workbook/i })).toBeVisible();
  await expect(exportDialog).toContainText("Charts and card data by sheet");
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
