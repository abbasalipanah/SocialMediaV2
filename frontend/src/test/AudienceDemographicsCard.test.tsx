import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DashboardBreakdown } from "../api";
import { AudienceDemographicsCard } from "../features/dashboard/AudienceDemographicsCard";

describe("AudienceDemographicsCard", () => {
  it("does not mistake engagement heatmap dimensions for age data", () => {
    const breakdowns: DashboardBreakdown[] = [
      {
        metric_id: "interactions",
        dimension: "best_time_to_engage",
        items: [{ key: "Mon|18", value: 1900, percentage: 100 }],
      },
      {
        metric_id: "followers",
        dimension: "follower_demographics_age",
        items: [{ key: "18-24", value: 300, percentage: 100 }],
      },
      {
        metric_id: "followers",
        dimension: "follower_demographics_gender",
        items: [
          { key: "F", value: 200, percentage: 66.7 },
          { key: "M", value: 100, percentage: 33.3 },
        ],
      },
    ];

    render(<AudienceDemographicsCard breakdowns={breakdowns} />);

    expect(screen.getAllByText("18-24").length).toBeGreaterThan(0);
    expect(screen.queryByText("Mon|18")).not.toBeInTheDocument();
  });

  it("recognizes TikTok plural age and gender dimensions", () => {
    const breakdowns: DashboardBreakdown[] = [
      {
        metric_id: "followers",
        dimension: "audience_ages",
        items: [{ key: "25-34", value: 45, percentage: 100 }],
      },
      {
        metric_id: "followers",
        dimension: "audience_genders",
        items: [
          { key: "Female", value: 30, percentage: 66.7 },
          { key: "Male", value: 15, percentage: 33.3 },
        ],
      },
    ];

    render(<AudienceDemographicsCard breakdowns={breakdowns} />);

    expect(screen.getAllByText("25-34").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Women").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Men").length).toBeGreaterThan(0);
  });
});
