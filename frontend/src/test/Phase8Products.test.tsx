import { act, render, screen, within } from "@testing-library/react";
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
import { MemoryRouter } from "../routing";
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

const periodMetric = (metricId: MetricId, value: number, previousValue: number): DashboardMetric => ({
  metric_id: metricId,
  value,
  previous_value: previousValue,
  delta_pct: ((value - previousValue) / Math.abs(previousValue)) * 100,
  semantic_type: "flow",
  unit: "count",
  data_status: "available",
  methodology: "provider_flow",
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
  content_metrics: {
    views: { value: null, previous_value: null, delta_pct: null },
    reach: { value: null, previous_value: null, delta_pct: null },
    likes: { value: 0, previous_value: 0, delta_pct: null },
    comments: { value: 0, previous_value: 0, delta_pct: null },
    shares: { value: 0, previous_value: 0, delta_pct: null },
    interactions: { value: 0, previous_value: 0, delta_pct: null },
    engagement_rate: { value: null, previous_value: null, delta_pct: null },
  },
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
  link_status: "active",
  nightly_enabled: true,
  last_synced_at: null,
};

describe("Phase 8 product surfaces", () => {
  it.each(["facebook", "instagram", "tiktok"] as const)(
    "renders adjacent-period content deltas on the %s dashboard",
    (platform) => {
      const data = {
        ...baseDashboard,
        meta: { ...baseDashboard.meta, dashboard_id: platform, platform },
        metrics: [],
        content_metrics: {
          ...baseDashboard.content_metrics,
          views: { value: 150, previous_value: 100, delta_pct: 50 },
          reach: { value: 80, previous_value: 100, delta_pct: -20 },
        },
      } as PlatformDashboard;

      render(platform === "facebook"
        ? <FacebookPulseDashboard data={data} tab="content" />
        : platform === "instagram"
          ? <InstagramPulseDashboard data={data} tab="content" />
          : <TikTokPulseDashboard data={data} tab="content" />);

      expect(screen.getByText("50.0%", { selector: ".facebook-pulse-delta" })).toHaveClass("positive");
      expect(screen.getByText("20.0%", { selector: ".facebook-pulse-delta" })).toHaveClass("negative");
    },
  );

  it("keeps Facebook Content headline values while comparing the exact previous period", () => {
    const data = {
      ...baseDashboard,
      metrics: [
        {
          metric_id: "views",
          value: 8658,
          previous_value: 11202,
          delta_pct: -22.710230316,
          semantic_type: "flow",
          unit: "count",
          data_status: "available",
          methodology: "provider_flow",
          availability_reason: null,
        },
        {
          metric_id: "reach",
          value: 2060,
          previous_value: 1198,
          delta_pct: 71.953255426,
          semantic_type: "flow",
          unit: "count",
          data_status: "available",
          methodology: "provider_flow",
          availability_reason: null,
        },
      ],
      content_metrics: {
        views: { value: 6060, previous_value: 9600, delta_pct: -36.875 },
        reach: { value: null, previous_value: null, delta_pct: null },
        likes: { value: 111, previous_value: 122, delta_pct: -9.016393443 },
        comments: { value: 20, previous_value: 19, delta_pct: 5.263157895 },
        shares: { value: 10, previous_value: 12, delta_pct: -16.666666667 },
        interactions: { value: 141, previous_value: 153, delta_pct: -7.843137255 },
        engagement_rate: { value: 141 / 6060, previous_value: 153 / 9600, delta_pct: 45.991069695 },
      },
    } as PlatformDashboard;

    render(<FacebookPulseDashboard data={data} tab="content" />);

    expect(screen.getByText("8.7K", { selector: ".facebook-pulse-kpi > strong" })).toBeInTheDocument();
    expect(screen.getByText("2.1K", { selector: ".facebook-pulse-kpi > strong" })).toBeInTheDocument();
    expect(screen.getByText("1.6%", { selector: ".facebook-pulse-kpi > strong" })).toBeInTheDocument();
    for (const delta of ["22.7%", "72.0%", "9.0%", "5.3%", "16.7%", "19.2%"] as const) {
      expect(screen.getByText(delta, { selector: ".facebook-pulse-delta" })).toBeInTheDocument();
    }
  });

  it("uses TikTok period flows instead of lifetime snapshots across Cover cards", () => {
    const data = {
      ...baseDashboard,
      meta: { ...baseDashboard.meta, dashboard_id: "tiktok", platform: "tiktok" },
      metrics: [
        periodMetric("followers", 770, 677),
        periodMetric("new_followers", 77, 141),
        periodMetric("views", 23880, 33537),
        periodMetric("reach", 3955, 16387),
        periodMetric("profile_views", 686, 1123),
        periodMetric("video_likes_daily", 239, 278),
        periodMetric("video_comments_daily", 22, 20),
        periodMetric("video_shares_daily", 92, 122),
        periodMetric("interactions", 353, 394),
        tiktokMetric("video_views_total", 66913),
        tiktokMetric("video_likes_total", 797),
        tiktokMetric("video_comments_total", 66),
        tiktokMetric("video_shares_total", 323),
      ],
    } as PlatformDashboard;

    render(<TikTokPulseDashboard data={data} tab="cover" />);

    const overview = screen.getByRole("heading", { name: "Overview" }).closest("section");
    const content = screen.getByRole("heading", { name: "Content" }).closest("section");
    const audience = screen.getByRole("heading", { name: "Audience" }).closest("section");
    if (!overview || !content || !audience) throw new Error("TikTok Cover sections are missing");

    for (const value of ["770", "77", "23.9K", "4K", "353", "1.5%"] as const) {
      expect(within(overview).getByText(value, { selector: ".facebook-pulse-kpi > strong" })).toBeInTheDocument();
    }
    for (const delta of ["13.7%", "45.4%", "28.8%", "75.9%", "10.4%", "25.8%"] as const) {
      expect(within(overview).getByText(delta, { selector: ".facebook-pulse-delta" })).toBeInTheDocument();
    }

    for (const value of ["23.9K", "4K", "239", "22", "92", "1.5%"] as const) {
      expect(within(content).getByText(value, { selector: ".facebook-pulse-kpi > strong" })).toBeInTheDocument();
    }
    for (const delta of ["28.8%", "75.9%", "14.0%", "10.0%", "24.6%", "25.8%"] as const) {
      expect(within(content).getByText(delta, { selector: ".facebook-pulse-delta" })).toBeInTheDocument();
    }

    for (const value of ["770", "77", "23.9K", "4K", "686", "1.5%"] as const) {
      expect(within(audience).getByText(value, { selector: ".facebook-pulse-kpi > strong" })).toBeInTheDocument();
    }
    for (const delta of ["13.7%", "45.4%", "28.8%", "75.9%", "38.9%", "25.8%"] as const) {
      expect(within(audience).getByText(delta, { selector: ".facebook-pulse-delta" })).toBeInTheDocument();
    }

    const viewType = screen.getByRole("heading", { name: "Video View Type" }).closest("article");
    if (!viewType) throw new Error("Video View Type card is missing");
    expect(within(viewType).getByText("23.9K")).toBeInTheDocument();
    expect(screen.queryByText("66.9K")).not.toBeInTheDocument();
  });

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

  it("keeps the approved executive Social overview information architecture", async () => {
    const platformDashboard = {
      ...baseDashboard,
      meta: { ...baseDashboard.meta, data_status: "available" as const, freshness: "fresh" as const },
      metrics: [metric(1200, "available")],
      series: [{ metric_id: "followers" as const, semantic_type: "snapshot" as const, points: [{ observed_on: "2026-07-14", value: 1200 }], methodology: "provider_reported" }],
    };
    const data = {
      meta: {
        ...baseDashboard.meta,
        platform: null,
        data_status: "partial" as const,
        freshness: "fresh" as const,
        warnings: ["facebook:metric_unavailable", "instagram:metric_unavailable"],
      },
      metrics: [metric(1200, "available")],
      platforms: [platformDashboard],
      content: [],
      community: baseDashboard.community,
    } as unknown as OverviewDashboard;

    render(
      <MemoryRouter initialEntries={["/overview"]}>
        <AccumulateSocialOverview
          brandName="Hotel One"
          data={data}
          insights={[{
            insight_id: 7,
            brand_id: "hotel-1",
            status: "completed",
            date_from: "2026-07-01",
            date_to: "2026-07-14",
            summary: "Reach improved while interactions remained stable.",
            recommendations: JSON.stringify([{
              priority: 1,
              title: "Scale short-form content",
              description: "Publish more of the strongest short-form format.",
              category: "content",
            }]),
            connector_analysis: "[]",
            anomalies: "[]",
            platform_evaluations: "[]",
            model: "test-model",
            error_message: null,
            created_by_user_sub: "user-1",
            created_at: "2026-07-14T12:00:00Z",
            completed_at: "2026-07-14T12:01:00Z",
          }]}
          insightsError={false}
          insightsLoading={false}
          onRange={() => undefined}
          range="last_30_days"
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Social Media Overview" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "What Changed?" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Channel Health" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Performance Trend" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Content Snapshot" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Top Performing Content" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AI Summary" })).toBeInTheDocument();
    expect(screen.queryByText("Partial reporting coverage")).not.toBeInTheDocument();
    expect(screen.queryByText(/Facebook:Metric Unavailable/)).not.toBeInTheDocument();
    expect(screen.queryByText("Overall Organic Health")).not.toBeInTheDocument();
    expect(screen.getAllByText(/Total Audience|Total Reach|Total Impressions|Total Interactions|Avg\. Engagement/)).toHaveLength(5);
    expect(document.querySelector(".overview-mini-line")).toHaveAttribute("stroke-width", "1.25");
    expect(document.querySelector(".overview-mini-sparkline defs")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Audience" }));
    expect(document.querySelector(".overview-performance-line")).toHaveAttribute("stroke-width", "1.25");
    expect(document.querySelector(".overview-performance-line")).toHaveAttribute("data-curve", "monotone");
    expect(document.querySelectorAll(".overview-performance-area")).toHaveLength(1);
    const comingSoon = screen.getByLabelText("LinkedIn, X, YouTube Coming soon");
    expect(within(comingSoon).getByLabelText("LinkedIn logo")).toBeInTheDocument();
    expect(within(comingSoon).getByLabelText("X logo")).toBeInTheDocument();
    expect(within(comingSoon).getByLabelText("YouTube logo")).toBeInTheDocument();
    expect(within(comingSoon).getByText("Coming soon")).toBeInTheDocument();
    expect(screen.getByText("Scale short-form content")).toBeInTheDocument();
    expect(screen.queryByText("Publish more of the strongest short-form format.")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Open/ }));
    expect(screen.getByRole("dialog", { name: "AI Summary" })).toBeInTheDocument();
    expect(screen.getAllByText("Reach improved while interactions remained stable.")).toHaveLength(2);
    expect(screen.getByText("Publish more of the strongest short-form format.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Generate summary/ })).not.toBeInTheDocument();
  });

  it("rotates Channel Health one platform at a time only after three connected channels", () => {
    vi.useFakeTimers();
    const platforms = (["instagram", "facebook", "tiktok", "linkedin"] as const).map((platform, index) => ({
      ...baseDashboard,
      meta: {
        ...baseDashboard.meta,
        dashboard_id: `${platform}-dashboard`,
        platform,
        resolved_account_ids: [index + 1],
        data_status: "available" as const,
        freshness: "fresh" as const,
      },
      metrics: [metric(1200 + index, "available")],
      series: [{
        metric_id: "followers" as const,
        semantic_type: "snapshot" as const,
        points: [
          { observed_on: "2026-07-01", value: 1100 + index },
          { observed_on: "2026-07-14", value: 1200 + index },
        ],
        methodology: "provider_reported",
      }],
    }));
    const data = {
      meta: { ...baseDashboard.meta, platform: null, data_status: "available" as const },
      metrics: [metric(4800, "available")],
      platforms,
      content: [],
      community: baseDashboard.community,
    } as unknown as OverviewDashboard;

    try {
      render(
        <MemoryRouter initialEntries={["/overview"]}>
          <AccumulateSocialOverview
            brandName="Hotel One"
            data={data}
            insights={[]}
            insightsError={false}
            insightsLoading={false}
            onRange={() => undefined}
            range="last_30_days"
          />
        </MemoryRouter>,
      );
      const carousel = screen.getByLabelText("Connected channel health");
      expect(within(carousel).getByText("Instagram")).toBeInTheDocument();
      expect(within(carousel).queryByText("LinkedIn")).not.toBeInTheDocument();

      act(() => vi.advanceTimersByTime(4_500));

      expect(within(carousel).queryByText("Instagram")).not.toBeInTheDocument();
      expect(within(carousel).getByText("LinkedIn")).toBeInTheDocument();
      const comingSoon = screen.getByLabelText("X, YouTube Coming soon");
      expect(within(comingSoon).queryByLabelText("LinkedIn logo")).not.toBeInTheDocument();
      expect(within(comingSoon).getByLabelText("X logo")).toBeInTheDocument();
      expect(within(comingSoon).getByLabelText("YouTube logo")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
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
    const performingContent = screen.getByRole("heading", { name: "All Performing Content" }).closest("article");
    if (!performingContent) throw new Error("Missing All Performing Content panel");
    expect(performingContent.querySelector("tbody tr td:last-child")).toHaveTextContent("—");
    // Facebook Pages stopped reporting like source, hourly activity and
    // audience geography on 2026-02-23, joining age and gender before them.
    // Geography is offered and stays; like source, hourly activity and
    // age/gender are not offered for Facebook Pages.
    expect(screen.getByRole("heading", { name: "Top Countries" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Top Cities" })).toBeInTheDocument();
    for (const retired of [
      "Page Like Types (Organic vs Paid)",
      "Best Time to Engage",
      "Age & Gender",
    ]) {
      expect(screen.queryByRole("heading", { name: retired })).not.toBeInTheDocument();
    }
    expect(screen.getAllByRole("heading", { name: "Followers Trend" })).toHaveLength(2);
    expect(screen.getAllByText("A quiet morning by the pool.")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Open content: A quiet morning by the pool." })).toHaveAttribute(
      "href",
      "https://example.test/post-1",
    );
    const imageType = screen.getByText("Image");
    expect(imageType).toHaveClass("facebook-type-chip", "is-post");
    expect(imageType.querySelector("svg")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Content Winners by Objective" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Unanswered Comments Queue" })).not.toBeInTheDocument();
  });

  it("keeps the Instagram Cover as the combined Page, Content, Stories and Audience view", () => {
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
    expect(screen.getByRole("heading", { name: "Stories" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Instagram Stories" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Story Performance Trends" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Age & Gender" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Audience by Country" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Content Type" })).toBeInTheDocument();
    const reelType = screen.getByText("Reel");
    expect(reelType).toHaveClass("facebook-type-chip", "is-video");
    expect(reelType.querySelector("svg")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Content Winners by Objective" })).not.toBeInTheDocument();
  });

  it("uses the shared pulse structure with TikTok-specific metrics and honest video rows", () => {
    const data: PlatformDashboard = {
      ...baseDashboard,
      meta: { ...baseDashboard.meta, dashboard_id: "tiktok", platform: "tiktok", data_status: "available", freshness: "fresh" },
      metrics: [
        tiktokMetric("followers", 3890),
        periodMetric("views", 126000, 98000),
        periodMetric("interactions", 11200, 8600),
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
    expect(screen.getAllByText("Follower Growth")).toHaveLength(2);
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
    const countryMap = screen.getByRole("heading", { name: "Audience by Country" })
      .closest("article");
    const countryTable = screen.getByRole("heading", { name: "Top Countries" })
      .closest("article");
    if (!countryMap || !countryTable) throw new Error("Country surfaces are missing");
    expect(within(countryMap).getByText("Türkiye")).toBeInTheDocument();
    expect(countryMap.querySelector(".country-flag")).not.toBeInTheDocument();
    expect(within(countryTable).getByText("Türkiye")).toBeInTheDocument();
    expect(countryTable.querySelector(".country-flag")).toHaveAttribute("src", "/flags/tr.svg");
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
