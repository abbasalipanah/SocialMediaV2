import type { MetricId, Platform } from "../../api";
export { PLATFORM_DESCRIPTIONS, PLATFORM_LABELS } from "../../platforms/catalog";

export type DashboardTab = {
  id: "account" | "audience" | "content" | "cover" | "overview" | "page" | "profile" | "stories" | "videos";
  label: string;
};

export const PRESET_RANGE_OPTIONS = [
  { id: "last_7_days", label: "Last 7 Days" },
  { id: "last_30_days", label: "Last 30 Days" },
  { id: "last_90_days", label: "Last 90 Days" },
  { id: "last_365_days", label: "Last 365 Days" },
] as const;

export const RANGE_OPTIONS = [
  ...PRESET_RANGE_OPTIONS,
  { id: "selected_period", label: "Selected Period" },
] as const;

export type PresetRangeKey = (typeof PRESET_RANGE_OPTIONS)[number]["id"];
export type RangeKey = (typeof RANGE_OPTIONS)[number]["id"];

export type ReportingPeriod = {
  key: RangeKey;
  startDate?: string;
  endDate?: string;
};

export const DEFAULT_REPORTING_PERIOD: ReportingPeriod = { key: "last_30_days" };

export function reportingPeriodQuery(period: ReportingPeriod) {
  return {
    range: period.key,
    start_date: period.key === "selected_period" ? period.startDate : undefined,
    end_date: period.key === "selected_period" ? period.endDate : undefined,
  };
}
export const METRIC_LABELS: Record<MetricId, string> = {
  followers: "Followers",
  follower_gains: "Follower gains",
  following: "Following",
  new_followers: "New followers",
  follows: "Follows",
  unfollows: "Unfollows",
  followers_net: "Net followers",
  reach: "Reach",
  reach_paid: "Paid reach",
  reach_organic: "Organic reach",
  views: "Views",
  views_paid: "Paid views",
  views_organic: "Organic views",
  interactions: "Interactions",
  engagement_rate: "Engagement rate",
  page_views: "Page views",
  profile_views: "Profile views",
  website_clicks: "Website clicks",
  clicks: "Clicks",
  total_actions: "Total actions",
  reactions: "Reactions",
  media_count: "Published content",
  video_views_total: "Video views",
  video_views_change: "Video view change",
  video_likes_daily: "Daily video likes",
  video_comments_daily: "Daily video comments",
  video_shares_daily: "Daily video shares",
  video_likes_total: "Video likes",
  video_comments_total: "Video comments",
  video_shares_total: "Video shares",
  video_engagements_total: "Video engagements",
  video_engagement_rate: "Video engagement rate",
  engaged_views: "Engaged views",
  watch_time_minutes: "Watch time",
  playlist_additions: "Playlist additions",
  playlist_removals: "Playlist removals",
};

export const PRIMARY_METRICS: Record<Platform | "overview", MetricId[]> = {
  overview: ["followers", "new_followers", "reach", "views", "interactions", "media_count"],
  facebook: ["followers", "new_followers", "reach", "page_views", "interactions", "engagement_rate"],
  instagram: ["followers", "new_followers", "reach", "profile_views", "interactions", "engagement_rate"],
  tiktok: [
    "followers",
    "video_views_total",
    "video_likes_total",
    "video_comments_total",
    "video_shares_total",
    "video_engagement_rate",
  ],
  x: ["followers", "new_followers", "views", "interactions", "engagement_rate", "media_count"],
  linkedin: ["followers", "follower_gains", "views", "reach", "page_views", "engagement_rate"],
  youtube: ["followers", "views", "engaged_views", "watch_time_minutes", "follows", "engagement_rate"],
};

export const TREND_METRICS: MetricId[] = [
  "followers",
  "new_followers",
  "follows",
  "unfollows",
  "followers_net",
  "reach",
  "views",
  "interactions",
  "engagement_rate",
  "profile_views",
  "video_views_total",
  "video_engagements_total",
  "engaged_views",
  "watch_time_minutes",
  "video_likes_daily",
  "video_comments_daily",
  "video_shares_daily",
  "playlist_additions",
  "playlist_removals",
];

export function platformTabs(platform: Platform, audienceAvailable: boolean): DashboardTab[] {
  const tabs: Record<Platform, DashboardTab[]> = {
    facebook: [
      { id: "cover", label: "Cover" },
      { id: "page", label: "Page" },
      { id: "content", label: "Content" },
      { id: "audience", label: "Audience" },
    ],
    instagram: [
      { id: "cover", label: "Cover" },
      { id: "page", label: "Page" },
      { id: "content", label: "Content" },
      { id: "stories", label: "Stories" },
      { id: "audience", label: "Audience" },
    ],
    tiktok: [
      { id: "cover", label: "Cover" },
      { id: "account", label: "Account" },
      { id: "content", label: "Content" },
      { id: "audience", label: "Audience" },
    ],
    x: [
      { id: "cover", label: "Cover" },
      { id: "profile", label: "Profile" },
      { id: "content", label: "Posts" },
      { id: "audience", label: "Audience Signals" },
    ],
    linkedin: [
      { id: "cover", label: "Cover" },
      { id: "page", label: "Page" },
      { id: "content", label: "Content" },
      { id: "audience", label: "Audience" },
    ],
    youtube: [
      { id: "cover", label: "Cover" },
      { id: "account", label: "Channel" },
      { id: "content", label: "Videos" },
      { id: "audience", label: "Audience" },
    ],
  };
  return tabs[platform];
}
