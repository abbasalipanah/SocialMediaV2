import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PlatformDashboard } from "../api";
import {
  LinkedInPulseDashboard,
  linkedInContentTotals,
} from "../features/linkedin/LinkedInPulseDashboard";

const comparison = (value: number | null) => ({
  value,
  previous_value: null,
  delta_pct: null,
});

const dashboard: PlatformDashboard = {
  meta: {
    dashboard_id: "linkedin",
    platform: "linkedin",
    requested_brand_id: "18",
    rollup: false,
    resolved_brand_ids: ["18"],
    resolved_account_ids: [91],
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
    { metric_id: "followers", value: 1400, previous_value: 1375, delta_pct: 1.82, semantic_type: "snapshot", unit: "count", data_status: "available", methodology: "provider:network_sizes", availability_reason: null },
    { metric_id: "follower_gains", value: 28, previous_value: 20, delta_pct: 40, semantic_type: "flow", unit: "count", data_status: "available", methodology: "provider:follower_statistics", availability_reason: null },
    { metric_id: "views", value: 3000, previous_value: 2500, delta_pct: 20, semantic_type: "flow", unit: "count", data_status: "available", methodology: "provider:share_statistics", availability_reason: null },
    { metric_id: "reach", value: 2100, previous_value: 1900, delta_pct: 10.53, semantic_type: "flow", unit: "count", data_status: "available", methodology: "provider:share_statistics", availability_reason: null },
    { metric_id: "interactions", value: 180, previous_value: 150, delta_pct: 20, semantic_type: "flow", unit: "count", data_status: "available", methodology: "provider:share_statistics", availability_reason: null },
    { metric_id: "clicks", value: 95, previous_value: 70, delta_pct: 35.71, semantic_type: "flow", unit: "count", data_status: "available", methodology: "provider:share_statistics", availability_reason: null },
    { metric_id: "page_views", value: 420, previous_value: 390, delta_pct: 7.69, semantic_type: "flow", unit: "count", data_status: "available", methodology: "provider:page_statistics", availability_reason: null },
    { metric_id: "engagement_rate", value: 0.06, previous_value: 0.06, delta_pct: 0, semantic_type: "ratio", unit: "ratio", data_status: "available", methodology: "derived:ratio_from_components:v1", availability_reason: null },
  ],
  series: [
    { metric_id: "followers", semantic_type: "snapshot", points: [{ observed_on: "2026-08-30", value: 1375 }, { observed_on: "2026-08-31", value: 1400 }], methodology: "provider:network_sizes" },
    { metric_id: "follower_gains", semantic_type: "flow", points: [{ observed_on: "2026-08-31", value: 28 }], methodology: "provider:follower_statistics" },
    { metric_id: "views", semantic_type: "flow", points: [{ observed_on: "2026-08-31", value: 3000 }], methodology: "provider:share_statistics" },
    { metric_id: "reach", semantic_type: "flow", points: [{ observed_on: "2026-08-31", value: 2100 }], methodology: "provider:share_statistics" },
    { metric_id: "interactions", semantic_type: "flow", points: [{ observed_on: "2026-08-31", value: 180 }], methodology: "provider:share_statistics" },
    { metric_id: "clicks", semantic_type: "flow", points: [{ observed_on: "2026-08-31", value: 95 }], methodology: "provider:share_statistics" },
    { metric_id: "page_views", semantic_type: "flow", points: [{ observed_on: "2026-08-31", value: 420 }], methodology: "provider:page_statistics" },
  ],
  breakdowns: [
    { metric_id: "followers", dimension: "staff_count", items: [{ key: "SIZE_11_TO_50", value: 80, percentage: 0.8 }] },
    { metric_id: "followers", dimension: "association_type", items: [{ key: "EMPLOYEE", value: 20, percentage: 0.2 }] },
  ],
  content: [{
    account_id: 91,
    external_content_id: "urn:li:share:123",
    content_type: "link",
    permalink: "https://www.linkedin.com/feed/update/urn:li:share:123/",
    message: "Product update",
    media_url: "",
    published_at: "2026-08-31T10:00:00Z",
    likes_count: 50,
    comments_count: 10,
    shares_count: 5,
    interactions: 100,
    views: 2000,
    reach: 1500,
    cover_url: null,
    thumbnail_url: null,
    cover_candidates: [],
    thumbnail_candidates: [],
    media_url_candidates: [],
    full_video_watched_rate: null,
    total_time_watched: null,
    average_time_watched: null,
    saves_count: null,
    profile_visits: null,
    clicks_count: 35,
    reposts_count: null,
    quotes_count: null,
    link_clicks: null,
    profile_clicks: null,
    video_views_count: null,
    video_playback_0_count: null,
    video_playback_25_count: null,
    video_playback_50_count: null,
    video_playback_75_count: null,
    video_playback_100_count: null,
    completion_rate: null,
    data_status: "partial",
  }],
  community: { total_comments: 0, answered_comments: 0, unanswered_comments: 0, comment_likes: 0, data_status: "unavailable", top_commenters: [], top_liked_comments: [] },
  top_hashtags: [],
  content_summary: { total: 1, by_type: [{ name: "Link", value: 1 }], reach_by_type: [{ name: "Link", value: 1500 }], views_by_type: [{ name: "Link", value: 2000 }], data_status: "partial" },
  content_metrics: {
    views: comparison(2000),
    reach: comparison(1500),
    likes: comparison(50),
    comments: comparison(10),
    shares: comparison(5),
    interactions: comparison(100),
    engagement_rate: comparison(0.05),
  },
  source_breakdown: null,
  metric_methodology: { follower_flow: "provider:follower_statistics", engagement_rate: "derived:ratio_from_components:v1", reach: "provider:share_statistics" },
  audience_capabilities: { source: "linkedin_api", geo: "unavailable", age_gender: "unavailable", activity: "unavailable" },
  stories: null,
  mentions: null,
};

describe("LinkedIn pulse dashboard", () => {
  it("renders Company Page, post and supported follower analytics without fake demographics", () => {
    render(<LinkedInPulseDashboard data={dashboard} tab="cover" />);

    expect(screen.getByRole("heading", { name: "Company Page" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Posts" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Follower Audience" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Followers by Company Size" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Followers by Association" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Audience Demographics" })).not.toBeInTheDocument();
    expect(document.querySelectorAll(".facebook-pulse-kpi")).toHaveLength(18);

    const table = screen.getByRole("heading", { name: "All Performing Posts" }).closest("article");
    if (!table) throw new Error("Missing LinkedIn performing posts table");
    for (const label of ["Impressions", "Unique Impressions", "Engagements", "Likes", "Comments", "Shares", "Clicks", "Engagement Rate"]) {
      expect(within(table).getByRole("columnheader", { name: label })).toBeInTheDocument();
    }
  });

  it("keeps LinkedIn post clicks separate from X link clicks", () => {
    expect(linkedInContentTotals(dashboard.content)).toEqual({
      impressions: 2000,
      uniqueImpressions: 1500,
      engagements: 100,
      clicks: 35,
      likes: 50,
      comments: 10,
      shares: 5,
    });
  });
});
