import { describe, expect, it } from "vitest";

import type { Platform } from "../api";
import {
  platformNavigationAvailable,
  previewPlatformsFromEnv,
} from "../platforms/navigation";

const capabilities = {
  platforms: [
    { platform: "facebook" as const, navigation_available: true },
    { platform: "tiktok" as const, navigation_available: false },
    { platform: "youtube" as const, navigation_available: false },
  ],
};

describe("local platform navigation preview", () => {
  it("parses only supported platform ids", () => {
    expect([...previewPlatformsFromEnv(" youtube, X,unknown, youtube ")]).toEqual([
      "youtube",
      "x",
    ]);
  });

  it("opens only the configured disconnected platform", () => {
    const preview = new Set<Platform>(["youtube"]);
    expect(platformNavigationAvailable("youtube", capabilities, preview)).toBe(true);
    expect(platformNavigationAvailable("tiktok", capabilities, preview)).toBe(false);
  });

  it("does not change connected platform navigation", () => {
    expect(platformNavigationAvailable("facebook", capabilities, new Set())).toBe(true);
  });
});
