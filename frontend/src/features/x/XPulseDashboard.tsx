import {
  Activity,
  AtSign,
  Bookmark,
  Eye,
  FileText,
  Heart,
  MessageCircle,
  MousePointerClick,
  Repeat2,
  TrendingUp,
  Users,
} from "lucide-react";

import type {
  DashboardContent,
  DashboardMetric,
  MetricId,
  PlatformDashboard,
} from "../../api";
import { V1_CHART_COLORS, V1_FOLLOWER_FLOW_KEYS, followerFlowSubtitle } from "../dashboard/visualPalette";
import {
  KpiGrid,
  PerformingContentTable,
  PulseHeatmapCard,
  PulsePieCard,
  PulseTrendCard,
  SectionTitle,
  SimplePulseTable,
  summaryPieRows,
  type PieRow,
  type PulseKpi,
} from "../facebook/FacebookPulseDashboard";

type XTab = "cover" | "profile" | "content" | "audience";
type DashboardComparison = PlatformDashboard["content_metrics"]["views"];

const X_COLORS = ["#0f1419", "#1d9bf0", "#536471", "#8b5cf6", "#f59e0b", "#14b8a6"];

function metric(data: PlatformDashboard, id: MetricId): DashboardMetric | undefined {
  return data.metrics.find((item) => item.metric_id === id);
}

function availableSum(values: Array<number | null>): number | null {
  const available = values.filter((value): value is number => value !== null);
  return available.length ? available.reduce((sum, value) => sum + value, 0) : null;
}

function availableAverage(values: Array<number | null>): number | null {
  const available = values.filter((value): value is number => value !== null);
  return available.length
    ? available.reduce((sum, value) => sum + value, 0) / available.length
    : null;
}

export function xContentTotals(content: DashboardContent[]) {
  return {
    views: availableSum(content.map((item) => item.views)),
    interactions: availableSum(content.map((item) => item.interactions)),
    likes: availableSum(content.map((item) => item.likes_count)),
    replies: availableSum(content.map((item) => item.comments_count)),
    reposts: availableSum(content.map((item) => item.reposts_count)),
    quotes: availableSum(content.map((item) => item.quotes_count)),
    bookmarks: availableSum(content.map((item) => item.saves_count)),
    linkClicks: availableSum(content.map((item) => item.link_clicks)),
    profileClicks: availableSum(content.map((item) => item.profile_clicks)),
    videoViews: availableSum(content.map((item) => item.video_views_count)),
    videoPlayback0: availableSum(content.map((item) => item.video_playback_0_count)),
    videoPlayback25: availableSum(content.map((item) => item.video_playback_25_count)),
    videoPlayback50: availableSum(content.map((item) => item.video_playback_50_count)),
    videoPlayback75: availableSum(content.map((item) => item.video_playback_75_count)),
    videoPlayback100: availableSum(content.map((item) => item.video_playback_100_count)),
    averageImpressions: availableAverage(content.map((item) => item.views)),
    averageEngagements: availableAverage(content.map((item) => item.interactions)),
  };
}

function metricKpi(
  data: PlatformDashboard,
  id: MetricId,
  label: string,
  icon: PulseKpi["icon"],
  color: string,
): PulseKpi {
  const current = metric(data, id);
  return {
    id,
    label,
    value: current?.value ?? null,
    delta: current?.delta_pct ?? null,
    icon,
    color,
    unit: current?.unit,
  };
}

function comparisonKpi(
  id: string,
  label: string,
  comparison: DashboardComparison,
  fallback: number | null,
  icon: PulseKpi["icon"],
  color: string,
  unit?: PulseKpi["unit"],
): PulseKpi {
  return {
    id,
    label,
    value: comparison.value ?? fallback,
    delta: comparison.delta_pct,
    icon,
    color,
    unit,
  };
}

