import type { MetricId, PlatformDashboard } from "../../api";

export const V1_CHART_COLORS = {
  followers: "#38bdf8",
  follows: "#3b82f6",
  unfollows: "#f59e0b",
  netFollowers: "#14b8a6",
  views: "#5eead4",
  reach: "#ec4899",
  organic: "#8357f6",
  organicViews: "#3b82f6",
  paid: "#f59e0b",
  organicReach: "#6366f1",
  likes: "#ef5da8",
  comments: "#3b82f6",
  shares: "#22c55e",
  contentType: "#ec4899",
  contentTypeReach: "#f59e0b",
} as const;

export const V1_OVERVIEW_PLATFORM_COLORS = {
  instagram: "#ec4899",
  facebook: "#2563eb",
  tiktok: "#111827",
} as const;

export const V1_TREND_STROKE_WIDTH = 1.25;
export const V1_TREND_FILL_TOP_OPACITY = 0.22;
export const V1_TREND_FILL_BOTTOM_OPACITY = 0;
export const V1_BAR_FILL_OPACITY = 0.82;

export type TrendKey = {
  id: MetricId;
  label: string;
  color: string;
  display?: "negative_absolute";
};

export const V1_FOLLOWER_FLOW_KEYS: readonly TrendKey[] = [
  { id: "follows", label: "Follows", color: V1_CHART_COLORS.follows },
  {
    id: "unfollows",
    label: "Unfollows",
    color: V1_CHART_COLORS.unfollows,
    display: "negative_absolute",
  },
  { id: "followers_net", label: "Net", color: V1_CHART_COLORS.netFollowers },
];

export function displayTrendValue(key: TrendKey, value: number): number {
  return key.display === "negative_absolute" ? -Math.abs(value) : value;
}

const compact = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});

export function followerFlowSubtitle(data: PlatformDashboard): string {
  const total = (id: MetricId, absolute = false) => {
    const points = data.series.find((series) => series.metric_id === id)?.points ?? [];
    return points.reduce(
      (sum, point) => sum + (absolute ? Math.abs(point.value) : point.value),
      0,
    );
  };
  const hasNativeFollows = data.series.some((series) => series.metric_id === "follows");
  const follows = hasNativeFollows ? total("follows") : total("new_followers");
  const unfollows = total("unfollows", true);
  const nativeNet = data.series.find((series) => series.metric_id === "followers_net");
  const net = nativeNet ? total("followers_net") : follows - unfollows;
  return `Follows: ${compact.format(follows)} | Unfollows: ${compact.format(unfollows)} | Net: ${compact.format(net)}`;
}
