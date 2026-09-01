import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PlatformDashboard } from "../api";
import {
  XPulseDashboard,
  withXContentSeries,
  xContentTotals,
} from "../features/x/XPulseDashboard";

const comparison = (value: number | null, previous: number | null = null) => ({
  value,
  previous_value: previous,
  delta_pct: value !== null && previous ? ((value - previous) / previous) * 100 : null,
});

const dashboard: PlatformDashboard = {
  meta: {
    dashboard_id: "x",
    platform: "x",
    requested_brand_id: "18",
    rollup: false,
    resolved_brand_ids: ["18"],
    resolved_account_ids: [81],
    date_range: { start_on: "2026-08-01", end_on: "2026-08-31", key: "last_30_days" },
    generated_at: "2026-09-01T12:00:00Z",
    last_sync_at: "2026-09-01T11:00:00Z",
    freshness: "fresh",
    observed_days: 2,
    expected_days: 31,
    data_status: "partial",
    warnings: [],
  },
  metrics: [
    { metric_id: "followers", value: 1200, previous_value: 1175, delta_pct: 2.13, semantic_type: "snapshot", unit: "count", data_status: "available", methodology: "provider_reported", availability_reason: null },
    { metric_id: "new_followers", value: 25, previous_value: 20, delta_pct: 25, semantic_type: "flow", unit: "count", data_status: "available", methodology: "derived:positive_snapshot_delta:v1", availability_reason: null },
    { metric_id: "media_count", value: 88, previous_value: 85, delta_pct: 3.53, semantic_type: "snapshot", unit: "count", data_status: "available", methodology: "provider_reported", availability_reason: null },
  ],
  series: [
    { metric_id: "followers", semantic_type: "snapshot", points: [{ observed_on: "2026-08-30", value: 1175 }, { observed_on: "2026-08-31", value: 1200 }], methodology: "provider_reported" },
    { metric_id: "media_count", semantic_type: "snapshot", points: [{ observed_on: "2026-08-30", value: 85 }, { observed_on: "2026-08-31", value: 88 }], methodology: "provider_reported" },
  ],
  breakdowns: [],
  content: [
    {
      account_id: 81,
      external_content_id: "1900000000000000001",
      content_type: "image",
      permalink: "https://x.com/i/web/status/1900000000000000001",
      message: "Product launch #accumulate",
      media_url: "",
      published_at: "2026-08-31T10:00:00Z",
      likes_count: 70,
      comments_count: 12,
      shares_count: 9,
      interactions: 96,
      views: 2400,
      reach: null,
      cover_url: null,
      thumbnail_url: null,
      cover_candidates: [],
      thumbnail_candidates: [],
      media_url_candidates: [],
      full_video_watched_rate: null,
      total_time_watched: null,
      average_time_watched: null,
      saves_count: 5,
      profile_visits: 18,
      data_status: "partial",
    },
  ],
  community: {
    total_comments: 0,
    answered_comments: 0,
    unanswered_comments: 0,
    comment_likes: 0,
    data_status: "unavailable",
    top_commenters: [],
    top_liked_comments: [],
  },
  top_hashtags: [{ name: "#accumulate", count: 1 }],
  content_summary: {
    total: 1,
    by_type: [{ name: "Image", value: 1 }],
    reach_by_type: [],
    views_by_type: [{ name: "Image", value: 2400 }],
    data_status: "partial",
  },
  content_metrics: {
    views: comparison(2400, 2000),
    reach: comparison(null),
    likes: comparison(70, 60),
    comments: comparison(12, 10),
    shares: comparison(9, 6),
    interactions: comparison(96, 80),
    engagement_rate: comparison(0.04, 0.04),
  },
  source_breakdown: null,
  metric_methodology: {
    follower_flow: "derived:positive_snapshot_delta:v1",
    engagement_rate: "derived:ratio_from_components:v1",
    reach: "unavailable",
  },
  audience_capabilities: {
    source: "x_api",
    geo: "unavailable",
    age_gender: "unavailable",
    activity: "unavailable",
  },
  stories: null,
};

describe("X pulse dashboard", () => {
  it("renders the full X-specific cover without presenting reach as an available KPI", () => {
    render(<XPulseDashboard data={dashboard} tab="cover" />);

    expect(screen.getByRole("heading", { name: "Profile" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Posts" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Audience Signals" })).toBeInTheDocument();
    expect(screen.getAllByText("Post Impressions").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Reposts & Quotes").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Bookmarks").length).toBeGreaterThan(0);
    expect(screen.queryByText("Post Reach")).not.toBeInTheDocument();
    expect(screen.getByText(/does not receive follower geography/i)).toBeInTheDocument();

    const table = screen.getByRole("heading", { name: "All Performing Posts" }).closest("article");
    if (!table) throw new Error("Missing X performing posts table");
    expect(within(table).getByRole("columnheader", { name: "Replies" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Reposts & Quotes" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Profile Visits" })).toBeInTheDocument();
  });

  it("keeps provider-specific counters and derives publish-date chart series", () => {
    expect(xContentTotals(dashboard.content)).toEqual({
      views: 2400,
      interactions: 96,
      likes: 70,
      replies: 12,
      repostsAndQuotes: 9,
      bookmarks: 5,
      profileVisits: 18,
    });
    const series = withXContentSeries(dashboard).series;
    expect(series.find((item) => item.metric_id === "views")?.points).toEqual([
      { observed_on: "2026-08-31", value: 2400 },
    ]);
    expect(series.find((item) => item.metric_id === "profile_views")?.points).toEqual([
      { observed_on: "2026-08-31", value: 18 },
    ]);
  });
});
