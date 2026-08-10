import type { Page } from "@playwright/test";

type Platform = "facebook" | "instagram" | "tiktok";

export const auth = {
  authenticated: true,
  user_id: "r5-user",
  email: "owner@example.test",
  source_system: "accumulate",
  brand_id: "hotel-1",
  role: "agency_admin",
  app_role: null,
  access_mode: "write",
  settings_visible: true,
  integrations_visible: true,
  is_internal_staff: true,
  expires_at: "2026-07-14T22:00:00Z",
  revoked: false,
};

export const scope = {
  requested_brand_id: "hotel-1",
  rollup: false,
  resolved_brand_ids: ["hotel-1"],
};

export const workspace = {
  default_brand_id: "hotel-1",
  brands: [
    { brand_id: "group-1", name: "Coastal Hotels", parent_brand_id: null, visibility: "hidden_parent", access_mode: null, role: null },
    { brand_id: "hotel-1", name: "Coastal One", parent_brand_id: "group-1", visibility: "active", access_mode: "write", role: "agency_admin" },
  ],
  families: [{ root_brand_id: "group-1", brand_ids: ["group-1", "hotel-1"] }],
  scope,
};

export const capabilities = {
  scope,
  platforms: (["facebook", "instagram", "tiktok"] as const).map((platform) => ({
    platform,
    linked_account_count: 1,
    navigation_available: true,
    capabilities: [
      { platform, capability: "profile", status: "available", reason: "linked" },
      { platform, capability: "audience", status: "available", reason: "linked" },
    ],
  })),
  permissions: {
    settings_visible: true,
    integrations_visible: true,
    internal_audit_visible: true,
    rollup_available: true,
    operation_mutation_available: false,
    tiktok_connection_manage: true,
    meta_connection_manage: true,
  },
  runtime: { mode: "dormant", writes_enabled: false, automated_schedule_available: false },
};

const metric = (
  metric_id: string,
  value: number,
  semantic_type: "snapshot" | "flow" | "cumulative" | "ratio" = "flow",
  unit: "count" | "ratio" = "count",
) => ({
  metric_id,
  value,
  previous_value: value * 0.9,
  delta_pct: 11.1,
  semantic_type,
  unit,
  data_status: "available",
  methodology: "provider_reported",
  availability_reason: null,
});

const points = (metric_id: string, semantic_type: "snapshot" | "flow" | "cumulative" | "ratio" = "flow") => ({
  metric_id,
  semantic_type,
  points: [
    { observed_on: "2026-06-15", value: 820 },
    { observed_on: "2026-06-22", value: 930 },
    { observed_on: "2026-06-29", value: 1010 },
    { observed_on: "2026-07-06", value: 1120 },
    { observed_on: "2026-07-14", value: 1200 },
  ],
  methodology: "provider_reported",
});

const followerFlowPoints = (metric_id: "follows" | "unfollows" | "followers_net") => ({
  metric_id,
  semantic_type: "flow" as const,
  points: [
    { observed_on: "2026-06-15", value: metric_id === "follows" ? 7 : metric_id === "unfollows" ? 2 : 5 },
    { observed_on: "2026-06-22", value: metric_id === "follows" ? 4 : metric_id === "unfollows" ? 5 : -1 },
    { observed_on: "2026-06-29", value: metric_id === "follows" ? 9 : metric_id === "unfollows" ? 3 : 6 },
    { observed_on: "2026-07-06", value: metric_id === "follows" ? 6 : metric_id === "unfollows" ? 7 : -1 },
    { observed_on: "2026-07-14", value: metric_id === "follows" ? 8 : metric_id === "unfollows" ? 4 : 4 },
  ],
  methodology: "provider_reported",
});

