import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MetricId, PlatformDashboard } from "../api";
import {
  YouTubePulseDashboard,
  youtubeContentTotals,
} from "../features/youtube/YouTubePulseDashboard";

const comparison = (value: number | null, previous: number | null = null) => ({
  value,
  previous_value: previous,
  delta_pct: value !== null && previous ? ((value - previous) / previous) * 100 : null,
});

function metric(
  metricId: MetricId,
  value: number,
  semanticType: "flow" | "ratio" | "snapshot" = "flow",
) {
  return {
    metric_id: metricId,
    value,
    previous_value: null,
    delta_pct: null,
    semantic_type: semanticType,
    unit: semanticType === "ratio" ? "ratio" as const : "count" as const,
    data_status: "available" as const,
    methodology: "provider:youtube_analytics_api",
    availability_reason: null,
  };
}

const dashboard: PlatformDashboard = {
  meta: {
    dashboard_id: "youtube",
    platform: "youtube",
    requested_brand_id: "18",
    rollup: false,
    resolved_brand_ids: ["18"],
    resolved_account_ids: [101],
    date_range: { start_on: "2026-08-01", end_on: "2026-08-31", key: "last_30_days" },
    generated_at: "2026-09-01T12:00:00Z",
    last_sync_at: "2026-09-01T11:00:00Z",
    freshness: "fresh",
    observed_days: 2,
    expected_days: 31,
    data_status: "available",
    warnings: [],
  },
  metrics: [
    metric("followers", 12_400, "snapshot"),
    metric("views", 48_000),
    metric("engaged_views", 39_000),
    metric("watch_time_minutes", 96_000),
    metric("follows", 420),
    metric("unfollows", 35),
    metric("video_likes_daily", 2_100),
    metric("video_comments_daily", 240),
    metric("video_shares_daily", 180),
    metric("playlist_additions", 95),
    metric("playlist_removals", 8),
    metric("interactions", 2_520),
    metric("engagement_rate", 0.0525, "ratio"),
  ],
  series: [
    { metric_id: "views", semantic_type: "flow", points: [{ observed_on: "2026-08-30", value: 22_000 }, { observed_on: "2026-08-31", value: 26_000 }], methodology: "provider:youtube_analytics_api" },
    { metric_id: "engaged_views", semantic_type: "flow", points: [{ observed_on: "2026-08-30", value: 18_000 }, { observed_on: "2026-08-31", value: 21_000 }], methodology: "provider:youtube_analytics_api" },
    { metric_id: "watch_time_minutes", semantic_type: "flow", points: [{ observed_on: "2026-08-30", value: 44_000 }, { observed_on: "2026-08-31", value: 52_000 }], methodology: "provider:youtube_analytics_api" },
    { metric_id: "follows", semantic_type: "flow", points: [{ observed_on: "2026-08-31", value: 420 }], methodology: "provider:youtube_analytics_api" },
    { metric_id: "unfollows", semantic_type: "flow", points: [{ observed_on: "2026-08-31", value: 35 }], methodology: "provider:youtube_analytics_api" },
    { metric_id: "video_likes_daily", semantic_type: "flow", points: [{ observed_on: "2026-08-31", value: 2_100 }], methodology: "provider:youtube_analytics_api" },
    { metric_id: "video_comments_daily", semantic_type: "flow", points: [{ observed_on: "2026-08-31", value: 240 }], methodology: "provider:youtube_analytics_api" },
    { metric_id: "video_shares_daily", semantic_type: "flow", points: [{ observed_on: "2026-08-31", value: 180 }], methodology: "provider:youtube_analytics_api" },
    { metric_id: "playlist_additions", semantic_type: "flow", points: [{ observed_on: "2026-08-31", value: 95 }], methodology: "provider:youtube_analytics_api" },
    { metric_id: "playlist_removals", semantic_type: "flow", points: [{ observed_on: "2026-08-31", value: 8 }], methodology: "provider:youtube_analytics_api" },
  ],
  breakdowns: [
    { metric_id: "views", dimension: "youtube_country", items: [{ key: "TR", value: 28_000, percentage: 58.33 }, { key: "US", value: 20_000, percentage: 41.67 }] },
    { metric_id: "views", dimension: "youtube_device_type", items: [{ key: "MOBILE", value: 32_000, percentage: 66.67 }, { key: "TV", value: 16_000, percentage: 33.33 }] },
    { metric_id: "views", dimension: "youtube_traffic_source", items: [{ key: "YT_SEARCH", value: 30_000, percentage: 62.5 }, { key: "RELATED_VIDEO", value: 18_000, percentage: 37.5 }] },
    { metric_id: "views", dimension: "youtube_subscribed_status", items: [{ key: "SUBSCRIBED", value: 16_000, percentage: 33.33 }, { key: "UNSUBSCRIBED", value: 32_000, percentage: 66.67 }] },
    { metric_id: "views", dimension: "youtube_content_type", items: [{ key: "VIDEO_ON_DEMAND", value: 30_000, percentage: 62.5 }, { key: "SHORTS", value: 18_000, percentage: 37.5 }] },
  ],
  content: [{
    account_id: 101,
    external_content_id: "video-a",
    content_type: "video",
    permalink: "https://www.youtube.com/watch?v=video-a",
    message: "Product walkthrough",
    media_url: "https://i.ytimg.com/vi/video-a/hqdefault.jpg",
    published_at: "2026-08-31T10:00:00Z",
    likes_count: 700,
    comments_count: 80,
    shares_count: null,
    interactions: 780,
    views: 20_000,
    reach: null,
    cover_url: "https://i.ytimg.com/vi/video-a/hqdefault.jpg",
    thumbnail_url: "https://i.ytimg.com/vi/video-a/hqdefault.jpg",
    cover_candidates: [],
    thumbnail_candidates: [],
    media_url_candidates: [],
    full_video_watched_rate: null,
    total_time_watched: null,
    average_time_watched: null,
    saves_count: null,
    profile_visits: null,
    clicks_count: null,
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
  community: { total_comments: 1, answered_comments: 0, unanswered_comments: 1, comment_likes: 2, data_status: "available", top_commenters: [], top_liked_comments: [] },
  top_hashtags: [],
  content_summary: { total: 1, by_type: [{ name: "Video", value: 1 }], reach_by_type: [], views_by_type: [{ name: "Video", value: 20_000 }], data_status: "partial" },
  content_metrics: {
    views: comparison(20_000, 18_000),
    reach: comparison(null),
    likes: comparison(700, 600),
    comments: comparison(80, 70),
    shares: comparison(null),
    interactions: comparison(780, 670),
    engagement_rate: comparison(0.039, 0.037),
  },
  source_breakdown: null,
  metric_methodology: { follower_flow: "provider:youtube_analytics_api", engagement_rate: "derived:ratio_from_components:v1", reach: "unavailable" },
  audience_capabilities: { source: "youtube_analytics_api", geo: "partial", age_gender: "unavailable", activity: "unavailable" },
  stories: null,
  mentions: null,
};

describe("YouTube pulse dashboard", () => {
  it("renders six-card channel, video and audience sections with YouTube-native metrics", () => {
    render(<YouTubePulseDashboard data={dashboard} tab="cover" />);

    expect(screen.getByRole("heading", { name: "Channel Overview" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Videos" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Audience & Discovery" })).toBeInTheDocument();
    expect(screen.getAllByText("Engaged Views").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Watch Time (hours)").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Content Type Performance" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Device Type" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Traffic Sources" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Audience Demographics" })).not.toBeInTheDocument();
    expect(document.querySelectorAll(".facebook-pulse-kpi")).toHaveLength(18);

    const table = screen.getByRole("heading", { name: "All Performing Videos" }).closest("article");
    if (!table) throw new Error("Missing YouTube performing videos table");
    for (const label of ["Views", "Visible Engagements", "Likes", "Comments", "Shares", "Visible Engagement Rate"]) {
      expect(within(table).getByRole("columnheader", { name: label })).toBeInTheDocument();
    }
  });

  it("derives only available video totals without inventing shares", () => {
    expect(youtubeContentTotals(dashboard.content)).toEqual({
      views: 20_000,
      likes: 700,
      comments: 80,
      interactions: 780,
      averageViews: 20_000,
      engagementRate: 0.039,
    });
    expect(dashboard.content[0]?.shares_count).toBeNull();
  });

  it("shows one honest audience state instead of unsupported empty charts", () => {
    render(<YouTubePulseDashboard data={{ ...dashboard, breakdowns: [] }} tab="audience" />);

    expect(screen.getByText("YouTube has not returned audience playback breakdowns for this channel and period yet.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Device Type" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Traffic Sources" })).not.toBeInTheDocument();
  });
});
