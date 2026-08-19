import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  PulsePieCard,
  sentimentPieRows,
} from "../features/facebook/FacebookPulseDashboard";

describe("PulsePieCard V1 interaction parity", () => {
  it("lifts the hovered slice and shows its label, value and percentage", () => {
    const { container } = render(
      <PulsePieCard
        rows={[
          { label: "Profile Visits", value: 609, color: "#2fb9d4" },
          { label: "Other", value: 247, color: "#8b5cf6" },
        ]}
        title="Engagement Split"
      />,
    );

    const chart = screen.getByRole("img", { name: "Engagement Split chart" });
    const profileSlice = within(chart).getByRole("button", {
      name: "Profile Visits: 609, 71%",
    });
    expect(profileSlice).toHaveAttribute("transform", "translate(0.00 0.00)");

    fireEvent.mouseEnter(profileSlice);
    expect(profileSlice).toHaveClass("is-active");
    expect(profileSlice).not.toHaveAttribute("transform", "translate(0.00 0.00)");
    expect(screen.getByRole("status")).toHaveTextContent("Profile Visits60971%");

    const graphic = container.querySelector(".facebook-pie-graphic");
    if (!graphic) throw new Error("Missing pie graphic");
    fireEvent.mouseLeave(graphic);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    const otherLegend = screen.getByRole("button", { name: "Highlight Other" });
    fireEvent.focus(otherLegend);
    expect(screen.getByRole("status")).toHaveTextContent("Other24729%");
  });

  it("renders a valid interactive ring for a single positive segment", () => {
    render(
      <PulsePieCard
        rows={[{ label: "Organic", value: 856, color: "#2fb9d4" }]}
        title="Reach Distribution"
      />,
    );
    const segment = within(screen.getByRole("img", { name: "Reach Distribution chart" }))
      .getByRole("button", { name: "Organic: 856, 100%" });
    expect(segment.getAttribute("d")).not.toMatch(/NaN|Infinity/u);
  });

  it("maps classified comment breakdowns to stable sentiment colors", () => {
    expect(
      sentimentPieRows([
        {
          metric_id: "interactions",
          dimension: "comment_sentiment",
          items: [
            { key: "negative", value: 1, percentage: 10 },
            { key: "positive", value: 8, percentage: 80 },
            { key: "neutral", value: 1, percentage: 10 },
          ],
        },
      ]),
    ).toEqual([
      { label: "Positive", value: 8, color: "#10b981" },
      { label: "Neutral", value: 1, color: "#f59e0b" },
      { label: "Negative", value: 1, color: "#ef4444" },
    ]);
  });
});