const story = {
  content_id: "story-1",
  title: "Morning on the coast",
  cover_url: "",
  permalink: "https://example.test/story-1",
  created_time: "2026-07-14T08:00:00Z",
  views: 446,
  reach: 390,
  interactions: 72,
  replies: 8,
  shares: 11,
  profile_visits: 19,
  follows: 6,
  sticker_taps: null,
  saves: 4,
  taps_forward: 90,
  taps_back: 12,
  swipe_forward: 7,
  exits: 18,
  navigation: 127,
  completion_rate: 72,
  data_status: "available",
};

const stories = [
  story,
  {
    ...story,
    content_id: "story-2",
    title: "Poolside serenity",
    cover_url: "/branding/follower-avatar-12.jpg",
    permalink: "https://example.test/story-2",
    created_time: "2026-07-14T07:00:00Z",
    views: 408,
    reach: 352,
    interactions: 64,
    replies: 6,
    shares: 9,
    profile_visits: 15,
    follows: 5,
    taps_forward: 82,
    taps_back: 10,
    swipe_forward: 8,
    exits: 20,
    navigation: 120,
    completion_rate: 68.5,
  },
  {
    ...story,
    content_id: "story-3",
    title: "A room with a view",
    cover_url: "/branding/follower-avatar-5.jpg",
    permalink: "https://example.test/story-3",
    created_time: "2026-07-14T06:00:00Z",
    views: 371,
    reach: 318,
    interactions: 51,
    replies: 5,
    shares: 7,
    profile_visits: 12,
    follows: 4,
    taps_forward: 76,
    taps_back: 11,
    swipe_forward: 6,
    exits: 22,
    navigation: 115,
    completion_rate: 65.2,
  },
  {
    ...story,
    content_id: "story-4",
    title: "Evening escape",
    cover_url: "/branding/follower-avatar-9.jpg",
    permalink: "https://example.test/story-4",
    created_time: "2026-07-13T20:00:00Z",
    views: 330,
    reach: 286,
    interactions: 44,
    replies: 4,
    shares: 6,
    profile_visits: 10,
    follows: 3,
    taps_forward: 69,
    taps_back: 9,
    swipe_forward: 5,
    exits: 24,
    navigation: 107,
    completion_rate: 62.8,
  },
];

