import { describe, expect, it } from "vitest";

import {
  PLATFORM_CATALOG,
  PLATFORM_DESCRIPTIONS,
  PLATFORM_IDS,
  PLATFORM_LABELS,
  platformDefinition,
} from "../platforms/catalog";

describe("platform catalog", () => {
  it("keeps identifiers, routes, labels, and descriptions in one complete catalog", () => {
    expect(PLATFORM_CATALOG.map((platform) => platform.id)).toEqual(PLATFORM_IDS);
    expect(new Set(PLATFORM_CATALOG.map((platform) => platform.route)).size).toBe(
      PLATFORM_CATALOG.length,
    );

    for (const platform of PLATFORM_CATALOG) {
      expect(platformDefinition(platform.id)).toBe(platform);
      expect(PLATFORM_LABELS[platform.id]).toBe(platform.label);
      expect(PLATFORM_DESCRIPTIONS[platform.id]).toBe(platform.description);
    }
  });
});
