import {
  Activity,
  Eye,
  Film,
  Heart,
  MessageCircle,
  Play,
  Share2,
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
import { AudienceDemographicsCard } from "../dashboard/AudienceDemographicsCard";
import {
  V1_CHART_COLORS,
  V1_FOLLOWER_FLOW_KEYS,
  followerFlowSubtitle,
} from "../dashboard/visualPalette";
import {
  CommunityTables,
  KpiGrid,
  PerformingContentTable,
  PulseHeatmapCard,
  PulsePieCard,
  PulseTrendCard,
  SectionTitle,
  SimplePulseTable,
  breakdownRows,
  countryBreakdownRows,
  derivedContentTotals,
  hashtagRows,
  sentimentPieRows,
  summaryPieRows,
  type PulseKpi,
} from "../facebook/FacebookPulseDashboard";
import { WorldMapWidget } from "../instagram/InstagramPulseDashboard";

type TikTokTab = "account" | "audience" | "content" | "cover";
type PieRow = { label: string; value: number; color: string };

const TIKTOK_COLORS = ["#25f4ee", "#fe2c55", "#8b5cf6", "#f59e0b", "#14b8a6", "#3b82f6"];
function metric(data: PlatformDashboard, id: MetricId): DashboardMetric | undefined {
  return data.metrics.find((item) => item.metric_id === id);
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

function followerGrowthKpi(data: PlatformDashboard): PulseKpi {
  const current = metric(data, "new_followers");
  return {
    id: "new_followers",
    label: "Follower Growth",
    value: current?.value ?? null,
    delta: current?.delta_pct ?? null,
    icon: Users,
    color: "#14b8a6",
    unit: "count",
  };
}

function accountKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    metricKpi(data, "followers", "Followers", Users, V1_CHART_COLORS.followers),
    followerGrowthKpi(data),
    metricKpi(data, "video_views_total", "Video Views", Play, "#ec4899"),
    metricKpi(data, "reach", "Reach", Eye, "#8b5cf6"),
    metricKpi(data, "video_engagements_total", "Total Interactions", Activity, "#f59e0b"),
    metricKpi(data, "video_engagement_rate", "Engagement Rate", TrendingUp, "#6366f1"),
  ];
}

function contentKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    metricKpi(data, "video_views_total", "Video Views", Eye, "#ec4899"),
    metricKpi(data, "reach", "Reach", Eye, "#8b5cf6"),
    metricKpi(data, "video_likes_total", "Likes", Heart, V1_CHART_COLORS.likes),
    metricKpi(data, "video_comments_total", "Comments", MessageCircle, "#3b82f6"),
    metricKpi(data, "video_shares_total", "Shares", Share2, "#22c55e"),
    metricKpi(data, "video_engagement_rate", "Engagement Rate", TrendingUp, "#6366f1"),
  ];
}

function audienceKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    metricKpi(data, "followers", "Followers", Users, V1_CHART_COLORS.followers),
    followerGrowthKpi(data),
    metricKpi(data, "video_views_total", "Video Views", Eye, "#ec4899"),
    metricKpi(data, "reach", "Reach", Activity, "#8b5cf6"),
    metricKpi(data, "profile_views", "Profile Views", Eye, "#3b82f6"),
    metricKpi(data, "video_engagement_rate", "Engagement Rate", TrendingUp, "#6366f1"),
  ];
}

function metricPie(data: PlatformDashboard, definitions: Array<{ id: MetricId; label: string; color: string }>): PieRow[] {
  return definitions.flatMap((definition) => {
    const value = metric(data, definition.id)?.value;
    return value !== null && value !== undefined && value > 0
      ? [{ label: definition.label, value, color: definition.color }]
      : [];
  });
}

function contentEngagementRows(content: DashboardContent[]): PieRow[] {
  const totals = derivedContentTotals(content);
  return [
    { label: "Likes", value: totals.likes, color: V1_CHART_COLORS.likes },
    { label: "Comments", value: totals.comments, color: V1_CHART_COLORS.comments },
    { label: "Shares", value: totals.shares, color: V1_CHART_COLORS.shares },
  ].filter((item) => item.value > 0);
}

function findBreakdown(breakdowns: DashboardBreakdown[], hint: string): DashboardBreakdown | undefined {
  return breakdowns.find((item) => item.dimension.toLowerCase().includes(hint));
}

function AccountSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Overview</SectionTitle>}
      <KpiGrid rows={accountKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: V1_CHART_COLORS.followers }]} localZoom subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard data={data} keys={[...V1_FOLLOWER_FLOW_KEYS]} subtitle={followerFlowSubtitle(data)} title="New Followers Trend" />
      </div>
      <PulseTrendCard bar data={data} keys={[{ id: "reach", label: "Video Reach", color: V1_CHART_COLORS.reach }, { id: "views", label: "Video Views", color: V1_CHART_COLORS.views }]} subtitle="Daily reach and views across the selected period" title="Performance Trends" wide />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={metricPie(data, [{ id: "video_views_total", label: "Organic Views", color: V1_CHART_COLORS.organic }])} subtitle="Collected video views" title="Video View Type" />
        <PulseTrendCard data={data} keys={[{ id: "views", label: "Organic Views", color: V1_CHART_COLORS.organicViews }]} subtitle="Daily views across the selected period" title="Views Source Trend" />
      </div>
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={metricPie(data, [{ id: "reach", label: "Organic Reach", color: V1_CHART_COLORS.organic }])} subtitle="Organic reach when available" title="Reach Distribution" />
        <PulseTrendCard data={data} keys={[{ id: "reach", label: "Organic Reach", color: V1_CHART_COLORS.organicReach }]} subtitle="Organic reach when available" title="Reach Source Trend" />
      </div>
    </section>
  );
}

function ContentSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Content</SectionTitle>}
      <KpiGrid rows={contentKpis(data)} />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={summaryPieRows(data.content_summary.by_type, TIKTOK_COLORS)} subtitle="Content type breakdown" title="Content Type" />
        <PulseTrendCard data={data} keys={[{ id: "views", label: "Video Views", color: V1_CHART_COLORS.views }, { id: "reach", label: "Video Reach", color: V1_CHART_COLORS.reach }]} subtitle="Daily video views and reach" title="Views & Reach Trend" />
      </div>
      <div className="facebook-two-three-grid">
        <PulseTrendCard data={data} keys={[{ id: "video_likes_total", label: "Likes", color: V1_CHART_COLORS.likes }, { id: "video_comments_total", label: "Comments", color: V1_CHART_COLORS.comments }, { id: "video_shares_total", label: "Shares", color: V1_CHART_COLORS.shares }]} subtitle="Likes, comments and shares over time" title="Interaction Trend" />
        <PulsePieCard legendColumns={3} rows={contentEngagementRows(data.content)} subtitle="Interaction mix" title="Engagement Split" />
      </div>
      <div className="facebook-three-grid">
        <PulsePieCard rows={summaryPieRows(data.content_summary.reach_by_type, TIKTOK_COLORS)} subtitle="Reach distribution by content type" title="Content Type Reach" />
        <PulsePieCard rows={sentimentPieRows(data.breakdowns)} subtitle="Classified comment distribution" title="Comment Sentiment" />
        <SimplePulseTable columns={["Hashtag", "Count"]} emptyCopy="No hashtags in collected captions." rows={hashtagRows(data)} subtitle="Hashtags found in collected captions" title="Top Hashtags" />
      </div>
      <PerformingContentTable content={data.content} />
    </section>
  );
}

function AudienceSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  const countries = findBreakdown(data.breakdowns, "country");
  const organicReachId: MetricId = data.series.some((item) => item.metric_id === "reach_organic")
    ? "reach_organic"
    : "reach";
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Audience</SectionTitle>}
      <KpiGrid rows={audienceKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: V1_CHART_COLORS.followers }]} localZoom subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard data={data} keys={[...V1_FOLLOWER_FLOW_KEYS]} subtitle={followerFlowSubtitle(data)} title="New Followers Trend" />
      </div>
      <div className="facebook-two-grid">
        <AudienceDemographicsCard breakdowns={data.breakdowns} />
        <WorldMapWidget breakdown={countries} />
      </div>
      <div className="facebook-two-grid">
        <PulseHeatmapCard breakdowns={data.breakdowns} />
        <PulseTrendCard data={data} keys={[{ id: organicReachId, label: "Organic Reach", color: "#8b5cf6" }]} subtitle="Organic delivery trend" title="Organic Reach Trend" />
      </div>
      <div className="facebook-two-grid">
        <SimplePulseTable columns={["#", "Country", "Value"]} rows={countryBreakdownRows(data.breakdowns)} subtitle="Country ranking" title="Top Countries" />
        <SimplePulseTable columns={["#", "Age group", "Value"]} rows={breakdownRows(data.breakdowns, "age")} subtitle="TikTok audience age ranking" title="Age Groups" />
      </div>
      <CommunityTables data={data} platform="tiktok" />
    </section>
  );
}

export function TikTokPulseDashboard({ data, tab }: { data: PlatformDashboard; tab: TikTokTab }) {
  const cover = tab === "cover";
  return (
    <div className="facebook-pulse-dashboard tiktok-pulse-dashboard">
      {(tab === "account" || cover) && <AccountSection data={data} withTitle={cover} />}
      {(tab === "content" || cover) && <ContentSection data={data} withTitle={cover} />}
      {(tab === "audience" || cover) && <AudienceSection data={data} withTitle={cover} />}
    </div>
  );
}
