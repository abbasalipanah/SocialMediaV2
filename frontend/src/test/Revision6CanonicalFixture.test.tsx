import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  DashboardMetric,
  DashboardSeries,
  MetricId,
  Platform,
  PlatformDashboard,
} from "../api";
import { platformDashboardSchema } from "../api";
import { platformTabs } from "../features/dashboard/catalog";
import { FacebookPulseDashboard } from "../features/facebook/FacebookPulseDashboard";
import { InstagramPulseDashboard } from "../features/instagram/InstagramPulseDashboard";
import { TikTokPulseDashboard } from "../features/tiktok/TikTokPulseDashboard";

type SourceKpi = {
  key: string;
  unit: "count" | "percent";
  value: number;
  previous: number;
  delta_pct: number | null;
};

type SourcePayload = {
  platform: Platform;
  brand_id: number;
  generated_at: string;
  window: { since: string; until: string; days: number };
  kpis: SourceKpi[];
  trend: {
    labels: string[];
    series: Array<{ key: string; points: number[] }>;
  };
  top_content: Array<{
    content_id: string;
    caption: string;
    permalink: string;
    media_url: string;
    cover_url: string | null;
    created_time: string | null;
    likes: number;
    comments: number;
    shares: number;
    views?: number;
    reach?: number;
    full_video_watched_rate?: number;
    total_time_watched?: number;
    average_time_watched?: number;
  }>;
  top_hashtags: Array<{ name: string; count: number }>;
  content_summary: {
    total: number;
    by_type: Array<{ name: string; value: number }>;
    reach_by_type: Array<{ name: string; value: number }>;
    views_by_type: Array<{ name: string; value: number }>;
  };
  source_breakdown: {
    organic_only: boolean;
    paid_available: boolean;
    views?: { organic: number; paid: number };
    reach?: { organic: number; paid: number };
  } | null;
  metric_methodology: {
    follower_flow: string;
    engagement_rate: string;
    reach: string;
  } | null;
  audience: Array<{
    key: string;
    items: Array<{ name: string; value: number; pct: number }>;
  }>;
  audience_capabilities?: {
    source: string;
    geo: "available" | "pending";
    age_gender: "provider_unavailable";
    activity: "provider_unavailable";
  };
  stories?: {
    summary: { count: number; views: number; reach: number; interactions: number; replies: number; completion_rate: number };
    previous_summary: { count: number; views: number; reach: number; interactions: number; replies: number; completion_rate: number };
    trend: { labels: string[]; views: number[]; reach: number[] };
    navigation: { taps_forward: number; taps_back: number; swipe_forward: number; exits: number };
    actions: { replies: number; shares: number; profile_visits: number; follows: number };
    items: Array<{
      content_id: string;
      title: string;
      cover_url: string;
      permalink: string;
      created_time: string | null;
      views: number;
      reach: number;
      interactions: number;
      replies: number;
      shares: number;
      profile_visits: number;
      follows: number;
      taps_forward: number;
      taps_back: number;
      swipe_forward: number;
      exits: number;
      navigation: number;
      completion_rate: number;
    }>;
  };
};

type OracleCase = {
  id: string;
  platform: Platform;
  patch: Record<string, unknown>;
  expected_tabs?: string[];
  expected_cover_excludes?: string[];
};

type OracleFixture = {
  fixture_id: string;
  consumers: Array<{ id: string }>;
  base_payload: SourcePayload;
  cases: OracleCase[];
};

const fixture = JSON.parse(readFileSync(
  resolve(process.cwd(), "../docs/revision6/r1/canonical_dashboard_fixture.json"),
  "utf8",
)) as OracleFixture;

function merge<T>(base: T, patch: unknown): T {
  if (!patch || typeof patch !== "object" || Array.isArray(patch)) return patch as T;
  const result = { ...(base as Record<string, unknown>) };
  for (const [key, value] of Object.entries(patch)) {
    result[key] = value && typeof value === "object" && !Array.isArray(value)
      ? merge(result[key], value)
      : value;
  }
  return result as T;
}

function materialize(id: string): SourcePayload {
  const selected = fixture.cases.find((item) => item.id === id);
  if (!selected) throw new Error(`Missing canonical fixture case: ${id}`);
  return merge(fixture.base_payload, selected.patch);
}

