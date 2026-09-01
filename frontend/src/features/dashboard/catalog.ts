import type { MetricId, Platform } from "../../api";

export type DashboardTab = {
  id: "account" | "audience" | "content" | "cover" | "overview" | "page" | "profile" | "stories" | "videos";
  label: string;
};

export const RANGE_OPTIONS = [
  { id: "last_7_days", label: "Last 7 Days" },
  { id: "last_30_days", label: "Last 30 Days" },
  { id: "last_90_days", label: "Last 90 Days" },
  { id: "last_365_days", label: "Last 365 Days" },
] as const;

export type RangeKey = (typeof RANGE_OPTIONS)[number]["id"];

export const PLATFORM_LABELS: Record<Platform, string> = {
  facebook: "Facebook",
  instagram: "Instagram",
  tiktok: "TikTok",
};

export const PLATFORM_DESCRIPTIONS: Record<Platform, string> = {
  facebook: "Unified Facebook performance monitor.",
  instagram: "Unified Instagram performance monitor.",
  tiktok: "Organic account, video and audience performance in one view.",
};

export const METRIC_LABELS: Record<MetricId, string> = {
  followers: "Followers",
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
  };
  return tabs[platform];
}
