import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  V1_BAR_FILL_OPACITY,
  V1_CHART_COLORS,
  V1_FOLLOWER_FLOW_KEYS,
  V1_OVERVIEW_PLATFORM_COLORS,
  V1_TREND_FILL_BOTTOM_OPACITY,
  V1_TREND_FILL_TOP_OPACITY,
  V1_TREND_STROKE_WIDTH,
  displayTrendValue,
} from "../features/dashboard/visualPalette";

const frontendRoot = process.cwd();
const html = readFileSync(resolve(frontendRoot, "index.html"), "utf8");
const styles = readFileSync(resolve(frontendRoot, "src/styles.css"), "utf8");
const pulseDashboard = readFileSync(
  resolve(frontendRoot, "src/features/facebook/FacebookPulseDashboard.tsx"),
  "utf8",
);

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

  it("keeps the three connected channels and coming-soon card equally sized", () => {
    expect(styles).toContain(
      ".executive-overview .overview-platform-summary { grid-template-columns: repeat(4, minmax(0, 1fr));",
    );
    expect(styles).not.toContain("overview-coming-soon-platform { grid-column: span");
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
    expect(V1_OVERVIEW_PLATFORM_COLORS).toEqual({
      instagram: "#ec4899",
      facebook: "#2563eb",
      tiktok: "#111827",
    });
    expect(displayTrendValue(V1_FOLLOWER_FLOW_KEYS[1]!, 7)).toBe(-7);
    expect(displayTrendValue(V1_FOLLOWER_FLOW_KEYS[1]!, -7)).toBe(-7);
  });

  it("fills every trend series toward the zero baseline with its own line color", () => {
    expect(pulseDashboard).toContain("<AreaChart baseValue={0}");
    expect(pulseDashboard).toContain('fill={`url(#${gradientSeed}-${line.id})`}');
    expect(pulseDashboard).not.toContain('fill={index === 0 ?');
    expect(pulseDashboard).not.toContain('fill="transparent"');
  });

  it("keeps bar-chart tooltips without rendering a grey hover cursor", () => {
    expect(pulseDashboard).toContain(
      '<Tooltip cursor={false} labelFormatter={(value) => chartDate(String(value))} />',
    );
  });
});

describe("sidebar return link", () => {
  it("keeps the product name on one line", () => {
    // "Back to Accumulate AI" wrapped in the 236px rail, and a two-line pill
    // reads as two separate links.
    const body = styles.split(".sidebar-return-link {").at(1) ?? "";
    const rule = body.split("}").at(0) ?? "";
    expect(rule).toContain("white-space: nowrap");
  });
});
