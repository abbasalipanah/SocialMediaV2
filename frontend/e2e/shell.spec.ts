import { expect, test } from "@playwright/test";

import { mockR5Api } from "./r5-fixtures";

test("desktop shell preserves canonical navigation and a reloaded platform route", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("desktop"), "desktop viewport assertion");
  await mockR5Api(page);
  await page.goto("/facebook");

  await expect(page.getByRole("heading", { name: "Facebook Dashboard", exact: true })).toBeVisible();
  const sidebar = page.getByRole("complementary", { name: "Primary navigation" });
  await expect(sidebar.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/tiktok");
  await expect(sidebar.getByText("Analytics")).toBeVisible();
  await expect(sidebar.getByText("Social Media")).toBeVisible();
  await expect(sidebar.getByRole("link", { name: "Facebook" })).toHaveAttribute("href", "/facebook");
  await expect(sidebar.getByRole("link", { name: "Instagram" })).toHaveAttribute("href", "/instagram");
  await expect(sidebar.getByRole("link", { name: "TikTok" })).toHaveAttribute("href", "/tiktok");
  await expect(sidebar.getByRole("link", { name: "Settings" })).toHaveCount(2);
  await expect(sidebar.getByText("Integrations")).toHaveCount(0);
  await expect(sidebar.getByText("Support")).toHaveCount(0);
  await expect(sidebar.getByText("Sign out")).toHaveCount(0);

  await page.reload();
  await expect(page).toHaveURL(/\/facebook$/);
  await expect(page.getByRole("heading", { name: "Facebook Dashboard", exact: true })).toBeVisible();
});

test("mobile shell uses an off-canvas drawer without horizontal page overflow", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.startsWith("mobile"), "mobile viewport assertion");
  await mockR5Api(page);
  await page.goto("/facebook");
  await expect(page.getByRole("heading", { name: "Facebook Dashboard", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.locator(".app-sidebar")).toHaveClass(/open/);
  await expect(page.locator(".sidebar-backdrop")).toHaveClass(/visible/);
  await page.locator(".sidebar-backdrop").click({ position: { x: 390, y: 500 } });
  await expect(page.locator(".app-sidebar")).not.toHaveClass(/open/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("unauthenticated route lands on the SSO-first entry gate", async ({ page }) => {
  await mockR5Api(page, false);
  await page.goto("/facebook");
  await expect(page.getByRole("heading", { name: "Social Media" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Continue with Accumulate/ })).toBeVisible();
  await expect(page.getByText(/No local password/)).toBeVisible();
});
