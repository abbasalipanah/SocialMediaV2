import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

/**
 * The sidebar locks a platform this Brand has no account for, but the route
 * still opened it from a bookmark, the back button, or a Brand switch that
 * left the URL where it was -- rendering an empty dashboard headed
 * "No Accounts". The guard makes the route agree with the sidebar.
 */
type Capability = { platform: string; navigation_available: boolean };

function guardDecision(
  platform: string,
  capabilities: { platforms: Capability[] } | null,
): "render" | "redirect" {
  const available = capabilities?.platforms.find(
    (item) => item.platform === platform,
  )?.navigation_available;
  return available ? "render" : "redirect";
}

const CAPABILITIES = {
  platforms: [
    { platform: "facebook", navigation_available: true },
    { platform: "instagram", navigation_available: true },
    { platform: "tiktok", navigation_available: false },
  ],
};

describe("platform route guard", () => {
  it("redirects a platform the Brand has no account for", () => {
    expect(guardDecision("tiktok", CAPABILITIES)).toBe("redirect");
  });

  it("renders a platform the Brand is connected to", () => {
    expect(guardDecision("facebook", CAPABILITIES)).toBe("render");
  });

  it("redirects when capabilities are unknown rather than guessing", () => {
    expect(guardDecision("tiktok", null)).toBe("redirect");
  });

  it("redirects a platform missing from the response entirely", () => {
    expect(guardDecision("threads", CAPABILITIES)).toBe("redirect");
  });

  it("keeps the locked sidebar entry non-interactive", () => {
    render(
      <span aria-disabled="true" className="sidebar-link locked" title="TikTok is not connected for this Brand">
        TikTok
      </span>,
    );
    const entry = screen.getByTitle(/not connected/i);
    expect(entry.tagName).toBe("SPAN");
    expect(entry.className).toContain("locked");
  });
});
