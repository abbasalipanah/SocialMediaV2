import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DashboardMetric, MetricId, OverviewDashboard, PlatformDashboard, ReportingAccount } from "../api";
import { MetricBand } from "../features/dashboard/DashboardCards";
import { platformTabs } from "../features/dashboard/catalog";
import { FacebookPulseDashboard } from "../features/facebook/FacebookPulseDashboard";
import { InstagramPulseDashboard } from "../features/instagram/InstagramPulseDashboard";
import { AccumulateSocialOverview } from "../features/overview/AccumulateSocialOverview";
import { AccountsTable } from "../features/settings/SettingsTables";
import { TikTokPulseDashboard } from "../features/tiktok/TikTokPulseDashboard";
import { Dialog } from "../ui";

const metric = (value: number | null, status: "available" | "partial" | "unavailable"): DashboardMetric => ({
  metric_id: "followers",
  value,
  previous_value: null,
  delta_pct: null,
  semantic_type: "snapshot",
  unit: "count",
  data_status: status,
  methodology: "provider_reported",
  availability_reason: status === "unavailable" ? "fixture_unavailable" : null,
});

const tiktokMetric = (metricId: MetricId, value: number, unit: "count" | "ratio" = "count"): DashboardMetric => ({
  metric_id: metricId,
  value,
  previous_value: null,
  delta_pct: null,
  semantic_type: unit === "ratio" ? "ratio" : metricId === "followers" ? "snapshot" : "cumulative",
  unit,
  data_status: "available",
  methodology: "provider_reported",
  availability_reason: null,
});

const baseDashboard = {
  meta: {
    dashboard_id: "test",
    platform: "facebook" as const,
    requested_brand_id: "hotel-1",
    rollup: false,
    resolved_brand_ids: ["hotel-1"],
    resolved_account_ids: [1],
    date_range: { start_on: "2026-07-01", end_on: "2026-07-14", key: "last_30_days" },
    generated_at: "2026-07-14T12:00:00Z",
    last_sync_at: null,
    freshness: "never_synced" as const,
    observed_days: 0,
    expected_days: 30,
    data_status: "unavailable" as const,
    warnings: [],
  },
  series: [],
  breakdowns: [],
  content: [],
  community: {
    total_comments: 0,
    answered_comments: 0,
    unanswered_comments: 0,
    comment_likes: 0,
    data_status: "unavailable" as const,
    top_commenters: [],
    top_liked_comments: [],
  },
  top_hashtags: [],
  content_summary: { total: 0, by_type: [], reach_by_type: [], views_by_type: [], data_status: "unavailable" as const },
  source_breakdown: null,
  metric_methodology: { follower_flow: "unavailable", engagement_rate: "unavailable", reach: "unavailable" },
  audience_capabilities: { source: null, geo: "unavailable" as const, age_gender: "unavailable" as const, activity: "unavailable" as const },
  stories: null,
};

const account: ReportingAccount = {
  account_id: 17,
  brand_id: "hotel-1",
  platform: "facebook",
  external_id: "page-17",
  display_name: "Coastal Facebook",
  status: "active",
  connection_state: "connected",
  health_status: "healthy",
  backfill_status: "complete",
  nightly_enabled: true,
  last_synced_at: null,
};

