import { expect, test } from "@playwright/test";

import { mockR5Api } from "./r5-fixtures";

for (const platform of ["facebook", "instagram", "tiktok"] as const) {
  test(`${platform} Cover matches the frozen R1 desktop/mobile surface`, async ({ page }) => {
    await mockR5Api(page);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(`/${platform}`);
    await expect(page.getByRole("heading", { name: `${platform === "tiktok" ? "TikTok" : `${platform[0]?.toUpperCase()}${platform.slice(1)}`} Dashboard` })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Cover" })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: "All Performing Content" })).toBeVisible();
    await page.getByRole("tab", { name: "Cover" }).focus();
    await expect(page.getByRole("tab", { name: "Cover" })).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(page).toHaveScreenshot(`${platform}-cover.png`, {
      animations: "disabled",
      fullPage: true,
      maxDiffPixelRatio: 0.01,
    });
  });
}
