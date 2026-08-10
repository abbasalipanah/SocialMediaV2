import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  V1_BAR_FILL_OPACITY,
  V1_CHART_COLORS,
  V1_FOLLOWER_FLOW_KEYS,
  V1_TREND_FILL_BOTTOM_OPACITY,
  V1_TREND_FILL_TOP_OPACITY,
  V1_TREND_STROKE_WIDTH,
  displayTrendValue,
} from "../features/dashboard/visualPalette";

const frontendRoot = process.cwd();
const html = readFileSync(resolve(frontendRoot, "index.html"), "utf8");
const styles = readFileSync(resolve(frontendRoot, "src/styles.css"), "utf8");

describe("V1 visual theme parity", () => {
  it("loads the same Inter weights used by the Accumulate shell", () => {
    expect(html).toContain("family=Inter:wght@300;400;500;600;700");
    expect(styles).toContain(
      'font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;',
    );
  });

  it("keeps the canonical V1 Social Media palette", () => {
    expect(styles).toContain("--sm-bg: #f8fafc;");
    expect(styles).toContain("--sm-copy: #172033;");
    expect(styles).toContain("--sm-muted: #78849a;");
    expect(styles).toContain("--sm-primary: #5b4cf0;");
    expect(styles).toContain("--sm-primary-soft: #f1efff;");
  });

  it("does not introduce pure-black UI colors", () => {
    expect(styles).not.toMatch(/#000(?:000)?\b|rgb\(0[ ,]+0[ ,]+0(?:\s*\/[^)]*)?\)|\bblack\b/i);
  });

  it("keeps V1 chart colors and rendering weights as one shared contract", () => {
    expect(V1_CHART_COLORS).toMatchObject({
      followers: "#38bdf8",
      follows: "#3b82f6",
      unfollows: "#f59e0b",
      netFollowers: "#14b8a6",
      views: "#5eead4",
      reach: "#ec4899",
    });
    expect(V1_FOLLOWER_FLOW_KEYS).toEqual([
      { id: "follows", label: "Follows", color: "#3b82f6" },
      {
        id: "unfollows",
        label: "Unfollows",
        color: "#f59e0b",
        display: "negative_absolute",
      },
      { id: "followers_net", label: "Net", color: "#14b8a6" },
    ]);
    expect(V1_TREND_STROKE_WIDTH).toBe(1.25);
    expect(V1_TREND_FILL_TOP_OPACITY).toBe(0.22);
    expect(V1_TREND_FILL_BOTTOM_OPACITY).toBe(0);
    expect(V1_BAR_FILL_OPACITY).toBe(0.82);
    expect(displayTrendValue(V1_FOLLOWER_FLOW_KEYS[1]!, 7)).toBe(-7);
    expect(displayTrendValue(V1_FOLLOWER_FLOW_KEYS[1]!, -7)).toBe(-7);
  });
});
