import {
  Activity,
  Eye,
  Film,
  Heart,
  MessageCircle,
  Play,
  Share2,
  TrendingUp,
  UserPlus,
  Users,
} from "lucide-react";

import type { DashboardBreakdown, DashboardContent, DashboardMetric, MetricId, PlatformDashboard } from "../../api";
import {
  ContentWinners,
  KpiGrid,
  PulseEmpty,
  PulsePieCard,
  PulseTrendCard,
  SimplePulseTable,
  breakdownRows,
  derivedContentTotals,
  type PulseKpi,
} from "../facebook/FacebookPulseDashboard";
import { formatDate, formatNumber, humanize } from "../dashboard/format";

type TikTokTab = "overview" | "videos" | "audience";
type PieRow = { label: string; value: number; color: string };

const TIKTOK_COLORS = ["#111827", "#25f4ee", "#fe2c55", "#8b5cf6", "#f59e0b", "#14b8a6"];

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

function overviewKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    metricKpi(data, "followers", "Followers", Users, "#25f4ee"),
    metricKpi(data, "video_views_total", "Video Views", Play, "#fe2c55"),
    metricKpi(data, "video_likes_total", "Video Likes", Heart, "#ef4444"),
    metricKpi(data, "video_comments_total", "Video Comments", MessageCircle, "#3b82f6"),
    metricKpi(data, "video_shares_total", "Video Shares", Share2, "#22c55e"),
    metricKpi(data, "video_engagement_rate", "Engagement Rate", TrendingUp, "#8b5cf6"),
  ];
}

function videoKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    { id: "videos", label: "Total Videos", value: data.content.length, delta: null, icon: Film, color: "#111827" },
    metricKpi(data, "video_views_total", "Video Views", Eye, "#fe2c55"),
    metricKpi(data, "video_likes_total", "Likes", Heart, "#ef4444"),
    metricKpi(data, "video_comments_total", "Comments", MessageCircle, "#3b82f6"),
    metricKpi(data, "video_shares_total", "Shares", Share2, "#22c55e"),
    metricKpi(data, "video_engagements_total", "Engagements", Activity, "#8b5cf6"),
  ];
}

function audienceKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    metricKpi(data, "followers", "Followers", Users, "#25f4ee"),
    metricKpi(data, "following", "Following", UserPlus, "#fe2c55"),
    metricKpi(data, "new_followers", "New Followers", Users, "#14b8a6"),
    metricKpi(data, "video_views_total", "Video Views", Eye, "#f59e0b"),
    metricKpi(data, "video_engagements_total", "Engagements", Activity, "#3b82f6"),
    metricKpi(data, "video_engagement_rate", "Engagement Rate", TrendingUp, "#8b5cf6"),
  ];
}

function engagementRows(data: PlatformDashboard): PieRow[] {
  const definitions: Array<{ id: MetricId; label: string; color: string }> = [
    { id: "video_likes_total", label: "Likes", color: "#fe2c55" },
    { id: "video_comments_total", label: "Comments", color: "#3b82f6" },
    { id: "video_shares_total", label: "Shares", color: "#25f4ee" },
  ];
  return definitions.flatMap((row) => {
    const value = metric(data, row.id)?.value;
    return value !== null && value !== undefined && value > 0 ? [{ label: row.label, value, color: row.color }] : [];
  });
}

function contentEngagementRows(content: DashboardContent[]): PieRow[] {
  const totals = derivedContentTotals(content);
  return [
    { label: "Likes", value: totals.likes, color: "#fe2c55" },
    { label: "Comments", value: totals.comments, color: "#3b82f6" },
    { label: "Shares", value: totals.shares, color: "#25f4ee" },
  ].filter((item) => item.value > 0);
}

function contentTypeRows(content: DashboardContent[]): PieRow[] {
  const counts = new Map<string, number>();
  content.forEach((item) => {
    const label = humanize(item.content_type);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  });
  return Array.from(counts.entries()).map(([label, value], index) => ({ label, value, color: TIKTOK_COLORS[index % TIKTOK_COLORS.length] ?? "#64748b" }));
}

function breakdownPie(breakdowns: DashboardBreakdown[], hints: string[]): PieRow[] {
  const breakdown = breakdowns.find((item) => {
    const key = `${item.dimension} ${item.metric_id}`.toLowerCase();
    return hints.some((hint) => key.includes(hint));
  });
  return breakdown?.items.slice(0, 8).map((item, index) => ({
    label: humanize(item.key),
    value: item.value,
    color: TIKTOK_COLORS[index % TIKTOK_COLORS.length] ?? "#64748b",
  })) ?? [];
}

function EmptyMetricCard({ title, subtitle, copy }: { title: string; subtitle: string; copy: string }) {
  return (
    <article className="facebook-pulse-card facebook-trend-card">
      <div className="facebook-pulse-card-heading"><h3>{title}</h3><p>{subtitle}</p></div>
      <PulseEmpty copy={copy} />
    </article>
  );
}