function profileKpis(data: PlatformDashboard): PulseKpi[] {
  const totals = xContentTotals(data.content);
  return [
    metricKpi(data, "followers", "Followers", Users, V1_CHART_COLORS.followers),
    metricKpi(data, "new_followers", "New Followers", TrendingUp, "#14b8a6"),
    metricKpi(data, "media_count", "Published Posts", FileText, "#536471"),
    comparisonKpi("x_impressions", "Post Impressions", data.content_metrics.views, totals.views, Eye, "#1d9bf0"),
    comparisonKpi("x_engagements", "Post Engagements", data.content_metrics.interactions, totals.interactions, Activity, "#f59e0b"),
    comparisonKpi("x_engagement_rate", "Engagement Rate", data.content_metrics.engagement_rate, null, TrendingUp, "#8b5cf6", "ratio"),
  ];
}

function contentKpis(data: PlatformDashboard): PulseKpi[] {
  const totals = xContentTotals(data.content);
  return [
    comparisonKpi("x_post_impressions", "Impressions", data.content_metrics.views, totals.views, Eye, "#1d9bf0"),
    comparisonKpi("x_post_likes", "Likes", data.content_metrics.likes, totals.likes, Heart, V1_CHART_COLORS.likes),
    comparisonKpi("x_post_replies", "Replies", data.content_metrics.comments, totals.replies, MessageCircle, "#3b82f6"),
    { id: "x_post_reposts", label: "Reposts", value: totals.reposts, delta: null, icon: Repeat2, color: "#22c55e" },
    { id: "x_post_bookmarks", label: "Bookmarks", value: totals.bookmarks, delta: null, icon: Bookmark, color: "#ec4899" },
    comparisonKpi("x_post_engagement_rate", "Engagement Rate", data.content_metrics.engagement_rate, null, TrendingUp, "#8b5cf6", "ratio"),
  ];
}

function audienceKpis(data: PlatformDashboard): PulseKpi[] {
  const totals = xContentTotals(data.content);
  return [
    metricKpi(data, "followers", "Followers", Users, V1_CHART_COLORS.followers),
    metricKpi(data, "new_followers", "New Followers", TrendingUp, "#14b8a6"),
    comparisonKpi("x_audience_impressions", "Post Impressions", data.content_metrics.views, totals.views, Eye, "#1d9bf0"),
    comparisonKpi("x_audience_engagements", "Post Engagements", data.content_metrics.interactions, totals.interactions, Activity, "#f59e0b"),
    { id: "x_profile_clicks", label: "Profile Clicks", value: totals.profileClicks, delta: null, icon: MousePointerClick, color: "#ec4899" },
    comparisonKpi("x_audience_engagement_rate", "Engagement Rate", data.content_metrics.engagement_rate, null, TrendingUp, "#8b5cf6", "ratio"),
  ];
}

function positiveRows(rows: Array<{ label: string; value: number | null; color: string }>): PieRow[] {
  return rows.flatMap((row) => row.value !== null && row.value > 0
    ? [{ ...row, value: row.value }]
    : []);
}

function interactionRows(data: PlatformDashboard): PieRow[] {
  const totals = xContentTotals(data.content);
  return positiveRows([
    { label: "Likes", value: totals.likes, color: V1_CHART_COLORS.likes },
    { label: "Replies", value: totals.replies, color: V1_CHART_COLORS.comments },
    { label: "Reposts", value: totals.reposts, color: V1_CHART_COLORS.shares },
    { label: "Quotes", value: totals.quotes, color: "#8b5cf6" },
    { label: "Bookmarks", value: totals.bookmarks, color: "#ec4899" },
  ]);
}

function actionRows(data: PlatformDashboard): PieRow[] {
  const totals = xContentTotals(data.content);
  return positiveRows([
    { label: "Link Clicks", value: totals.linkClicks, color: "#14b8a6" },
    { label: "Profile Clicks", value: totals.profileClicks, color: "#1d9bf0" },
    { label: "Video Views", value: totals.videoViews, color: "#8b5cf6" },
    { label: "Bookmarks", value: totals.bookmarks, color: "#ec4899" },
  ]);
}

