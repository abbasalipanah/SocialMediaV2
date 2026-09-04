import {
  Activity,
  Clock3,
  Eye,
  Gauge,
  MessageCircle,
  PlayCircle,
  ThumbsUp,
  TrendingUp,
  UserMinus,
  Users,
  Video,
} from "lucide-react";
import type { ReactNode } from "react";

import type {
  DashboardBreakdown,
  DashboardContent,
  DashboardMetric,
  MetricId,
  PlatformDashboard,
} from "../../api";
import { HonestEmpty } from "../dashboard/DashboardCards";
import { CountryTableLabel } from "../dashboard/countryPresentation";
import { humanize } from "../dashboard/format";
import { V1_CHART_COLORS } from "../dashboard/visualPalette";
import {
  KpiGrid,
  PerformingContentTable,
  PulsePieCard,
  PulseTrendCard,
  SectionTitle,
  SimplePulseTable,
  type PieRow,
  type PulseKpi,
} from "../facebook/FacebookPulseDashboard";

type YouTubeTab = "account" | "cover" | "content" | "audience";

const YOUTUBE_RED = "#ff0033";
const YOUTUBE_COLORS = [YOUTUBE_RED, "#8b5cf6", "#0ea5e9", "#14b8a6", "#f59e0b", "#ec4899"];

const BREAKDOWN_LABELS: Record<string, string> = {
  ADVERTISING: "YouTube Advertising",
  BROWSE: "Browse Features",
  CHANNEL: "Channel Pages",
  CORE: "YouTube",
  DESKTOP: "Desktop",
  END_SCREEN: "End Screens",
  EMBEDDED: "Embedded Players",
  EXTERNAL_APP: "External Apps",
  EXT_URL: "External",
  GAME_CONSOLE: "Game Console",
  LIVE: "Live",
  MOBILE: "Mobile",
  MUSIC: "YouTube Music",
  NOTIFICATION: "Notifications",
  NO_LINK_OTHER: "Direct or Unknown",
  PLAYLIST: "Playlists",
  RELATED_VIDEO: "Suggested Videos",
  SHORTS: "Shorts",
  SEARCH: "YouTube Search",
  SUBSCRIBED: "Subscribed",
  TABLET: "Tablet",
  TV: "TV",
  UNSUBSCRIBED: "Not Subscribed",
  VIDEO_ON_DEMAND: "Videos",
  WATCH: "Watch Pages",
  YT_CHANNEL: "Channel Pages",
  YT_OTHER_PAGE: "Other YouTube Features",
  YT_SEARCH: "YouTube Search",
};

const AGE_LABELS: Record<string, string> = {
  "age13-17": "13–17",
  "age18-24": "18–24",
  "age25-34": "25–34",
  "age35-44": "35–44",
  "age45-54": "45–54",
  "age55-64": "55–64",
  "age65-": "65+",
};

function metric(data: PlatformDashboard, id: MetricId): DashboardMetric | undefined {
  return data.metrics.find((item) => item.metric_id === id);
}

function availableSum(values: Array<number | null>): number | null {
  const available = values.filter((value): value is number => value !== null);
  return available.length ? available.reduce((total, value) => total + value, 0) : null;
}

function availableAverage(values: Array<number | null>): number | null {
  const available = values.filter((value): value is number => value !== null);
  return available.length
    ? available.reduce((total, value) => total + value, 0) / available.length
    : null;
}

export function youtubeContentTotals(content: DashboardContent[]) {
  const views = availableSum(content.map((item) => item.views));
  const likes = availableSum(content.map((item) => item.likes_count));
  const comments = availableSum(content.map((item) => item.comments_count));
  const interactions = availableSum(content.map((item) => item.interactions));
  return {
    views,
    likes,
    comments,
    interactions,
    averageViews: availableAverage(content.map((item) => item.views)),
    engagementRate: views !== null && views > 0 && interactions !== null
      ? interactions / views
      : null,
  };
}

function metricKpi(
  data: PlatformDashboard,
  id: MetricId,
  label: string,
  icon: PulseKpi["icon"],
  color: string,
  transform: (value: number) => number = (value) => value,
  unit?: PulseKpi["unit"],
): PulseKpi {
  const current = metric(data, id);
  return {
    id,
    label,
    value: current?.value === null || current?.value === undefined
      ? null
      : transform(current.value),
    delta: current?.delta_pct ?? null,
    icon,
    color,
    unit,
  };
}

function channelKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    metricKpi(data, "followers", "Subscribers", Users, YOUTUBE_RED),
    metricKpi(data, "views", "Views", Eye, "#0ea5e9"),
    metricKpi(data, "engaged_views", "Engaged Views", PlayCircle, "#8b5cf6"),
    metricKpi(data, "watch_time_minutes", "Watch Time (hours)", Clock3, "#14b8a6", (value) => value / 60),
    metricKpi(data, "follows", "Subscribers Gained", TrendingUp, "#22c55e"),
    metricKpi(data, "engagement_rate", "Engagement Rate", Activity, "#f59e0b", (value) => value, "ratio"),
  ];
}

function audienceKpis(data: PlatformDashboard): PulseKpi[] {
  const views = metric(data, "views");
  const watchTime = metric(data, "watch_time_minutes");
  const averageViewDuration = views?.value && watchTime?.value !== null && watchTime?.value !== undefined
    ? (watchTime.value * 60) / views.value
    : null;
  return [
    metricKpi(data, "views", "Audience Views", Eye, "#0ea5e9"),
    metricKpi(data, "engaged_views", "Engaged Views", PlayCircle, "#8b5cf6"),
    metricKpi(data, "watch_time_minutes", "Watch Time (hours)", Clock3, "#14b8a6", (value) => value / 60),
    { id: "youtube_average_view_duration", label: "Avg. View Duration (sec)", value: averageViewDuration, delta: null, icon: Gauge, color: "#f59e0b" },
    metricKpi(data, "follows", "Subscribers Gained", TrendingUp, "#22c55e"),
    metricKpi(data, "unfollows", "Subscribers Lost", UserMinus, "#ef4444"),
  ];
}

function contentKpis(data: PlatformDashboard): PulseKpi[] {
  const totals = youtubeContentTotals(data.content);
  return [
    { id: "youtube_video_count", label: "Published Videos", value: data.content_summary.total, delta: null, icon: Video, color: YOUTUBE_RED },
    { id: "youtube_video_views", label: "Video Views", value: totals.views, delta: data.content_metrics.views.delta_pct, icon: Eye, color: "#0ea5e9" },
    { id: "youtube_video_likes", label: "Likes", value: totals.likes, delta: data.content_metrics.likes.delta_pct, icon: ThumbsUp, color: "#ec4899" },
    { id: "youtube_video_comments", label: "Comments", value: totals.comments, delta: data.content_metrics.comments.delta_pct, icon: MessageCircle, color: "#8b5cf6" },
    { id: "youtube_average_views", label: "Avg. Views per Video", value: totals.averageViews, delta: null, icon: PlayCircle, color: "#14b8a6" },
    { id: "youtube_content_engagement", label: "Visible Engagement Rate", value: totals.engagementRate, delta: data.content_metrics.engagement_rate.delta_pct, icon: Activity, color: "#f59e0b", unit: "ratio" },
  ];
}

function exactBreakdown(
  breakdowns: DashboardBreakdown[],
  dimension: string,
  metricId: MetricId = "views",
): DashboardBreakdown | undefined {
  return breakdowns.find(
    (item) => item.dimension === dimension && item.metric_id === metricId,
  );
}

function displayBreakdownLabel(value: string): string {
  return AGE_LABELS[value] ?? BREAKDOWN_LABELS[value] ?? humanize(value);
}

function pieRows(
  breakdowns: DashboardBreakdown[],
  dimension: string,
  metricId: MetricId = "views",
): PieRow[] {
  return exactBreakdown(breakdowns, dimension, metricId)?.items
    .filter((item) => item.value > 0)
    .map((item, index) => ({
      label: displayBreakdownLabel(item.key),
      value: item.value,
      color: YOUTUBE_COLORS[index % YOUTUBE_COLORS.length] ?? "#64748b",
    })) ?? [];
}

