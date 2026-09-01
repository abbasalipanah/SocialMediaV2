import {
  Activity,
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
  UnavailableInsightCard,
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

export function xContentTotals(content: DashboardContent[]) {
  return {
    views: availableSum(content.map((item) => item.views)),
    interactions: availableSum(content.map((item) => item.interactions)),
    likes: availableSum(content.map((item) => item.likes_count)),
    replies: availableSum(content.map((item) => item.comments_count)),
    repostsAndQuotes: availableSum(content.map((item) => item.shares_count)),
    bookmarks: availableSum(content.map((item) => item.saves_count)),
    profileVisits: availableSum(content.map((item) => item.profile_visits)),
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
    comparisonKpi("x_post_reposts", "Reposts & Quotes", data.content_metrics.shares, totals.repostsAndQuotes, Repeat2, "#22c55e"),
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
    { id: "x_profile_visits", label: "Profile Visits", value: totals.profileVisits, delta: null, icon: MousePointerClick, color: "#ec4899" },
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
    { label: "Reposts & Quotes", value: totals.repostsAndQuotes, color: V1_CHART_COLORS.shares },
    { label: "Bookmarks", value: totals.bookmarks, color: "#ec4899" },
  ]);
}

function actionRows(data: PlatformDashboard): PieRow[] {
  const totals = xContentTotals(data.content);
  return positiveRows([
    { label: "Bookmarks", value: totals.bookmarks, color: "#ec4899" },
    { label: "Profile Visits", value: totals.profileVisits, color: "#1d9bf0" },
  ]);
}

export function withXContentSeries(data: PlatformDashboard): PlatformDashboard {
  const buckets = new Map<string, { views: number; interactions: number; profile_views: number; present: Set<string> }>();
  data.content.forEach((item) => {
    if (!item.published_at) return;
    const observedOn = item.published_at.slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/u.test(observedOn)) return;
    const bucket = buckets.get(observedOn) ?? { views: 0, interactions: 0, profile_views: 0, present: new Set<string>() };
    for (const [id, value] of [
      ["views", item.views],
      ["interactions", item.interactions],
      ["profile_views", item.profile_visits],
    ] as const) {
      if (value !== null) {
        bucket[id] += value;
        bucket.present.add(id);
      }
    }
    buckets.set(observedOn, bucket);
  });
  const derivedIds = ["views", "interactions", "profile_views"] as const;
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
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Posts</SectionTitle>}
      <KpiGrid rows={contentKpis(data)} />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={summaryPieRows(data.content_summary.by_type, X_COLORS)} subtitle="Owned posts by format" title="Post Type" />
        <PulseTrendCard data={chartData} keys={[{ id: "views", label: "Impressions", color: "#1d9bf0" }, { id: "interactions", label: "Engagements", color: "#f59e0b" }]} subtitle="Current results grouped by post publish date" title="Impressions & Engagements" />
      </div>
      <div className="facebook-two-grid">
        <PulsePieCard legendColumns={2} rows={interactionRows(data)} subtitle="Likes, replies, reposts, quotes and bookmarks" title="Engagement Split" />
        <PulsePieCard rows={actionRows(data)} subtitle="Owned-post actions returned by X" title="Post Actions" />
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
  const chartData = withXContentSeries(data);
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Audience Signals</SectionTitle>}
      <KpiGrid rows={audienceKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: V1_CHART_COLORS.followers }]} localZoom subtitle="Owned profile follower snapshots" title="Followers Trend" />
        <PulseTrendCard connectGaps data={data} keys={[...V1_FOLLOWER_FLOW_KEYS]} subtitle={followerFlowSubtitle(data)} title="Follower Change" />
      </div>
      <div className="facebook-two-grid">
        <PulseTrendCard data={chartData} keys={[{ id: "profile_views", label: "Profile Visits", color: "#ec4899" }, { id: "interactions", label: "Engagements", color: "#f59e0b" }]} subtitle="Current owned-post actions grouped by publish date" title="Audience Actions" />
        <UnavailableInsightCard copy="The current read-only X integration does not receive follower geography, age, gender or activity demographics." subtitle="Not returned by the approved X endpoints" title="Audience Demographics" />
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