function TikTokVideoTable({ content }: { content: DashboardContent[] }) {
  const rows = [...content].sort((left, right) => right.interactions - left.interactions);
  return (
    <article className="facebook-pulse-table-card tiktok-video-table">
      <div className="facebook-table-title"><div><h3>All Videos</h3><p>Video-level engagement from the selected date range</p></div><span>Video Performance</span></div>
      <div className="facebook-table-scroll"><table><thead><tr><th>#</th><th>Video</th><th>Date</th><th>Type</th><th>Views</th><th>Likes</th><th>Comments</th><th>Shares</th><th>Interactions</th><th>Original</th></tr></thead><tbody>
        {rows.length === 0 ? <tr><td colSpan={10}>No video data</td></tr> : rows.map((item, index) => (
          <tr key={`${item.account_id}-${item.external_content_id}`}>
            <td>{index + 1}</td>
            <td><span className="facebook-caption" title={item.message}>{item.message || "Caption unavailable"}</span></td>
            <td>{item.published_at ? formatDate(item.published_at) : "—"}</td>
            <td><span className="facebook-type-chip">{humanize(item.content_type)}</span></td>
            <td>—</td>
            <td>{formatNumber(item.likes_count)}</td>
            <td>{formatNumber(item.comments_count)}</td>
            <td>{formatNumber(item.shares_count)}</td>
            <td><strong>{formatNumber(item.interactions)}</strong></td>
            <td>{item.permalink ? <a className="tiktok-video-link" href={item.permalink} rel="noreferrer" target="_blank">View</a> : "—"}</td>
          </tr>
        ))}
      </tbody></table></div>
      <p className="tiktok-table-note">Video-level view counts are not exposed by the current dashboard response; aggregate Video Views remain available above.</p>
    </article>
  );
}

function OverviewSection({ data }: { data: PlatformDashboard }) {
  return (
    <section className="facebook-pulse-section">
      <KpiGrid rows={overviewKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: "#25f4ee" }]} subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard data={data} keys={[{ id: "video_views_total", label: "Video Views", color: "#fe2c55" }]} subtitle="Cumulative video view trajectory" title="Video Views Trend" />
      </div>
      <PulseTrendCard bar data={data} keys={[{ id: "video_views_total", label: "Video Views", color: "#111827" }, { id: "video_engagements_total", label: "Engagements", color: "#25f4ee" }]} subtitle="Video views and supported engagement totals" title="Video Performance Trends" wide />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={engagementRows(data)} subtitle="Likes, comments and shares" title="Video Engagement Mix" />
        <PulseTrendCard data={data} keys={[{ id: "video_likes_total", label: "Likes", color: "#fe2c55" }, { id: "video_comments_total", label: "Comments", color: "#3b82f6" }, { id: "video_shares_total", label: "Shares", color: "#25f4ee" }]} subtitle="Supported cumulative engagement signals" title="Engagement Trends" />
      </div>
    </section>
  );
}

function VideosSection({ data }: { data: PlatformDashboard }) {
  return (
    <section className="facebook-pulse-section">
      <KpiGrid rows={videoKpis(data)} />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={contentTypeRows(data.content)} subtitle="Published formats in this range" title="Video Type" />
        <PulseTrendCard data={data} keys={[{ id: "video_views_total", label: "Video Views", color: "#fe2c55" }]} subtitle="Aggregate video-view movement" title="Video Views Trend" />
      </div>
      <div className="facebook-two-three-grid">
        <PulseTrendCard data={data} keys={[{ id: "video_engagements_total", label: "Engagements", color: "#8b5cf6" }]} subtitle="Likes, comments and shares combined" title="Video Engagements Trend" />
        <PulsePieCard rows={contentEngagementRows(data.content)} subtitle="Visible video-row engagement" title="Content Engagement Split" />
      </div>
      <TikTokVideoTable content={data.content} />
      <ContentWinners content={data.content} />
    </section>
  );
}

function AudienceSection({ data }: { data: PlatformDashboard }) {
  const audienceRows = breakdownPie(data.breakdowns, ["age", "gender"]);
  return (
    <section className="facebook-pulse-section">
      <KpiGrid rows={audienceKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: "#25f4ee" }]} subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard data={data} keys={[{ id: "new_followers", label: "New Followers", color: "#fe2c55" }]} subtitle="Net new-follower movement" title="New Followers Trend" />
      </div>
      <div className="facebook-two-grid">
        <PulsePieCard rows={audienceRows} subtitle="Supported age and gender breakdown" title="Audience Demographics" />
        <EmptyMetricCard copy="The reporting contract does not return hourly TikTok audience activity." subtitle="Hourly audience activity" title="Best Time to Engage" />
      </div>
      <div className="facebook-two-grid">
        <SimplePulseTable columns={["#", "Country", "Value"]} rows={breakdownRows(data.breakdowns, "country")} subtitle="Country ranking" title="Top Countries" />
        <SimplePulseTable columns={["#", "City", "Value"]} rows={breakdownRows(data.breakdowns, "city")} subtitle="City ranking" title="Top Cities" />
      </div>
    </section>
  );
}

export function TikTokPulseDashboard({ data, tab }: { data: PlatformDashboard; tab: TikTokTab }) {
  return (
    <div className="facebook-pulse-dashboard tiktok-pulse-dashboard">
      {tab === "overview" && <OverviewSection data={data} />}
      {tab === "videos" && <VideosSection data={data} />}
      {tab === "audience" && <AudienceSection data={data} />}
    </div>
  );
}