function metricId(platform: Platform, key: string): MetricId | null {
  const common: Partial<Record<string, MetricId>> = {
    followers: "followers",
    new_followers: "new_followers",
    follows: "follows",
    unfollows: "unfollows",
    followers_net: "followers_net",
    reach: "reach",
    profile_views: "profile_views",
  };
  if (common[key]) return common[key] ?? null;
  if (platform === "tiktok") {
    return ({
      views: "video_views_total",
      likes: "video_likes_total",
      comments: "video_comments_total",
      shares: "video_shares_total",
      engagement_rate: "video_engagement_rate",
    } as Partial<Record<string, MetricId>>)[key] ?? null;
  }
  return ({
    views: "views",
    likes: "reactions",
    engagement_rate: "engagement_rate",
  } as Partial<Record<string, MetricId>>)[key] ?? null;
}

function adapt(payload: SourcePayload): PlatformDashboard {
  const metrics = payload.kpis.flatMap((item): DashboardMetric[] => {
    const id = metricId(payload.platform, item.key);
    if (!id) return [];
    const ratio = item.unit === "percent";
    return [{
      metric_id: id,
      value: ratio ? item.value / 100 : item.value,
      previous_value: ratio ? item.previous / 100 : item.previous,
      delta_pct: item.delta_pct,
      semantic_type: ratio ? "ratio" : item.key === "followers" ? "snapshot" : "flow",
      unit: ratio ? "ratio" : "count",
      data_status: "available",
      methodology: "provider_reported",
      availability_reason: null,
    }];
  });
  const interactions = payload.kpis
    .filter((item) => ["likes", "comments", "shares"].includes(item.key))
    .reduce((sum, item) => sum + item.value, 0);
  const previousInteractions = payload.kpis
    .filter((item) => ["likes", "comments", "shares"].includes(item.key))
    .reduce((sum, item) => sum + item.previous, 0);
  if (interactions > 0) {
    metrics.push({
      metric_id: payload.platform === "tiktok" ? "video_engagements_total" : "interactions",
      value: interactions,
      previous_value: previousInteractions,
      delta_pct: previousInteractions > 0 ? ((interactions - previousInteractions) / previousInteractions) * 100 : null,
      semantic_type: "flow",
      unit: "count",
      data_status: "available",
      methodology: "derived:sum_components:v1:selected_period",
      availability_reason: null,
    });
  }
  const series = payload.trend.series.flatMap((item): DashboardSeries[] => {
    const id = metricId(payload.platform, item.key);
    if (!id) return [];
    return [{
      metric_id: id,
      semantic_type: item.key === "followers" ? "snapshot" : "flow",
      points: payload.trend.labels.map((observed_on, index) => ({
        observed_on,
        value: item.points[index] ?? 0,
      })),
      methodology: "provider_reported",
    }];
  });
  return {
    meta: {
      dashboard_id: payload.platform,
      platform: payload.platform,
      requested_brand_id: String(payload.brand_id),
      rollup: false,
      resolved_brand_ids: [String(payload.brand_id)],
      resolved_account_ids: [1],
      date_range: {
        start_on: payload.window.since,
        end_on: payload.window.until,
        key: "last_30_days",
      },
      generated_at: payload.generated_at,
      last_sync_at: payload.generated_at,
      freshness: "fresh",
      observed_days: payload.window.days,
      expected_days: payload.window.days,
      data_status: "available",
      warnings: [],
    },
    metrics,
    series,
    breakdowns: payload.audience.map((row) => ({
      metric_id: "followers",
      dimension: row.key,
      items: row.items.map((item) => ({
        key: item.name,
        value: item.value,
        percentage: item.pct,
      })),
    })),
    content: payload.top_content.map((item) => ({
      account_id: 1,
      external_content_id: item.content_id,
      content_type: payload.platform === "tiktok" ? "video" : "image",
      permalink: item.permalink,
      message: item.caption,
      media_url: item.media_url || item.cover_url || "",
      published_at: item.created_time,
      likes_count: item.likes,
      comments_count: item.comments,
      shares_count: item.shares,
      interactions: item.likes + item.comments + item.shares,
      views: item.views ?? null,
      reach: item.reach ?? null,
      cover_url: item.cover_url,
      thumbnail_url: null,
      cover_candidates: item.cover_url ? [item.cover_url] : [],
      thumbnail_candidates: [],
      media_url_candidates: item.media_url ? [item.media_url] : [],
      full_video_watched_rate: item.full_video_watched_rate ?? null,
      total_time_watched: item.total_time_watched ?? null,
      average_time_watched: item.average_time_watched ?? null,
      data_status: item.views === undefined || item.reach === undefined ? "partial" : "available",
    })),
    community: {
      total_comments: 0,
      answered_comments: 0,
      unanswered_comments: 0,
      comment_likes: 0,
      data_status: "unavailable",
      top_commenters: [],
      top_liked_comments: [],
    },
    top_hashtags: payload.top_hashtags,
    content_summary: { ...payload.content_summary, data_status: "available" },
    source_breakdown: payload.source_breakdown ? {
      organic_only: payload.source_breakdown.organic_only,
      paid_available: payload.source_breakdown.paid_available,
      views: payload.source_breakdown.views ? { ...payload.source_breakdown.views, data_status: "available" } : null,
      reach: payload.source_breakdown.reach ? { ...payload.source_breakdown.reach, data_status: "available" } : null,
      data_status: "available",
    } : null,
    metric_methodology: payload.metric_methodology ?? { follower_flow: "unavailable", engagement_rate: "unavailable", reach: "unavailable" },
    audience_capabilities: payload.audience_capabilities ?? {
      source: payload.platform === "tiktok" ? "tiktok_display_api" : "meta_graph_api_v23",
      geo: "available",
      age_gender: "available",
      activity: "available",
    },
    stories: payload.stories ? {
      summary: { ...payload.stories.summary, data_status: "available" },
      previous_summary: { ...payload.stories.previous_summary, data_status: "available" },
      trend: { ...payload.stories.trend, data_status: "available" },
      navigation: { ...payload.stories.navigation, data_status: "available" },
      actions: { ...payload.stories.actions, sticker_taps: null, saves: null, data_status: "available" },
      items: payload.stories.items.map((item) => ({ ...item, sticker_taps: null, saves: null, data_status: "available" })),
      data_status: "available",
    } : null,
  };
}

