import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { dashboardContentSchema } from "../api";
import { ContentSection } from "../features/dashboard/DashboardCards";
import { derivedContentTotals } from "../features/facebook/FacebookPulseDashboard";

const content = dashboardContentSchema.parse({
  account_id: 31,
  external_content_id: "video-a",
  content_type: "video",
  permalink: "https://www.youtube.com/watch?v=video-a",
  message: "Video",
  media_url: "",
  published_at: "2026-08-01T10:00:00Z",
  likes_count: 7,
  comments_count: null,
  shares_count: null,
  interactions: null,
  views: 100,
  reach: null,
  cover_url: null,
  thumbnail_url: null,
  cover_candidates: [],
  thumbnail_candidates: [],
  media_url_candidates: [],
  full_video_watched_rate: null,
  total_time_watched: null,
  average_time_watched: null,
  data_status: "partial",
});

describe("optional content engagement counters", () => {
  it("accepts unavailable provider counters without replacing them with zero", () => {
    expect(content.comments_count).toBeNull();
    expect(content.shares_count).toBeNull();
    expect(content.interactions).toBeNull();
    expect(derivedContentTotals([content])).toEqual({
      likes: 7,
      comments: null,
      shares: null,
      interactions: null,
    });
  });

  it("renders unavailable labels for unknown values", () => {
    render(<ContentSection content={[content]} />);

    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getAllByText("Unavailable")).toHaveLength(3);
  });
});
