import { expect, test } from "@playwright/test";

import { mockR5Api } from "./r5-fixtures";

test("Instagram Stories follows the approved responsive workspace", async ({ page }) => {
  await mockR5Api(page);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/instagram?tab=stories");

  await expect(page.getByRole("heading", { name: "Instagram Stories", exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Stories" })).toHaveAttribute("aria-selected", "true");
  for (const heading of ["Latest Story", "Story Live Status", "Evolution", "Story Health", "Behaviour", "History"]) {
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }

  await page.getByRole("button", { name: "Story 2: Poolside serenity" }).click();
  await expect(page.getByRole("button", { name: "Story 2: Poolside serenity" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("408", { exact: true }).first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await expect(page).toHaveScreenshot("instagram-stories.png", {
    animations: "disabled",
    fullPage: true,
    maxDiffPixelRatio: 0.01,
  });
});