export function withXContentSeries(data: PlatformDashboard): PlatformDashboard {
  const buckets = new Map<string, {
    interactions: number;
    profile_views: number;
    video_views_total: number;
    views: number;
    website_clicks: number;
    present: Set<string>;
  }>();
  data.content.forEach((item) => {
    if (!item.published_at) return;
    const observedOn = item.published_at.slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/u.test(observedOn)) return;
    const bucket = buckets.get(observedOn) ?? {
      views: 0,
      interactions: 0,
      profile_views: 0,
      website_clicks: 0,
      video_views_total: 0,
      present: new Set<string>(),
    };
    for (const [id, value] of [
      ["views", item.views],
      ["interactions", item.interactions],
      ["profile_views", item.profile_clicks],
      ["website_clicks", item.link_clicks],
      ["video_views_total", item.video_views_count],
    ] as const) {
      if (value !== null) {
        bucket[id] += value;
        bucket.present.add(id);
      }
    }
    buckets.set(observedOn, bucket);
  });
  const derivedIds = [
    "views",
    "interactions",
    "profile_views",
    "website_clicks",
    "video_views_total",
  ] as const;
  const derived = derivedIds.flatMap((id) => {
    const points = [...buckets.entries()]
      .filter(([, bucket]) => bucket.present.has(id))
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([observed_on, bucket]) => ({ observed_on, value: bucket[id] }));
    return points.length ? [{
      metric_id: id,
      semantic_type: "flow" as const,
      points,
      methodology: "derived:owned_posts_grouped_by_publish_date:v1",
    }] : [];
  });
  return {
    ...data,
    series: [
      ...data.series.filter((item) => !derivedIds.includes(item.metric_id as typeof derivedIds[number])),
      ...derived,
    ],
  };
}

function withXMentionSeries(data: PlatformDashboard): PlatformDashboard {
  const mentionSeries = data.mentions?.daily.length
    ? [{
      metric_id: "reactions" as const,
      semantic_type: "flow" as const,
      points: data.mentions.daily,
      methodology: "provider:x_user_mentions_endpoint",
    }]
    : [];
  return {
    ...data,
    series: [
      ...data.series.filter((item) => item.metric_id !== "reactions"),
      ...mentionSeries,
    ],
  };
}

function displayMetric(value: number | null, digits = 0): string {
  return value === null
    ? "—"
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(value);
}

function contentTypePerformanceRows(content: DashboardContent[]) {
  const labels: Record<string, string> = {
    text: "Text",
    image: "Image",
    video: "Video",
    link: "Link",
  };
  return ["text", "image", "video", "link"].flatMap((type) => {
    const rows = content.filter((item) => item.content_type.toLowerCase() === type);
    if (!rows.length) return [];
    const impressions = availableSum(rows.map((item) => item.views));
    const engagements = availableSum(rows.map((item) => item.interactions));
    return [[
      labels[type],
      rows.length,
      displayMetric(impressions),
      displayMetric(engagements),
      displayMetric(availableAverage(rows.map((item) => item.interactions)), 1),
    ]];
  });
}

function videoPlaybackRows(data: PlatformDashboard) {
  const totals = xContentTotals(data.content);
  const completionRate = totals.videoPlayback0 && totals.videoPlayback100 !== null
    ? totals.videoPlayback100 / totals.videoPlayback0
    : null;
  return [
    ["Video Views", totals.videoViews],
    ["Started (0%)", totals.videoPlayback0],
    ["25%", totals.videoPlayback25],
    ["50%", totals.videoPlayback50],
    ["75%", totals.videoPlayback75],
    ["100%", totals.videoPlayback100],
    ["Completion Rate (derived)", completionRate === null ? null : `${(completionRate * 100).toFixed(1)}%`],
  ].flatMap(([label, value]) => value === null ? [] : [[label, value]]);
}

function ProfileSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  const chartData = withXContentSeries(data);
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Profile</SectionTitle>}
      <KpiGrid rows={profileKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: V1_CHART_COLORS.followers }]} localZoom subtitle="Owned profile follower snapshots" title="Followers Trend" />
        <PulseTrendCard data={data} keys={[{ id: "media_count", label: "Published Posts", color: "#536471" }]} localZoom subtitle="Owned profile post-count snapshots" title="Published Posts Trend" />
      </div>
      <PulseTrendCard bar data={chartData} keys={[{ id: "views", label: "Impressions", color: "#1d9bf0" }, { id: "interactions", label: "Engagements", color: "#f59e0b" }]} subtitle="Current owned-post results grouped by publish date" title="Post Performance" wide />
    </section>
  );
}

function ContentSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  const chartData = withXContentSeries(data);
  const totals = xContentTotals(data.content);
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Posts</SectionTitle>}
      <KpiGrid rows={contentKpis(data)} />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={summaryPieRows(data.content_summary.by_type, X_COLORS)} subtitle="Owned posts by format" title="Post Type" />
        <PulseTrendCard data={chartData} keys={[{ id: "views", label: "Impressions", color: "#1d9bf0" }, { id: "interactions", label: "Engagements", color: "#f59e0b" }]} subtitle="Current results grouped by post publish date" title="Impressions & Engagements" />
      </div>
      <div className="facebook-two-three-grid">
        <SimplePulseTable
          columns={["Type", "Posts", "Impressions", "Engagements", "Avg. Engagement"]}
          emptyCopy="No owned-post format data in this period."
          rows={contentTypePerformanceRows(data.content)}
          subtitle="Text, image, video and link post results"
          title="Content Type Performance"
        />
        <SimplePulseTable
          columns={["Metric", "Average"]}
          rows={[
            ["Avg. Impressions per Post", displayMetric(totals.averageImpressions, 1)],
            ["Avg. Engagement per Post", displayMetric(totals.averageEngagements, 1)],
          ]}
          subtitle="Average across posts where the metric is available"
          title="Per-post Averages"
        />
      </div>
      <div className="facebook-three-grid">
        <PulsePieCard legendColumns={2} rows={interactionRows(data)} subtitle="Likes, replies, reposts, quotes and bookmarks" title="Engagement Split" />
        <PulsePieCard legendColumns={2} rows={actionRows(data)} subtitle="Clicks, bookmarks and video views returned by X" title="Post Actions" />
        <SimplePulseTable
          columns={["Playback", "Value"]}
          emptyCopy="X returned no video playback metrics for these posts."
          rows={videoPlaybackRows(data)}
          subtitle="Owned-video playback stages; completion is derived from starts"
          title="Video Playback"
        />
      </div>
      <div className="facebook-two-grid">
        <PulseHeatmapCard breakdowns={data.breakdowns} />
        <SimplePulseTable columns={["Hashtag", "Posts"]} emptyCopy="No hashtags in collected posts." rows={data.top_hashtags.map((item) => [item.name, item.count])} subtitle="Hashtags found in owned posts" title="Top Hashtags" />
      </div>
      <PerformingContentTable content={data.content} variant="x" />
    </section>
  );
}

function AudienceSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  const chartData = withXMentionSeries(data);
  const mentionRows = data.mentions && data.mentions.total > 0
    ? [
      [<span className="facebook-table-metric"><AtSign size={14} />Mentions</span>, data.mentions.total],
      [<span className="facebook-table-metric"><Users size={14} />Unique Mention Authors</span>, data.mentions.unique_authors],
    ]
    : [];
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Audience Signals</SectionTitle>}
      <KpiGrid rows={audienceKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: V1_CHART_COLORS.followers }]} localZoom subtitle="Owned profile follower snapshots" title="Followers Trend" />
        <PulseTrendCard connectGaps data={data} keys={[...V1_FOLLOWER_FLOW_KEYS]} subtitle={followerFlowSubtitle(data)} title="Follower Change" />
      </div>
      <div className="facebook-two-grid">
        <PulseTrendCard data={chartData} keys={[{ id: "reactions", label: "Mentions", color: "#1d9bf0" }]} subtitle="Account mentions returned by the X mentions endpoint" title="Mentions Trend" />
        <SimplePulseTable
          columns={["Signal", "Value"]}
          emptyCopy="No mention data was returned for this period."
          rows={mentionRows}
          subtitle="Mention counts are kept separate from owned-post engagement"
          title="Mention Signals"
        />
      </div>
    </section>
  );
}

export function XPulseDashboard({ data, tab }: { data: PlatformDashboard; tab: XTab }) {
  const cover = tab === "cover";
  return (
    <div className="facebook-pulse-dashboard x-pulse-dashboard">
      {(tab === "profile" || cover) && <ProfileSection data={data} withTitle={cover} />}
      {(tab === "content" || cover) && <ContentSection data={data} withTitle={cover} />}
      {(tab === "audience" || cover) && <AudienceSection data={data} withTitle={cover} />}
    </div>
  );
}