describe("Phase 8 product surfaces", () => {
  it("keeps unavailable metrics honest instead of rendering a synthetic zero", () => {
    render(<MetricBand data={{ ...baseDashboard, metrics: [metric(null, "unavailable")] }} scope="facebook" />);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
    expect(screen.getByText("Comparison unavailable")).toBeInTheDocument();
  });

  it("keeps the current Social Media tab structure for Instagram and TikTok", () => {
    expect(platformTabs("instagram", true).map((tab) => tab.label)).toEqual([
      "Cover", "Page", "Content", "Stories", "Audience",
    ]);
    expect(platformTabs("tiktok", false).map((tab) => tab.label)).toEqual([
      "Cover", "Account", "Content", "Audience",
    ]);
    expect(platformTabs("tiktok", true).map((tab) => tab.label)).toEqual([
      "Cover", "Account", "Content", "Audience",
    ]);
  });

  it("keeps the active Accumulate Social overview information architecture", () => {
    const platformDashboard = {
      ...baseDashboard,
      meta: { ...baseDashboard.meta, data_status: "available" as const, freshness: "fresh" as const },
      metrics: [metric(1200, "available")],
      series: [{ metric_id: "followers" as const, semantic_type: "snapshot" as const, points: [{ observed_on: "2026-07-14", value: 1200 }], methodology: "provider_reported" }],
    };
    const data = {
      meta: { ...baseDashboard.meta, platform: null, data_status: "available" as const, freshness: "fresh" as const },
      metrics: [metric(1200, "available")],
      platforms: [platformDashboard],
      content: [],
      community: baseDashboard.community,
    } as unknown as OverviewDashboard;

    render(
      <AccumulateSocialOverview
        brandName="Hotel One"
        data={data}
        insights={[]}
        insightsError={false}
        insightsLoading={false}
        onRange={() => undefined}
        range="last_30_days"
      />,
    );

    expect(screen.getByRole("heading", { name: "Social Media Overview" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Audience Growth" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Cross-Channel" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Content Type" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AI Insights" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Action Breakdown" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Top Performing Posts" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Platform Breakdown" })).toBeInTheDocument();
  });

  it("keeps the Accumulate Facebook Cover as the combined Page, Content and Audience view", () => {
    const data = {
      ...baseDashboard,
      meta: { ...baseDashboard.meta, data_status: "available" as const, freshness: "fresh" as const },
      metrics: [metric(1200, "available")],
      series: [{
        metric_id: "followers" as const,
        semantic_type: "snapshot" as const,
        points: [{ observed_on: "2026-07-14", value: 1200 }],
        methodology: "provider_reported",
      }],
      content: [{
        account_id: 1,
        external_content_id: "post-1",
        content_type: "image",
        permalink: "https://example.test/post-1",
        message: "A quiet morning by the pool.",
        media_url: "",
        published_at: "2026-07-14T12:00:00Z",
        likes_count: 18,
        comments_count: 4,
        shares_count: 2,
        interactions: 24,
        views: null,
        reach: null,
        cover_url: null,
        thumbnail_url: null,
        cover_candidates: [],
        thumbnail_candidates: [],
        media_url_candidates: [],
        full_video_watched_rate: null,
        total_time_watched: null,
        average_time_watched: null,
        data_status: "partial" as const,
      }],
    } as unknown as PlatformDashboard;

    render(<FacebookPulseDashboard data={data} tab="cover" />);

    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Content" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Audience" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Performance Trends" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "All Performing Content" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Top Countries" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Page Like Types (Organic vs Paid)" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Age & Gender" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "Followers Trend" })).toHaveLength(2);
    expect(screen.getAllByText("A quiet morning by the pool.")).toHaveLength(1);
    expect(screen.queryByRole("heading", { name: "Content Winners by Objective" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Unanswered Comments Queue" })).not.toBeInTheDocument();
  });

  it("keeps the Accumulate Instagram Cover as the combined Page, Content and Audience view", () => {
    const data = {
      ...baseDashboard,
      meta: {
        ...baseDashboard.meta,
        platform: "instagram" as const,
        data_status: "available" as const,
        freshness: "fresh" as const,
      },
      metrics: [metric(8560, "available")],
      series: [{
        metric_id: "followers" as const,
        semantic_type: "snapshot" as const,
        points: [{ observed_on: "2026-07-14", value: 8560 }],
        methodology: "provider_reported",
      }],
      content: [{
        account_id: 21,
        external_content_id: "reel-1",
        content_type: "reel",
        permalink: "https://example.test/reel-1",
        message: "Sunset from the terrace.",
        media_url: "",
        published_at: "2026-07-14T12:00:00Z",
        likes_count: 92,
        comments_count: 6,
        shares_count: 11,
        interactions: 109,
        views: null,
        reach: null,
        cover_url: null,
        thumbnail_url: null,
        cover_candidates: [],
        thumbnail_candidates: [],
        media_url_candidates: [],
        full_video_watched_rate: null,
        total_time_watched: null,
        average_time_watched: null,
        data_status: "partial" as const,
      }],
    } as unknown as PlatformDashboard;

    render(<InstagramPulseDashboard data={data} tab="cover" />);

    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Content" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Audience" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Stories" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Story Performance Trends" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Age & Gender" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Audience by Country" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Content Type" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Content Winners by Objective" })).not.toBeInTheDocument();
  });

  it("uses the shared pulse structure with TikTok-specific metrics and honest video rows", () => {
    const data: PlatformDashboard = {
      ...baseDashboard,
      meta: { ...baseDashboard.meta, dashboard_id: "tiktok", platform: "tiktok", data_status: "available", freshness: "fresh" },
      metrics: [
        tiktokMetric("followers", 3890),
        tiktokMetric("video_views_total", 126000),
        tiktokMetric("video_likes_total", 9400),
        tiktokMetric("video_comments_total", 620),
        tiktokMetric("video_shares_total", 1180),
        tiktokMetric("video_engagements_total", 11200),
        tiktokMetric("video_engagement_rate", 0.089, "ratio"),
      ],
      series: [
        { metric_id: "followers", semantic_type: "snapshot", points: [{ observed_on: "2026-06-15", value: 3400 }, { observed_on: "2026-07-14", value: 3890 }], methodology: "provider_reported" },
        { metric_id: "video_views_total", semantic_type: "cumulative", points: [{ observed_on: "2026-06-15", value: 98000 }, { observed_on: "2026-07-14", value: 126000 }], methodology: "provider_reported" },
        { metric_id: "video_engagements_total", semantic_type: "cumulative", points: [{ observed_on: "2026-06-15", value: 8600 }, { observed_on: "2026-07-14", value: 11200 }], methodology: "derived:sum_components:v1:same_sample" },
      ],
      breakdowns: [{ metric_id: "followers", dimension: "country", items: [{ key: "tr", value: 2100, percentage: 54 }] }],
      content: [{
        account_id: 31,
        external_content_id: "video-1",
        content_type: "video",
        permalink: "https://example.test/video-1",
        message: "A day at the resort.",
        media_url: "",
        published_at: "2026-07-13T12:00:00Z",
        likes_count: 2240,
        comments_count: 143,
        shares_count: 305,
        interactions: 2688,
        views: null,
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
      }],
    };

    const { rerender } = render(<TikTokPulseDashboard data={data} tab="cover" />);
    expect(screen.getByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Content" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Audience" })).toBeInTheDocument();
    expect(screen.getAllByText("Engagement Rate").length).toBeGreaterThan(0);
    expect(screen.getAllByText("8.9%").length).toBeGreaterThan(0);
    expect(screen.queryByText("Follower Growth")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Performance Trends" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Video View Type" })).toBeInTheDocument();

    rerender(<TikTokPulseDashboard data={data} tab="content" />);
    expect(screen.getByRole("heading", { name: "All Performing Content" })).toBeInTheDocument();
    expect(screen.getAllByText("A day at the resort.").length).toBe(1);
    expect(screen.queryByRole("heading", { name: "Content Winners by Objective" })).not.toBeInTheDocument();

    rerender(<TikTokPulseDashboard data={data} tab="audience" />);
    expect(screen.getByRole("heading", { name: "Age & Gender" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Audience by Country" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Best Time to Engage" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Top Countries" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Age Groups" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Most Active Commenters" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Most Liked Comments" })).toBeInTheDocument();
    expect(screen.getByText("No heatmap data in selected range.")).toBeInTheDocument();
  });

  it("filters the table and leaves manual sync disabled when backend mutation is unavailable", async () => {
    const user = userEvent.setup();
    render(<AccountsTable items={[account]} mutationAvailable={false} navigation={null} />);
    expect(screen.getByText("Coastal Facebook")).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("Search by name or ID"), "missing");
    expect(screen.getByText("No matching records.")).toBeInTheDocument();
    await user.clear(screen.getByPlaceholderText("Search by name or ID"));
    await user.click(screen.getByRole("button", { name: "Review Coastal Facebook" }));
    expect(screen.getByRole("dialog", { name: "Coastal Facebook" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sync now/ })).toBeDisabled();
  });

  it("traps an accessible dialog, closes on Escape and returns focus", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { rerender } = render(<><button type="button">Launch setup</button><Dialog onClose={onClose} open={false} title="Setup"><button type="button">First action</button></Dialog></>);
    screen.getByRole("button", { name: "Launch setup" }).focus();
    rerender(<><button type="button">Launch setup</button><Dialog onClose={onClose} open title="Setup"><button type="button">First action</button><button type="button">Last action</button></Dialog></>);
    expect(await screen.findByRole("dialog", { name: "Setup" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
    rerender(<><button type="button">Launch setup</button><Dialog onClose={onClose} open={false} title="Setup"><button type="button">First action</button></Dialog></>);
    expect(screen.getByRole("button", { name: "Launch setup" })).toHaveFocus();
  });
});
