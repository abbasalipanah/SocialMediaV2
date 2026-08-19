import { describe, expect, it } from "vitest";

/**
 * Selecting a child Brand in Accumulate and launching Social Media opened
 * whatever Brand had been open last -- usually the parent, rolled up -- because
 * the remembered choice was preferred over the Brand the session was launched
 * with. Accumulate is the entry point: the Brand picked there is the one the
 * user asked to see.
 *
 * This mirrors the resolution in BrandScopeProvider's hydration effect.
 */
function resolveBrand(args: {
  launchBrandId: string;
  storedBrandId: string | null;
  workspaceDefaultBrandId: string;
  scope: string[];
}): string {
  const { launchBrandId, storedBrandId, workspaceDefaultBrandId, scope } = args;
  const brandIds = new Set(scope);
  const storedIsValid = Boolean(storedBrandId && brandIds.has(storedBrandId));
  return brandIds.has(launchBrandId)
    ? launchBrandId
    : storedIsValid && storedBrandId
      ? storedBrandId
      : workspaceDefaultBrandId;
}

const SCOPE = ["218998", "219392", "219397"];

describe("launch Brand priority", () => {
  it("opens the child Brand the launch names, not the remembered parent", () => {
    expect(
      resolveBrand({
        launchBrandId: "219397",
        storedBrandId: "218998",
        workspaceDefaultBrandId: "218998",
        scope: SCOPE,
      }),
    ).toBe("219397");
  });

  it("opens the launch Brand even when it is what was already remembered", () => {
    expect(
      resolveBrand({
        launchBrandId: "219392",
        storedBrandId: "219392",
        workspaceDefaultBrandId: "218998",
        scope: SCOPE,
      }),
    ).toBe("219392");
  });

  it("falls back to the remembered Brand when the launch names one out of scope", () => {
    expect(
      resolveBrand({
        launchBrandId: "999999",
        storedBrandId: "219397",
        workspaceDefaultBrandId: "218998",
        scope: SCOPE,
      }),
    ).toBe("219397");
  });

  it("falls back to the workspace default when nothing else is usable", () => {
    expect(
      resolveBrand({
        launchBrandId: "999999",
        storedBrandId: "888888",
        workspaceDefaultBrandId: "218998",
        scope: SCOPE,
      }),
    ).toBe("218998");
  });
});
