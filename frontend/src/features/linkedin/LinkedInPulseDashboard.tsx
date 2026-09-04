import {
  Activity,
  Eye,
  FileText,
  MessageCircle,
  MousePointerClick,
  Share2,
  ThumbsUp,
  TrendingUp,
  Users,
} from "lucide-react";

import type {
  DashboardBreakdown,
  DashboardContent,
  DashboardMetric,
  MetricId,
  PlatformDashboard,
} from "../../api";
import {
  KpiGrid,
  PerformingContentTable,
  PulsePieCard,
  PulseTrendCard,
  SectionTitle,
  SimplePulseTable,
  summaryPieRows,
  type PieRow,
  type PulseKpi,
} from "../facebook/FacebookPulseDashboard";
import { humanize } from "../dashboard/format";
import { V1_CHART_COLORS } from "../dashboard/visualPalette";

type LinkedInTab = "cover" | "page" | "content" | "audience";

const LINKEDIN_COLORS = ["#0a66c2", "#378fe9", "#5e5e5e", "#8b5cf6", "#14b8a6", "#f59e0b"];

function metric(data: PlatformDashboard, id: MetricId): DashboardMetric | undefined {
  return data.metrics.find((item) => item.metric_id === id);
}

function sum(values: Array<number | null>): number | null {
  const available = values.filter((value): value is number => value !== null);
  return available.length ? available.reduce((total, value) => total + value, 0) : null;
}

function average(values: Array<number | null>): number | null {
  const available = values.filter((value): value is number => value !== null);
  return available.length
    ? available.reduce((total, value) => total + value, 0) / available.length
    : null;
}

export function linkedInContentTotals(content: DashboardContent[]) {
  return {
    impressions: sum(content.map((item) => item.views)),
    uniqueImpressions: sum(content.map((item) => item.reach)),
    engagements: sum(content.map((item) => item.interactions)),
    clicks: sum(content.map((item) => item.clicks_count)),
    likes: sum(content.map((item) => item.likes_count)),
    comments: sum(content.map((item) => item.comments_count)),
    shares: sum(content.map((item) => item.shares_count)),
  };
}

function metricKpi(
  data: PlatformDashboard,
  id: MetricId,
  label: string,
  icon: PulseKpi["icon"],
  color: string,
  fallback: number | null = null,
): PulseKpi {
  const current = metric(data, id);
  return {
    id,
    label,
    value: current?.value ?? fallback,
    delta: current?.delta_pct ?? null,
    icon,
    color,
    unit: current?.unit,
  };
}

function pageKpis(data: PlatformDashboard): PulseKpi[] {
  const totals = linkedInContentTotals(data.content);
  return [
    metricKpi(data, "followers", "Followers", Users, "#0a66c2"),
    metricKpi(data, "follower_gains", "Follower Gains", TrendingUp, "#14b8a6"),
    metricKpi(data, "views", "Post Impressions", Eye, "#378fe9", totals.impressions),
    metricKpi(data, "reach", "Unique Impressions", Users, "#8b5cf6", totals.uniqueImpressions),
    metricKpi(data, "page_views", "Page Views", Eye, "#ec4899"),
    metricKpi(data, "engagement_rate", "Engagement Rate", Activity, "#f59e0b"),
  ];
}

function contentKpis(data: PlatformDashboard): PulseKpi[] {
  const totals = linkedInContentTotals(data.content);
  return [
    metricKpi(data, "views", "Impressions", Eye, "#378fe9", totals.impressions),
    metricKpi(data, "reach", "Unique Impressions", Users, "#8b5cf6", totals.uniqueImpressions),
    metricKpi(data, "interactions", "Engagements", Activity, "#f59e0b", totals.engagements),
    metricKpi(data, "clicks", "Clicks", MousePointerClick, "#14b8a6", totals.clicks),
    { id: "linkedin_posts", label: "Published Posts", value: data.content_summary.total, delta: null, icon: FileText, color: "#5e5e5e" },
    metricKpi(data, "engagement_rate", "Engagement Rate", TrendingUp, "#0a66c2"),
  ];
}

function format(value: number | null, digits = 0): string {
  return value === null
    ? "—"
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(value);
}

function contentTypeRows(content: DashboardContent[]) {
  const types = [...new Set(content.map((item) => item.content_type.toLowerCase()))].sort();
  return types.map((type) => {
    const posts = content.filter((item) => item.content_type.toLowerCase() === type);
    const impressions = sum(posts.map((item) => item.views));
    const engagements = sum(posts.map((item) => item.interactions));
    const clicks = sum(posts.map((item) => item.clicks_count));
    const rate = impressions && impressions > 0 && engagements !== null
      ? engagements / impressions
      : null;
    return [
      humanize(type),
      posts.length,
      format(impressions),
      format(engagements),
      format(clicks),
      rate === null ? "—" : `${(rate * 100).toFixed(1)}%`,
    ];
  });
}

function engagementRows(content: DashboardContent[]): PieRow[] {
  const totals = linkedInContentTotals(content);
  return [
    { label: "Clicks", value: totals.clicks, color: "#14b8a6" },
    { label: "Likes", value: totals.likes, color: V1_CHART_COLORS.likes },
    { label: "Comments", value: totals.comments, color: V1_CHART_COLORS.comments },
    { label: "Shares", value: totals.shares, color: V1_CHART_COLORS.shares },
  ].flatMap((item) => item.value !== null && item.value > 0
    ? [{ ...item, value: item.value }]
    : []);
}

