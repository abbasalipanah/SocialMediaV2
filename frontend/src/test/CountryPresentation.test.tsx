import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PulseHeatmapCard } from "../features/facebook/FacebookPulseDashboard";

import {
  CountryTableLabel,
  countryCode,
  countryDisplayName,
  countryFlagSrc,
  countryLookupKey,
} from "../features/dashboard/countryPresentation";

describe("country presentation", () => {
  it("expands provider country codes into full country names", () => {
    expect(countryDisplayName("TR")).toBe("Türkiye");
    expect(countryDisplayName("de")).toBe("Germany");
    expect(countryDisplayName("GB")).toBe("United Kingdom");
    expect(countryDisplayName("US")).toBe("United States");
    expect(countryCode("United States of America")).toBe("US");
    expect(countryCode("Others")).toBeNull();
    expect(countryLookupKey("TR")).toBe("turkey");
  });

  it("renders a local circular flag label for country tables", () => {
    const { container } = render(<CountryTableLabel value="TR" />);
    expect(screen.getByText("Türkiye")).toBeInTheDocument();
    // An image path, not the regional-indicator emoji: Windows renders no flag
    // for those code points and falls back to the two letters.
    expect(countryFlagSrc("TR")).toBe("/flags/tr.svg");
    expect(countryFlagSrc("Germany")).toBe("/flags/de.svg");
    expect(countryFlagSrc("Other")).toBeNull();
    const flag = container.querySelector(".country-flag");
    expect(flag).toHaveAttribute("src", "/flags/tr.svg");
    // Decorative: the country name beside it already carries the meaning.
    expect(flag).toHaveAttribute("alt", "");
  });
});

describe("hourly activity", () => {
  it("treats an all-zero grid as no data", () => {
    // The provider answers with the full 7x24 grid at zero when it has no
    // hourly activity to report; every heatmap row in the dataset is zero.
    const empty = [
      { dimension: "best_time_to_engage", metric_id: "interactions", items: [
        { key: "Fri|0", value: 0, percentage: null },
        { key: "Fri|1", value: 0, percentage: null },
      ] },
    ];
    render(<PulseHeatmapCard breakdowns={empty as never} />);
    expect(screen.getByText("No heatmap data in selected range.")).toBeInTheDocument();
  });

  it("draws the grid when the provider reports activity", () => {
    const filled = [
      { dimension: "best_time_to_engage", metric_id: "interactions", items: [
        { key: "Fri|10", value: 12, percentage: null },
      ] },
    ];
    render(<PulseHeatmapCard breakdowns={filled as never} />);
    expect(screen.queryByText("No heatmap data in selected range.")).not.toBeInTheDocument();
  });
});