function tableRows(
  breakdowns: DashboardBreakdown[],
  dimension: string,
  metricId: MetricId = "views",
): Array<Array<ReactNode>> {
  return exactBreakdown(breakdowns, dimension, metricId)?.items
    .filter((item) => item.value > 0)
    .slice(0, 10)
    .map((item, index) => [
      index + 1,
      displayBreakdownLabel(item.key),
      new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(item.value),
      item.percentage === null ? "—" : `${item.percentage.toFixed(1)}%`,
    ]) ?? [];
}

function countryRows(breakdowns: DashboardBreakdown[]): Array<Array<ReactNode>> {
  return exactBreakdown(breakdowns, "youtube_country")?.items
    .filter((item) => item.value > 0)
    .slice(0, 10)
    .map((item, index) => [
      index + 1,
      <CountryTableLabel key={item.key} value={item.key} />,
      new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(item.value),
      item.percentage === null ? "—" : `${item.percentage.toFixed(1)}%`,
    ]) ?? [];
}

function engagementRows(data: PlatformDashboard): PieRow[] {
  return [
    { id: "video_likes_daily" as const, label: "Likes", color: V1_CHART_COLORS.likes },
    { id: "video_comments_daily" as const, label: "Comments", color: V1_CHART_COLORS.comments },
    { id: "video_shares_daily" as const, label: "Shares", color: V1_CHART_COLORS.shares },
  ].flatMap(({ id, label, color }) => {
    const value = metric(data, id)?.value;
    return value !== null && value !== undefined && value > 0 ? [{ label, value, color }] : [];
  });
}

function ChannelSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Channel Overview</SectionTitle>}
      <KpiGrid rows={channelKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "views", label: "Views", color: YOUTUBE_RED }, { id: "engaged_views", label: "Engaged Views", color: "#8b5cf6" }]} subtitle="Daily channel views; engaged views remain comparable across Shorts counting changes" title="Views & Engaged Views" />
        <PulseTrendCard bar data={data} keys={[{ id: "watch_time_minutes", label: "Watch Time (min)", color: "#14b8a6" }]} subtitle="Estimated minutes watched each day" title="Watch Time" />
      </div>
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "follows", label: "Gained", color: "#22c55e" }, { id: "unfollows", label: "Lost", color: "#ef4444" }]} subtitle="Daily subscriber gains and losses" title="Subscriber Movement" />
        <PulseTrendCard data={data} keys={[{ id: "video_likes_daily", label: "Likes", color: V1_CHART_COLORS.likes }, { id: "video_comments_daily", label: "Comments", color: V1_CHART_COLORS.comments }, { id: "video_shares_daily", label: "Shares", color: V1_CHART_COLORS.shares }]} subtitle="Daily engagement actions returned by YouTube Analytics" title="Engagement Activity" />
      </div>
      <div className="facebook-one-three-grid">
        <PulsePieCard legendColumns={3} rows={engagementRows(data)} subtitle="Likes, comments and shares in the selected period" title="Engagement Split" />
        <PulseTrendCard data={data} keys={[{ id: "playlist_additions", label: "Added", color: "#22c55e" }, { id: "playlist_removals", label: "Removed", color: "#ef4444" }]} subtitle="Videos added to and removed from viewer playlists" title="Playlist Activity" />
      </div>
    </section>
  );
}

function ContentSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  const contentType = pieRows(data.breakdowns, "youtube_content_type");
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Videos</SectionTitle>}
      <KpiGrid rows={contentKpis(data)} />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={contentType} subtitle="Selected-period views across Videos, Shorts and Live" title="Content Type Performance" />
        <PulseTrendCard data={data} keys={[{ id: "views", label: "Views", color: YOUTUBE_RED }, { id: "engaged_views", label: "Engaged Views", color: "#8b5cf6" }]} subtitle="Daily playback performance" title="Video Performance" />
      </div>
      <div className="facebook-one-three-grid">
        <PulsePieCard legendColumns={3} rows={engagementRows(data)} subtitle="Visible video engagement actions in the selected period" title="Video Engagement Split" />
        <PulseTrendCard data={data} keys={[{ id: "video_likes_daily", label: "Likes", color: V1_CHART_COLORS.likes }, { id: "video_comments_daily", label: "Comments", color: V1_CHART_COLORS.comments }, { id: "video_shares_daily", label: "Shares", color: V1_CHART_COLORS.shares }]} subtitle="Daily likes, comments and shares" title="Video Engagement Activity" />
      </div>
      <div className="facebook-two-grid">
        <PulseTrendCard bar data={data} keys={[{ id: "watch_time_minutes", label: "Watch Time (min)", color: "#14b8a6" }]} subtitle="Daily estimated minutes watched" title="Video Watch Time" />
        <PulseTrendCard data={data} keys={[{ id: "playlist_additions", label: "Added", color: "#22c55e" }, { id: "playlist_removals", label: "Removed", color: "#ef4444" }]} subtitle="Playlist additions and removals generated by videos" title="Video Playlist Activity" />
      </div>
      <PerformingContentTable content={data.content} variant="youtube" />
    </section>
  );
}

function AudienceSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  const ages = pieRows(data.breakdowns, "youtube_viewer_age", "viewer_percentage");
  const genders = pieRows(data.breakdowns, "youtube_viewer_gender", "viewer_percentage");
  const devices = pieRows(data.breakdowns, "youtube_device_type");
  const subscribed = pieRows(data.breakdowns, "youtube_subscribed_status");
  const products = pieRows(data.breakdowns, "youtube_product");
  const liveStatus = pieRows(data.breakdowns, "youtube_live_status");
  const operatingSystems = tableRows(data.breakdowns, "youtube_operating_system");
  const playbackLocations = tableRows(data.breakdowns, "youtube_playback_location");
  const traffic = tableRows(data.breakdowns, "youtube_traffic_source");
  const countries = countryRows(data.breakdowns);
  const noLinkedChannel = data.meta.resolved_account_ids.length === 0;
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Audience & Discovery</SectionTitle>}
      <KpiGrid rows={audienceKpis(data)} />
      {noLinkedChannel && <HonestEmpty copy="Connect a YouTube channel in Integrations, then run YouTube collection to load audience analytics." title="No YouTube channel connected" />}
      <div className="facebook-two-grid">
        <PulsePieCard rows={ages} subtitle="Latest available 28-day viewer distribution; subject to YouTube privacy thresholds" title="Viewer Age" />
        <PulsePieCard rows={genders} subtitle="Latest available 28-day viewer distribution; subject to YouTube privacy thresholds" title="Viewer Gender" />
      </div>
      <div className="facebook-two-grid">
        <PulsePieCard rows={devices} subtitle="Views by playback device in the selected period" title="Device Type" />
        <PulsePieCard rows={subscribed} subtitle="Views from subscribed and non-subscribed viewers" title="Subscriber Status" />
      </div>
      <div className="facebook-two-grid">
        <PulsePieCard rows={products} subtitle="Views across YouTube products in the selected period" title="YouTube Product" />
        <PulsePieCard rows={liveStatus} subtitle="Live and on-demand viewing in the selected period" title="Live vs On-demand" />
      </div>
      <div className="facebook-two-grid">
        <SimplePulseTable columns={["#", "Country", "Views", "Share"]} rows={countries} subtitle="Top playback countries in the selected period" title="Top Countries" />
        <SimplePulseTable columns={["#", "Source", "Views", "Share"]} rows={traffic} subtitle="How viewers discovered the channel's videos" title="Traffic Sources" />
      </div>
      <div className="facebook-two-grid">
        <SimplePulseTable columns={["#", "Operating System", "Views", "Share"]} rows={operatingSystems} subtitle="Playback operating systems in the selected period" title="Operating Systems" />
        <SimplePulseTable columns={["#", "Location", "Views", "Share"]} rows={playbackLocations} subtitle="Where viewers played the channel's videos" title="Playback Locations" />
      </div>
    </section>
  );
}

export function YouTubePulseDashboard({ data, tab }: { data: PlatformDashboard; tab: YouTubeTab }) {
  const cover = tab === "cover";
  return (
    <div className="facebook-pulse-dashboard youtube-pulse-dashboard">
      {(tab === "account" || cover) && <ChannelSection data={data} withTitle={cover} />}
      {(tab === "content" || cover) && <ContentSection data={data} withTitle={cover} />}
      {(tab === "audience" || cover) && <AudienceSection data={data} withTitle={cover} />}
    </div>
  );
}
