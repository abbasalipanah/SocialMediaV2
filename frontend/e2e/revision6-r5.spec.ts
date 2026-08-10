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
    const followerFlow = page.locator(".facebook-trend-card", {
      has: page.getByRole("heading", { name: "New Followers Trend", exact: true }),
    }).first();
    await expect(followerFlow.locator(".recharts-area-curve")).toHaveCount(3);
    await expect(followerFlow.locator(".recharts-area-curve").nth(0)).toHaveAttribute("stroke", "#3b82f6");
    await expect(followerFlow.locator(".recharts-area-curve").nth(1)).toHaveAttribute("stroke", "#f59e0b");
    await expect(followerFlow.locator(".recharts-area-curve").nth(2)).toHaveAttribute("stroke", "#14b8a6");
    await expect(followerFlow.locator(".recharts-area-curve").nth(0)).toHaveAttribute("stroke-width", "1.25");
    await expect(followerFlow.locator(".facebook-chart-legend span")).toHaveText(["Follows", "Unfollows", "Net"]);
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
