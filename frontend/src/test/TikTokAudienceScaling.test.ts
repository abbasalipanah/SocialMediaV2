import { describe, expect, it } from "vitest";

import type { DashboardBreakdown } from "../api";
import { followerScaledAudienceBreakdowns } from "../features/tiktok/TikTokPulseDashboard";

describe("TikTok audience shares", () => {
  it("scales provider shares to follower counts without touching engagement time", () => {
    const breakdowns: DashboardBreakdown[] = [
      {
        metric_id: "followers",
        dimension: "audience_ages",
        items: [
          { key: "18-24", value: 0.25, percentage: 25 },
          { key: "25-34", value: 0.75, percentage: 75 },
        ],
      },
      {
        metric_id: "interactions",
        dimension: "best_time_to_engage",
        items: [{ key: "Mon|18", value: 16, percentage: 100 }],
      },
    ];

    const result = followerScaledAudienceBreakdowns(breakdowns, 80);

    expect(result[0]?.items.map((item) => item.value)).toEqual([20, 60]);
    expect(result[1]).toBe(breakdowns[1]);
  });
});