function breakdownRows(
  breakdowns: DashboardBreakdown[],
  dimension: "association_type" | "staff_count",
): PieRow[] {
  const breakdown = breakdowns.find((item) => item.dimension === dimension);
  return breakdown?.items
    .filter((item) => item.value > 0)
    .map((item, index) => ({
      label: humanize(item.key),
      value: item.value,
      color: LINKEDIN_COLORS[index % LINKEDIN_COLORS.length] ?? "#64748b",
    })) ?? [];
}

function PageSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Company Page</SectionTitle>}
      <KpiGrid rows={pageKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: "#0a66c2" }]} localZoom subtitle="Company Page follower snapshots" title="Followers Trend" />
        <PulseTrendCard bar data={data} keys={[{ id: "follower_gains", label: "Follower Gains", color: "#14b8a6" }]} subtitle="Organic and paid follower gains returned by LinkedIn" title="Follower Gains" />
      </div>
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "views", label: "Impressions", color: "#378fe9" }, { id: "reach", label: "Unique Impressions", color: "#8b5cf6" }]} subtitle="Daily organic Company Page post delivery" title="Post Visibility" />
        <PulseTrendCard data={data} keys={[{ id: "page_views", label: "Page Views", color: "#ec4899" }, { id: "clicks", label: "Post Clicks", color: "#14b8a6" }]} subtitle="Daily Company Page views and organic post clicks" title="Page & Post Actions" />
      </div>
    </section>
  );
}

function ContentSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  const totals = linkedInContentTotals(data.content);
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Posts</SectionTitle>}
      <KpiGrid rows={contentKpis(data)} />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={summaryPieRows(data.content_summary.by_type, LINKEDIN_COLORS)} subtitle="Published Company Page posts by format" title="Post Type" />
        <PulseTrendCard data={data} keys={[{ id: "views", label: "Impressions", color: "#378fe9" }, { id: "interactions", label: "Engagements", color: "#f59e0b" }, { id: "clicks", label: "Clicks", color: "#14b8a6" }]} subtitle="Daily organic post results returned by LinkedIn" title="Post Performance" />
      </div>
      <div className="facebook-two-three-grid">
        <SimplePulseTable columns={["Type", "Posts", "Impressions", "Engagements", "Clicks", "Engagement Rate"]} emptyCopy="No Company Page post formats were collected in this period." rows={contentTypeRows(data.content)} subtitle="Observed performance by LinkedIn post format" title="Content Type Performance" />
        <SimplePulseTable columns={["Metric", "Average"]} rows={[
          ["Avg. Impressions per Post", format(average(data.content.map((item) => item.views)), 1)],
          ["Avg. Unique Impressions per Post", format(average(data.content.map((item) => item.reach)), 1)],
          ["Avg. Engagements per Post", format(average(data.content.map((item) => item.interactions)), 1)],
          ["Avg. Clicks per Post", format(average(data.content.map((item) => item.clicks_count)), 1)],
        ]} subtitle="Average across posts where each metric is available" title="Per-post Averages" />
      </div>
      <div className="facebook-two-grid">
        <PulsePieCard rows={engagementRows(data.content)} subtitle="Clicks, likes, comments and shares on organic posts" title="Engagement Split" />
        <SimplePulseTable columns={["Metric", "Total"]} rows={[
          ["Impressions", format(totals.impressions)],
          ["Unique Impressions", format(totals.uniqueImpressions)],
          ["Engagements", format(totals.engagements)],
          ["Clicks", format(totals.clicks)],
        ]} subtitle="Totals from the currently loaded Company Page posts" title="Collected Post Totals" />
      </div>
      <PerformingContentTable content={data.content} variant="linkedin" />
    </section>
  );
}

function AudienceSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Follower Audience</SectionTitle>}
      <KpiGrid rows={pageKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: "#0a66c2" }]} localZoom subtitle="Company Page follower snapshots" title="Followers Trend" />
        <PulseTrendCard bar data={data} keys={[{ id: "follower_gains", label: "Follower Gains", color: "#14b8a6" }]} subtitle="Daily follower gains returned by LinkedIn" title="Follower Growth" />
      </div>
      <div className="facebook-two-grid">
        <PulsePieCard rows={breakdownRows(data.breakdowns, "staff_count")} subtitle="Supported LinkedIn follower facet" title="Followers by Company Size" />
        <PulsePieCard rows={breakdownRows(data.breakdowns, "association_type")} subtitle="Supported LinkedIn follower facet" title="Followers by Association" />
      </div>
    </section>
  );
}

export function LinkedInPulseDashboard({ data, tab }: { data: PlatformDashboard; tab: LinkedInTab }) {
  const cover = tab === "cover";
  return (
    <div className="facebook-pulse-dashboard linkedin-pulse-dashboard">
      {(tab === "page" || cover) && <PageSection data={data} withTitle={cover} />}
      {(tab === "content" || cover) && <ContentSection data={data} withTitle={cover} />}
      {(tab === "audience" || cover) && <AudienceSection data={data} withTitle={cover} />}
    </div>
  );
}