export function dashboardFor(platform: Platform) {
  const tiktok = platform === "tiktok";
  return {
    meta: {
      dashboard_id: platform,
      platform,
      requested_brand_id: "hotel-1",
      rollup: false,
      resolved_brand_ids: ["hotel-1"],
      resolved_account_ids: [31],
      date_range: { start_on: "2026-06-15", end_on: "2026-07-14", key: "last_30_days" },
      generated_at: "2026-07-14T12:00:00Z",
      last_sync_at: "2026-07-14T11:00:00Z",
      freshness: "fresh",
      observed_days: 30,
      expected_days: 30,
      data_status: "available",
      warnings: [],
    },
    metrics: tiktok ? [
      metric("followers", 1200, "snapshot"),
      metric("new_followers", 84),
      metric("reach", 9300),
      metric("video_views_total", 14800, "cumulative"),
      metric("video_likes_total", 960, "cumulative"),
      metric("video_comments_total", 118, "cumulative"),
      metric("video_shares_total", 72, "cumulative"),
      metric("video_engagements_total", 1150, "cumulative"),
      metric("video_engagement_rate", 0.078, "ratio", "ratio"),
    ] : [
      metric("followers", 1200, "snapshot"),
      metric("new_followers", 84),
      metric("views", 14800),
      metric("reach", 9300),
      metric("profile_views", 760),
      metric("interactions", 1150),
      metric("views_organic", 12100),
      metric("views_paid", 2700),
      metric("reach_organic", 7800),
      metric("reach_paid", 1500),
    ],
    series: tiktok ? [
      points("followers", "snapshot"), points("new_followers"),
      followerFlowPoints("follows"), followerFlowPoints("unfollows"), followerFlowPoints("followers_net"),
      points("reach"),
      points("video_views_total", "cumulative"), points("video_likes_total", "cumulative"),
      points("video_comments_total", "cumulative"), points("video_shares_total", "cumulative"),
    ] : [
      points("followers", "snapshot"), points("new_followers"),
      followerFlowPoints("follows"), followerFlowPoints("unfollows"), followerFlowPoints("followers_net"),
      points("views"), points("reach"),
      points("interactions"), points("views_organic"), points("views_paid"), points("reach_organic"), points("reach_paid"),
    ],
    breakdowns: [
      { metric_id: "followers", dimension: "audience_age_gender", items: [{ key: "female|25-34", value: 420, percentage: 35 }, { key: "male|25-34", value: 330, percentage: 27.5 }, { key: "female|35-44", value: 250, percentage: 20.8 }] },
      { metric_id: "followers", dimension: "audience_age", items: [{ key: "25-34", value: 750, percentage: 62.5 }, { key: "35-44", value: 300, percentage: 25 }] },
      { metric_id: "followers", dimension: "audience_country", items: [{ key: "Turkey", value: 720, percentage: 60 }, { key: "United Kingdom", value: 240, percentage: 20 }] },
      { metric_id: "followers", dimension: "audience_city", items: [{ key: "Istanbul", value: 380, percentage: 31.7 }, { key: "London", value: 160, percentage: 13.3 }] },
      { metric_id: "followers", dimension: "audience_activity", items: [{ key: "mon|10", value: 88, percentage: null }, { key: "fri|20", value: 112, percentage: null }] },
      { metric_id: "followers", dimension: "like_type", items: [{ key: "organic", value: 1130, percentage: 94.2 }, { key: "paid", value: 70, percentage: 5.8 }] },
    ],
    content: [{
      account_id: 31,
      external_content_id: `${platform}-video-1`,
      content_type: "video",
      permalink: "https://example.test/video-1",
      message: "Coastal sunrise and a quiet morning by the pool.",
      media_url: "",
      published_at: "2026-07-13T10:00:00Z",
      likes_count: 250,
      comments_count: 44,
      shares_count: 22,
      interactions: 316,
      views: 4200,
      reach: 3100,
      cover_url: null,
      thumbnail_url: null,
      cover_candidates: [],
      thumbnail_candidates: [],
      media_url_candidates: [],
      full_video_watched_rate: tiktok ? 0.43 : null,
      total_time_watched: tiktok ? 23000 : null,
      average_time_watched: tiktok ? 12.4 : null,
      data_status: "available",
    }],
    community: {
      total_comments: 44,
      answered_comments: 31,
      unanswered_comments: 13,
      comment_likes: 190,
      data_status: "available",
      top_commenters: [{ name: "coastlover", comments: 12, likes: 56 }],
      top_liked_comments: [{ name: "traveler", comment: "Beautiful morning!", likes: 42, replies: 3 }],
    },
    top_hashtags: [{ name: "#coastal", count: 8 }, { name: "#travel", count: 5 }],
    content_summary: {
      total: 1,
      by_type: [{ name: "Video", value: 1 }],
      reach_by_type: [{ name: "Video", value: 3100 }],
      views_by_type: [{ name: "Video", value: 4200 }],
      data_status: "available",
    },
    source_breakdown: {
      organic_only: false,
      paid_available: true,
      views: { organic: 12100, paid: 2700, data_status: "available" },
      reach: { organic: 7800, paid: 1500, data_status: "available" },
      data_status: "available",
    },
    metric_methodology: { follower_flow: "provider_reported", engagement_rate: "derived", reach: "provider_reported" },
    audience_capabilities: { source: tiktok ? "tiktok_display_api" : "meta_graph_api", geo: "available", age_gender: "available", activity: "available" },
    stories: platform === "instagram" ? {
      summary: { count: 1, views: 446, reach: 390, interactions: 72, replies: 8, completion_rate: 72, data_status: "available" },
      previous_summary: { count: 1, views: 400, reach: 350, interactions: 61, replies: 6, completion_rate: 68, data_status: "available" },
      trend: { labels: ["2026-07-13", "2026-07-14"], views: [400, 446], reach: [350, 390], data_status: "available" },
      navigation: { taps_forward: 90, taps_back: 12, swipe_forward: 7, exits: 18, data_status: "available" },
      actions: { replies: 8, shares: 11, profile_visits: 19, follows: 6, sticker_taps: null, saves: 4, data_status: "partial" },
      items: stories,
      data_status: "available",
    } : null,
  };
}