describe("Revision 6 shared canonical fixture", () => {
  it("uses the R1 oracle as the V2 tab contract", () => {
    expect(fixture.fixture_id).toBe("socialmedia-revision6-r1-dashboard-oracle");
    expect(fixture.consumers.map((item) => item.id)).toContain("v2_render_test");
    for (const id of ["facebook_full", "instagram_full_with_stories", "tiktok_full"]) {
      const selected = fixture.cases.find((item) => item.id === id);
      if (!selected?.expected_tabs) throw new Error(`Missing expected tabs: ${id}`);
      expect(platformTabs(selected.platform, false).map((tab) => tab.label)).toEqual(selected.expected_tabs);
    }
  });

  it("keeps the R1 critical Cover and provider-availability contracts", () => {
    const facebook = adapt(materialize("facebook_full"));
    const { rerender } = render(<FacebookPulseDashboard data={facebook} tab="cover" />);
    expect(
      screen.queryByRole("heading", { name: "Page Like Types (Organic vs Paid)" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Age & Gender" })).not.toBeInTheDocument();

    const instagramCase = fixture.cases.find((item) => item.id === "instagram_full_with_stories");
    expect(instagramCase?.expected_cover_excludes).toContain("stories");
    rerender(<InstagramPulseDashboard data={adapt(materialize("instagram_full_with_stories"))} tab="cover" />);
    // The user-approved post-R10 override supersedes the historical R1 exclusion.
    expect(screen.getByRole("heading", { name: "Stories" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Evolution" })).toBeInTheDocument();

    rerender(<TikTokPulseDashboard data={adapt(materialize("partial_metrics"))} tab="account" />);
    expect(screen.getByText("Follower Growth")).toBeInTheDocument();
  });

  it("validates and renders the structured R1 Stories contract", () => {
    const data = adapt(materialize("instagram_full_with_stories"));
    expect(platformDashboardSchema.parse(data).stories?.data_status).toBe("available");
    const { stories: _missingStories, ...legacyShape } = data;
    expect(_missingStories).not.toBeNull();
    expect(platformDashboardSchema.safeParse(legacyShape).success).toBe(false);

    render(<InstagramPulseDashboard data={data} tab="stories" />);
    expect(screen.getByRole("heading", { name: "Latest Story" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Story gallery" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Story Live Status" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Evolution" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Story Health" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Behaviour" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "History" })).toBeInTheDocument();
    expect(screen.getAllByText("446").length).toBeGreaterThan(0);
    expect(screen.queryByText(/vs previous story/i)).not.toBeInTheDocument();

    const featureLayout = document.querySelector(".instagram-story-feature-layout");
    const gallery = document.querySelector(".instagram-story-gallery");
    if (!featureLayout || !gallery) throw new Error("Missing Stories hero layout");
    expect(gallery.parentElement).toBe(featureLayout);

    const selectedActions = document.querySelector(".instagram-story-selected-actions");
    const periodActions = document.querySelector(".instagram-story-behaviour");
    if (!selectedActions || !periodActions) throw new Error("Missing R11 Story action panels");
    expect(selectedActions).toHaveTextContent("Replies2Shares4Profile Visits8Follows1");
    expect(periodActions).toHaveTextContent("Period Action TotalsReplies5Shares9Profile Visits16Follows3");
    expect(within(selectedActions as HTMLElement).getAllByText("Not provided")).toHaveLength(2);
    expect(within(periodActions as HTMLElement).getAllByText("Not provided")).toHaveLength(2);

    const navigationChart = screen.getByRole("img", { name: "Story Navigation Split chart" });
    expect(within(navigationChart).getAllByRole("button")).toHaveLength(4);
    expect(document.querySelector(".instagram-story-navigation-bar")).not.toBeInTheDocument();
  });

  it("locks the R11 three-series follower-flow contract for every platform", () => {
    const cases = [
      ["facebook", <FacebookPulseDashboard data={adapt(materialize("facebook_full"))} tab="page" />],
      ["instagram", <InstagramPulseDashboard data={adapt(materialize("instagram_full_with_stories"))} tab="page" />],
      ["tiktok", <TikTokPulseDashboard data={adapt(materialize("tiktok_full"))} tab="account" />],
    ] as const;

    for (const [platform, surface] of cases) {
      const { unmount } = render(surface);
      const panel = screen.getByRole("heading", { name: "New Followers Trend" }).closest("article");
      if (!panel) throw new Error(`Missing follower-flow panel: ${platform}`);
      expect(within(panel).getByRole("img", {
        name: "New Followers Trend: Follows, Unfollows, Net",
      })).toBeInTheDocument();
      unmount();
    }
  });

  it("keeps exactly six KPI cards in every platform section", () => {
    const surfaces = [
      <FacebookPulseDashboard data={adapt(materialize("facebook_full"))} tab="page" />,
      <FacebookPulseDashboard data={adapt(materialize("facebook_full"))} tab="content" />,
      <FacebookPulseDashboard data={adapt(materialize("facebook_full"))} tab="audience" />,
      <InstagramPulseDashboard data={adapt(materialize("instagram_full_with_stories"))} tab="page" />,
      <InstagramPulseDashboard data={adapt(materialize("instagram_full_with_stories"))} tab="content" />,
      <InstagramPulseDashboard data={adapt(materialize("instagram_full_with_stories"))} tab="audience" />,
      <TikTokPulseDashboard data={adapt(materialize("tiktok_full"))} tab="account" />,
      <TikTokPulseDashboard data={adapt(materialize("tiktok_full"))} tab="content" />,
      <TikTokPulseDashboard data={adapt(materialize("tiktok_full"))} tab="audience" />,
    ];

    for (const surface of surfaces) {
      const { container, unmount } = render(surface);
      expect(container.querySelectorAll(".facebook-pulse-kpi")).toHaveLength(6);
      expect(screen.queryByText("Frequency")).not.toBeInTheDocument();
      unmount();
    }
  });

  it("renders every R1 card heading in canonical focused-tab order", () => {
    const facebook = adapt(materialize("facebook_full"));
    const instagram = adapt(materialize("instagram_full_with_stories"));
    const tiktok = adapt(materialize("tiktok_full"));
    const { container, rerender } = render(<FacebookPulseDashboard data={facebook} tab="page" />);
    const headings = () => [...container.querySelectorAll("h3")].map((item) => item.textContent);

    expect(headings()).toEqual([
      "Followers Trend", "New Followers Trend", "Performance Trends", "Page View Type",
      "Views Source Trend", "Reach Distribution", "Reach Source Trend",
    ]);

    rerender(<FacebookPulseDashboard data={facebook} tab="content" />);
    expect(headings()).toEqual([
      "Content Type", "Views & Reach Trend", "Interaction Trend", "Engagement Split",
      "Content Type Views", "Comment Sentiment", "Top Hashtags", "All Performing Content",
    ]);
    const contentTable = screen.getByRole("heading", { name: "All Performing Content" }).closest("article");
    if (!contentTable) throw new Error("Missing All Performing Content panel");
    expect(within(contentTable).getAllByRole("columnheader").map((item) => item.textContent)).toEqual([
      "#", "Cover", "Caption", "Date", "Type", "Post Views", "Interactions", "Likes", "Comments", "Shares", "Engagement",
    ]);
    expect(within(contentTable).getByRole("button", { name: "Sort by Date" }).closest("th")).toHaveAttribute("aria-sort", "descending");
    expect(within(contentTable).getAllByText("Image")).toHaveLength(2);
    within(contentTable).getAllByText("Image").forEach((item) => {
      expect(item).toHaveClass("facebook-type-chip", "is-post");
      expect(item.querySelector("svg")).toBeInTheDocument();
    });
    expect(within(contentTable).getByRole("link", { name: "Open content: Canonical summer story #travel" })).toHaveAttribute(
      "href",
      "https://example.invalid/content/fixture-video-1",
    );
    expect(within(contentTable).getByRole("link", { name: "Open cover: Canonical summer story #travel" })).toHaveAttribute(
      "href",
      "https://example.invalid/content/fixture-video-1",
    );
    expect(within(contentTable).queryByRole("link", { name: "Open content: Canonical evening #hotel" })).not.toBeInTheDocument();
    expect(within(contentTable).getByText("12.3%")).toHaveClass("facebook-engagement-score");
    expect(within(contentTable).getByText("11.2%")).toHaveClass("facebook-engagement-score");
    fireEvent.click(within(contentTable).getByRole("button", { name: "Sort by Caption" }));
    expect([...contentTable.querySelectorAll("tbody tr")].map((row) => row.textContent)).toEqual([
      expect.stringContaining("Canonical evening #hotel"),
      expect.stringContaining("Canonical summer story #travel"),
    ]);
    expect(within(contentTable).getByRole("button", { name: "Sort by Caption" }).closest("th")).toHaveAttribute("aria-sort", "ascending");
    expect(screen.queryByRole("heading", { name: "Content Winners by Objective" })).not.toBeInTheDocument();

    rerender(<FacebookPulseDashboard data={facebook} tab="audience" />);
    expect(headings()).toEqual([
            "Followers Trend", "New Followers Trend", "Top Countries", "Top Cities",
            "Paid Views Trend", "Organic Views Trend",
    ]);

    rerender(<InstagramPulseDashboard data={instagram} tab="audience" />);
    expect(headings()).toEqual([
      "Followers Trend", "New Followers Trend", "Age & Gender", "Audience by Country",
      "Best Time to Engage", "Organic Reach Trend", "Top Countries", "Top Cities",
      "Reach Source (Organic vs Paid)", "Paid Reach Trend", "Most Comments and Messages", "Most Liked Comments",
    ]);

    rerender(<TikTokPulseDashboard data={tiktok} tab="account" />);
    expect(headings()).toEqual([
      "Followers Trend", "New Followers Trend", "Performance Trends", "Video View Type",
      "Views Source Trend", "Reach Distribution", "Reach Source Trend",
    ]);

    rerender(<TikTokPulseDashboard data={tiktok} tab="audience" />);
    expect(headings()).toEqual([
      "Followers Trend", "New Followers Trend", "Age & Gender", "Audience by Country",
      "Best Time to Engage", "Organic Reach Trend", "Top Countries", "Age Groups",
      "Most Active Commenters", "Most Liked Comments",
    ]);
  });
});