export function overviewDashboard() {
  const platforms = (["facebook", "instagram", "tiktok"] as const).map(dashboardFor);
  return {
    meta: { ...platforms[0].meta, dashboard_id: "overview", platform: null },
    metrics: [
      metric("followers", 3600, "snapshot"),
      metric("new_followers", 252),
      metric("reach", 27900),
      metric("views", 44400),
      metric("interactions", 3450),
      metric("website_clicks", 220),
      metric("reactions", 820),
    ],
    platforms,
    content: platforms.flatMap((dashboard) => dashboard.content),
    community: platforms[0].community,
  };
}

const accountFor = (platform: Platform) => ({
  account_id: platform === "facebook" ? 31 : platform === "instagram" ? 32 : 33,
  brand_id: "hotel-1",
  platform,
  external_id: `${platform}-account`,
  display_name: `Coastal ${platform === "tiktok" ? "TikTok" : `${platform[0]?.toUpperCase()}${platform.slice(1)}`}`,
  status: "active",
  connection_state: "connected",
  health_status: "healthy",
  backfill_status: "complete",
  nightly_enabled: true,
  last_synced_at: "2026-07-14T11:00:00Z",
});

export async function mockR5Api(page: Page, authenticated = true) {
  await page.route(/^http:\/\/127\.0\.0\.1:\d+\/api\//, async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path === "/api/auth/me") {
      await route.fulfill({ status: authenticated ? 200 : 401, json: authenticated ? auth : { detail: "session_invalid" } });
      return;
    }
    if (path === "/api/workspace/brands") return void await route.fulfill({ json: workspace });
    if (path === "/api/workspace/capabilities") return void await route.fulfill({ json: capabilities });
    if (path === "/api/dashboards/overview") return void await route.fulfill({ json: overviewDashboard() });
    if (path === "/api/insights") return void await route.fulfill({ json: { meta: scope, items: [] } });
    for (const platform of ["facebook", "instagram", "tiktok"] as const) {
      if (path === `/api/platforms/${platform}/accounts`) return void await route.fulfill({ json: { meta: scope, platform, accounts: [accountFor(platform)] } });
      if (path === `/api/dashboards/${platform}`) return void await route.fulfill({ json: dashboardFor(platform) });
    }
    if (path === "/api/settings/brands") return void await route.fulfill({ json: { meta: scope, items: workspace.brands.map((brand, index) => ({ ...brand, linked_account_count: index, last_sync_at: index ? "2026-07-14T11:00:00Z" : null })) } });
    if (path === "/api/settings/social-accounts") return void await route.fulfill({ json: { meta: scope, items: (["facebook", "instagram", "tiktok"] as const).map(accountFor) } });
    if (path === "/api/settings/brand-links") return void await route.fulfill({ json: { meta: scope, items: [] } });
    if (path === "/api/settings/connections") return void await route.fulfill({ json: { meta: scope, items: [] } });
    if (path === "/api/settings/sync-jobs") return void await route.fulfill({ json: { meta: scope, items: [] } });
    if (path === "/api/operations/readiness") return void await route.fulfill({ json: { status: "ready", runtime_mode: "dormant", writes_enabled: false, database_configured: true, scope, platforms: (["facebook", "instagram", "tiktok"] as const).map((platform) => ({ platform, account_count: 1, last_sync_at: "2026-07-14T11:00:00Z", pending_job_count: 0 })) } });
    if (path === "/api/settings/tiktok/activation-readiness") return void await route.fulfill({ status: 403, json: { detail: "tiktok_owner_launch_required" } });
    await route.abort("blockedbyclient");
  });
}
