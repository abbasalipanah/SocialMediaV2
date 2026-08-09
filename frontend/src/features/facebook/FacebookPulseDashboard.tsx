import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Eye,
  Heart,
  Image as ImageIcon,
  Info,
  MessageCircle,
  MousePointerClick,
  PieChart as PieChartIcon,
  Share2,
  Target,
  ThumbsUp,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useId, useMemo, type ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type {
  DashboardBreakdown,
  DashboardContent,
  DashboardMetric,
  DashboardSeries,
  MetricId,
  PlatformDashboard,
} from "../../api";
import { FollowerAvatarStack } from "../../ui";
import { formatDate, formatNumber, humanize } from "../dashboard/format";

type FacebookTab = "cover" | "page" | "content" | "audience";

export type PulseKpi = {
  id: string;
  label: string;
  value: number | null;
  delta: number | null;
  icon: LucideIcon;
  color: string;
  unit?: "count" | "ratio";
};

type PieRow = { label: string; value: number; color: string };

const PALETTE = ["#8b5cf6", "#ec4899", "#38bdf8", "#f59e0b", "#14b8a6", "#6366f1"];

function metric(metrics: DashboardMetric[], id: MetricId): DashboardMetric | undefined {
  return metrics.find((item) => item.metric_id === id);
}

function metricValue(metrics: DashboardMetric[], ids: MetricId[]): number | null {
  for (const id of ids) {
    const current = metric(metrics, id);
    if (current?.value !== null && current?.value !== undefined) return current.value;
  }
  return null;
}

function compact(value: number | null): string {
  return value === null
    ? "—"
    : new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function derivedContentTotals(content: DashboardContent[]) {
  return content.reduce(
    (current, item) => ({
      likes: current.likes + item.likes_count,
      comments: current.comments + item.comments_count,
      shares: current.shares + item.shares_count,
      interactions: current.interactions + item.interactions,
    }),
    { likes: 0, comments: 0, shares: 0, interactions: 0 },
  );
}

function kpiFromMetric(
  data: PlatformDashboard,
  id: MetricId,
  label: string,
  icon: LucideIcon,
  color: string,
  fallbackIds: MetricId[] = [],
): PulseKpi {
  const current = metric(data.metrics, id);
  return {
    id,
    label,
    value: current?.value ?? metricValue(data.metrics, fallbackIds),
    delta: current?.delta_pct ?? null,
    icon,
    color,
    unit: current?.unit === "ratio" ? "ratio" : undefined,
  };
}

function pageKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    kpiFromMetric(data, "followers", "Followers", Users, "#38bdf8"),
    kpiFromMetric(data, "new_followers", "New Followers", Users, "#14b8a6"),
    kpiFromMetric(data, "reach", "Page Reach", Eye, "#8b5cf6"),
    kpiFromMetric(data, "views", "Page Views", Eye, "#ec4899", ["page_views"]),
    kpiFromMetric(data, "interactions", "Interactions", MessageCircle, "#f59e0b"),
    kpiFromMetric(data, "engagement_rate", "Engagement Rate", Activity, "#6366f1"),
  ];
}

function contentKpis(data: PlatformDashboard): PulseKpi[] {
  const totals = derivedContentTotals(data.content);
  const collectedTotal = (field: "views" | "reach") => {
    const values = data.content.flatMap((item) => item[field] === null ? [] : [item[field]]);
    return values.length > 0 ? values.reduce((sum, value) => sum + value, 0) : null;
  };
  const views = metric(data.metrics, "views")?.value ?? collectedTotal("views");
  const reach = metric(data.metrics, "reach")?.value ?? collectedTotal("reach");
  return [
    { id: "post_views", label: "Views", value: views, delta: null, icon: Eye, color: "#ec4899" },
    { id: "post_reach", label: "Reach", value: reach, delta: null, icon: Target, color: "#38bdf8" },
    { id: "like_reactions", label: "Likes", value: totals.likes, delta: null, icon: ThumbsUp, color: "#ef4444" },
    { id: "comments", label: "Comments", value: totals.comments, delta: null, icon: MessageCircle, color: "#3b82f6" },
    { id: "shares", label: "Shares", value: totals.shares, delta: null, icon: Share2, color: "#22c55e" },
    { id: "engagement_rate", label: "Engagement Rate", value: views && views > 0 ? totals.interactions / views : null, delta: null, icon: Activity, color: "#6366f1", unit: "ratio" },
  ];
}

function audienceKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    kpiFromMetric(data, "followers", "Followers", Users, "#38bdf8"),
    kpiFromMetric(data, "new_followers", "New Followers", Users, "#14b8a6"),
    kpiFromMetric(data, "views", "Views", Eye, "#06b6d4", ["page_views"]),
    kpiFromMetric(data, "reach", "Reach", Target, "#8b5cf6"),
    kpiFromMetric(data, "profile_views", "Profile Views", Eye, "#ec4899", ["page_views"]),
    kpiFromMetric(data, "engagement_rate", "Engagement Rate", Activity, "#6366f1"),
  ];
}

function PulseKpiCard({ item }: { item: PulseKpi }) {
  const positive = item.delta !== null && item.delta > 0;
  const negative = item.delta !== null && item.delta < 0;
  return (
    <article className="facebook-pulse-kpi">
      <div className="facebook-pulse-kpi-top">
        {item.id === "followers" ? (
          <FollowerAvatarStack />
        ) : (
          <span className="facebook-pulse-kpi-icon" style={{ color: item.color, background: `${item.color}1a` }}><item.icon size={20} /></span>
        )}
        <span className={`facebook-pulse-delta${positive ? " positive" : negative ? " negative" : " neutral"}`}>
          {positive ? <ArrowUpRight size={12} /> : negative ? <ArrowDownRight size={12} /> : null}
          {item.delta === null ? "—" : `${Math.abs(item.delta).toFixed(1)}%`}
        </span>
      </div>
      <strong>{item.value === null ? "—" : item.unit === "ratio" ? new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 }).format(item.value) : compact(item.value)}</strong>
      <span>{item.label}</span>
    </article>
  );
}

export function KpiGrid({ rows }: { rows: PulseKpi[] }) {
  const visibleRows = rows.filter((item) => item.value !== null);
  return <div className="facebook-pulse-kpi-grid">{visibleRows.map((item) => <PulseKpiCard item={item} key={item.id} />)}</div>;
}

type TrendKey = { id: MetricId; label: string; color: string };

const FOLLOWER_FLOW_KEYS: TrendKey[] = [
  { id: "follows", label: "Follows", color: "#3b82f6" },
  { id: "unfollows", label: "Unfollows", color: "#ec4899" },
  { id: "followers_net", label: "Net", color: "#14b8a6" },
];

function seriesFor(data: PlatformDashboard, id: MetricId): DashboardSeries | undefined {
  return data.series.find((item) => item.metric_id === id);
}

export function PulseCardHeading({ action, subtitle, title }: { action?: ReactNode; subtitle?: string; title: string }) {
  return (
    <div className="facebook-pulse-card-heading">
      <div className="facebook-pulse-heading-line">
        <span><h3>{title}</h3><Info aria-label={`${title} information`} size={14} /></span>
        {action}
      </div>
      {subtitle && <p>{subtitle}</p>}
    </div>
  );
}

function PulseTableHeading({ action, subtitle, title }: { action?: string; subtitle?: string; title: string }) {
  return (
    <div className="facebook-table-title">
      <div>
        <div className="facebook-table-heading-name"><h3>{title}</h3><Info aria-label={`${title} information`} size={14} /></div>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action && <span>{action}</span>}
    </div>
  );
}

function chartDate(value: string): string {
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString("en-US", { day: "2-digit", month: "short", timeZone: "UTC" });
}

function selectedRangeDates(startOn: string, endOn: string): string[] {
  const start = new Date(`${startOn}T00:00:00Z`);
  const end = new Date(`${endOn}T00:00:00Z`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) return [];
  const dates: string[] = [];
  for (let cursor = start; cursor <= end && dates.length < 366; cursor = new Date(cursor.getTime() + 86_400_000)) {
    dates.push(cursor.toISOString().slice(0, 10));
  }
  return dates;
}

export function PulseTrendCard({
  data,
  title,
  subtitle,
  keys,
  wide = false,
  bar = false,
  localZoom = false,
}: {
  data: PlatformDashboard;
  title: string;
  subtitle: string;
  keys: TrendKey[];
  wide?: boolean;
  bar?: boolean;
  localZoom?: boolean;
}) {
  const gradientSeed = useId().replace(/[^a-zA-Z0-9]/g, "");
  const lines = keys.flatMap((key) => {
    const series = seriesFor(data, key.id);
    return series ? [{ ...key, points: series.points }] : [];
  });
  const values = lines.flatMap((line) => line.points.map((point) => point.value));
  const rawMinimum = values.length > 0 ? Math.min(...values) : 0;
  const rawMaximum = values.length > 0 ? Math.max(...values) : 1;
  const localPadding = Math.max(1, (rawMaximum - rawMinimum) * 0.12);
  const minimum = localZoom ? rawMinimum - localPadding : Math.min(0, rawMinimum);
  const maximum = localZoom ? rawMaximum + localPadding : Math.max(1, rawMaximum);
  const chartData = useMemo(() => {
    const sampledDates = lines.flatMap((line) => line.points.map((point) => point.observed_on));
    const dates = [...new Set([
      ...selectedRangeDates(data.meta.date_range.start_on, data.meta.date_range.end_on),
      ...sampledDates,
    ])].sort();
    return dates.map((observed_on) => ({
      observed_on,
      ...Object.fromEntries(lines.map((line) => [line.id, line.points.find((point) => point.observed_on === observed_on)?.value ?? null])),
    }));
  }, [data.meta.date_range.end_on, data.meta.date_range.start_on, lines]);
  return (
    <article className={`facebook-pulse-card facebook-trend-card${wide ? " wide" : ""}`}>
      <PulseCardHeading subtitle={subtitle} title={title} />
      {values.length === 0 ? <PulseEmpty copy="No trend data for this period." /> : (
        <div aria-label={`${title}: ${lines.map((line) => line.label).join(", ")}`} className="facebook-rechart" role="img">
          <ResponsiveContainer height="100%" width="100%">
            {bar ? (
              <BarChart data={chartData} margin={{ bottom: 2, left: -12, right: 10, top: 4 }}>
                <CartesianGrid opacity={0.55} stroke="#e8edf4" strokeDasharray="3 3" vertical={false} />
                <XAxis axisLine={false} dataKey="observed_on" minTickGap={52} tick={{ fill: "#94a3b8", fontSize: 10 }} tickFormatter={chartDate} tickLine={false} />
                <YAxis axisLine={false} domain={[minimum, maximum]} tick={{ fill: "#7c8aa0", fontSize: 10 }} tickFormatter={(value) => compact(Number(value))} tickLine={false} width={46} />
                <Tooltip labelFormatter={(value) => chartDate(String(value))} />
                <Legend iconType="circle" verticalAlign="top" wrapperStyle={{ color: "#64748b", fontSize: "10px", paddingBottom: "10px" }} />
                {lines.map((line) => <Bar barSize={10} dataKey={line.id} fill={line.color} fillOpacity={0.7} key={line.id} name={line.label} radius={[4, 4, 0, 0]} />)}
              </BarChart>
            ) : (
              <AreaChart data={chartData} margin={{ bottom: 2, left: -12, right: 10, top: 4 }}>
                <defs>
                  {lines.map((line) => (
                    <linearGradient id={`${gradientSeed}-${line.id}`} key={line.id} x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor={line.color} stopOpacity="0.28" />
                      <stop offset="95%" stopColor={line.color} stopOpacity="0.01" />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid opacity={0.55} stroke="#e8edf4" strokeDasharray="3 3" vertical={false} />
                <XAxis axisLine={false} dataKey="observed_on" minTickGap={52} tick={{ fill: "#94a3b8", fontSize: 10 }} tickFormatter={chartDate} tickLine={false} />
                <YAxis axisLine={false} domain={[minimum, maximum]} tick={{ fill: "#7c8aa0", fontSize: 10 }} tickFormatter={(value) => compact(Number(value))} tickLine={false} width={46} />
                <Tooltip labelFormatter={(value) => chartDate(String(value))} />
                <Legend iconType="circle" verticalAlign="top" wrapperStyle={{ color: "#64748b", fontSize: "10px", paddingBottom: "10px" }} />
                {lines.map((line) => (
                  <Area activeDot={{ r: 3 }} connectNulls={false} dataKey={line.id} dot={false} fill={`url(#${gradientSeed}-${line.id})`} key={line.id} name={line.label} stroke={line.color} strokeWidth={1.45} type="monotone" />
                ))}
              </AreaChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}

export function PulseEmpty({ copy }: { copy: string }) {
  return <div className="facebook-pulse-empty">{copy}</div>;
}

export function UnavailableInsightCard({
  title,
  subtitle,
  copy,
}: {
  title: string;
  subtitle: string;
  copy: string;
}) {
  return (
    <article className="facebook-pulse-card facebook-trend-card facebook-unavailable-card">
      <PulseCardHeading subtitle={subtitle} title={title} />
      <PulseEmpty copy={copy} />
    </article>
  );
}

function pieBackground(rows: PieRow[]): string {
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  if (total <= 0) return "#e2e8f0";
  let cursor = 0;
  return `conic-gradient(${rows.map((row) => {
    const end = cursor + (row.value / total) * 100;
    const part = `${row.color} ${cursor}% ${end}%`;
    cursor = end;
    return part;
  }).join(",")})`;
}

function pieCenterLabel(title: string): string {
  const normalized = title.toLowerCase();
  if (normalized.includes("view")) return "Views";
  if (normalized.includes("reach")) return "Reach";
  if (normalized.includes("content") || normalized.includes("type")) return "Content";
  if (normalized.includes("interaction") || normalized.includes("engagement")) return "Interactions";
  if (normalized.includes("sentiment")) return "Comments";
  if (normalized.includes("like")) return "Likes";
  return "Total";
}

export function PulsePieCard({ legendColumns = 2, title, subtitle, rows }: { legendColumns?: 2 | 3; title: string; subtitle?: string; rows: PieRow[] }) {
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  return (
    <article className="facebook-pulse-card facebook-pie-card">
      <PulseCardHeading action={<span className="facebook-pie-heading-icon"><PieChartIcon size={17} /></span>} subtitle={subtitle} title={title} />
      {total <= 0 ? <PulseEmpty copy="No distribution data in selected range." /> : (
        <>
          <div className="facebook-pie-wrap"><div className="facebook-pie" style={{ background: pieBackground(rows) }}><span><strong>{formatNumber(total)}</strong><small>{pieCenterLabel(title)}</small></span></div></div>
          <div className={`facebook-pie-legend columns-${legendColumns}`}>{rows.map((row) => <div key={row.label}><span><i style={{ background: row.color }} />{row.label}</span><strong>{((row.value / total) * 100).toFixed(0)}%</strong></div>)}</div>
        </>
      )}
    </article>
  );
}

function pageViewRows(data: PlatformDashboard): PieRow[] {
  const source = data.source_breakdown?.views;
  const organic = source?.organic ?? metric(data.metrics, "views_organic")?.value ?? null;
  const paid = source?.paid ?? metric(data.metrics, "views_paid")?.value ?? null;
  return [
    organic === null ? null : { label: "Organic", value: organic, color: "#8b5cf6" },
    paid === null ? null : { label: "Paid", value: paid, color: "#ec4899" },
  ].filter((item): item is PieRow => item !== null);
}

function reachTypeRows(data: PlatformDashboard): PieRow[] {
  const source = data.source_breakdown?.reach;
  const organic = source?.organic ?? metric(data.metrics, "reach_organic")?.value ?? null;
  const paid = source?.paid ?? metric(data.metrics, "reach_paid")?.value ?? null;
  return [
    organic === null ? null : { label: "Organic", value: organic, color: "#8b5cf6" },
    paid === null ? null : { label: "Paid", value: paid, color: "#ec4899" },
  ].filter((item): item is PieRow => item !== null);
}

export function hashtagRows(data: PlatformDashboard): Array<Array<string | number>> {
  return data.top_hashtags.map((item) => [item.name, item.count]);
}

export function summaryPieRows(
  items: PlatformDashboard["content_summary"]["by_type"],
  colors: string[] = PALETTE,
): PieRow[] {
  return items.map((item, index) => ({
    label: item.name,
    value: item.value,
    color: colors[index % colors.length] ?? "#64748b",
  }));
}

function engagementRows(content: DashboardContent[]): PieRow[] {
  const totals = derivedContentTotals(content);
  return [
    { label: "Likes", value: totals.likes, color: "#ef4444" },
    { label: "Comments", value: totals.comments, color: "#3b82f6" },
    { label: "Shares", value: totals.shares, color: "#22c55e" },
  ].filter((item) => item.value > 0);
}

export function SimplePulseTable({ title, subtitle, columns, rows, emptyCopy = "No data in selected range." }: { title: string; subtitle?: string; columns: string[]; rows: Array<Array<string | number>>; emptyCopy?: string }) {
  return (
    <article className="facebook-pulse-card facebook-simple-table">
      <PulseCardHeading subtitle={subtitle} title={title} />
      <div className="facebook-table-scroll"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.length === 0 ? <tr><td colSpan={columns.length}>{emptyCopy}</td></tr> : rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div>
    </article>
  );
}

export function breakdownRows(breakdowns: DashboardBreakdown[], hint: string): Array<Array<string | number>> {
  const breakdown = breakdowns.find((item) => item.dimension.toLowerCase().includes(hint));
  return breakdown?.items.slice(0, 10).map((item, index) => [index + 1, humanize(item.key), formatNumber(item.value)]) ?? [];
}

export function breakdownPieRows(breakdowns: DashboardBreakdown[], hints: string[], colors: string[] = PALETTE): PieRow[] {
  const breakdown = breakdowns.find((item) => {
    const key = `${item.dimension} ${item.metric_id}`.toLowerCase();
    return hints.some((hint) => key.includes(hint));
  });
  return breakdown?.items.map((item, index) => ({
    label: humanize(item.key),
    value: item.value,
    color: colors[index % colors.length] ?? "#64748b",
  })).filter((item) => item.value > 0) ?? [];
}

export function PulseHeatmapCard({ breakdowns }: { breakdowns: DashboardBreakdown[] }) {
  const rows = breakdowns.find((item) => /best_time|heatmap|hourly|activity/.test(item.dimension.toLowerCase()))?.items ?? [];
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const dayIndexes: Record<string, number> = { mon: 0, monday: 0, tue: 1, tuesday: 1, wed: 2, wednesday: 2, thu: 3, thursday: 3, fri: 4, friday: 4, sat: 5, saturday: 5, sun: 6, sunday: 6 };
  const matrix = new Map<string, number>();
  rows.forEach((row) => {
    const [rawDay, rawHour] = row.key.split("|");
    const day = dayIndexes[String(rawDay ?? "").trim().toLowerCase()];
    const hour = Number(rawHour);
    if (day === undefined || !Number.isFinite(hour)) return;
    matrix.set(`${day}|${Math.floor(hour / 2) * 2}`, row.value);
  });
  const maximum = Math.max(1, ...matrix.values());
  const hours = Array.from({ length: 12 }, (_, index) => index * 2);
  const color = (value: number) => {
    if (value <= 0) return "#f4f7fb";
    const ratio = Math.min(1, value / maximum);
    return `hsl(${210 - (ratio * 85)} 72% ${96 - (ratio * 45)}%)`;
  };
  return (
    <article className="facebook-pulse-card facebook-heatmap-card">
      <PulseCardHeading subtitle="Hourly activity density" title="Best Time to Engage" />
      {rows.length === 0 ? <PulseEmpty copy="No heatmap data in selected range." /> : (
        <div className="facebook-heatmap">
          <div className="facebook-heatmap-days">{days.map((day) => <span key={day}>{day}</span>)}</div>
          <div className="facebook-heatmap-grid">
            {days.flatMap((day, dayIndex) => hours.map((hour) => {
              const value = matrix.get(`${dayIndex}|${hour}`) ?? 0;
              return <i key={`${day}-${hour}`} style={{ background: color(value) }} title={`${day} ${String(hour).padStart(2, "0")}:00 · ${formatNumber(value)}`} />;
            }))}
          </div>
          <div className="facebook-heatmap-hours">{hours.map((hour) => <span key={hour}>{String(hour).padStart(2, "0")}</span>)}</div>
          <div className="facebook-heatmap-scale"><span>Low</span><i /><span>High</span></div>
        </div>
      )}
    </article>
  );
}

export function PerformingContentTable({ content }: { content: DashboardContent[] }) {
  const rows = [...content].sort((left, right) => right.interactions - left.interactions);
  return (
    <article className="facebook-pulse-table-card">
      <PulseTableHeading action={`${rows.length} items`} subtitle="Content ranked by collected interactions" title="All Performing Content" />
      <div className="facebook-table-scroll"><table><thead><tr><th>#</th><th>Video</th><th>Date</th><th>Views</th><th>Reach</th><th>Likes</th><th>Comments</th><th>Shares</th><th>Interactions</th></tr></thead><tbody>
        {rows.length === 0 ? <tr><td colSpan={9}>No videos were collected in this period.</td></tr> : rows.map((item, index) => (
          <tr key={`${item.account_id}-${item.external_content_id}`}>
            <td>{index + 1}</td>
            <td>
              <span className="facebook-content-title-cell">
                <span className="facebook-content-cover">{item.cover_url || item.thumbnail_url || item.media_url ? <img alt="" src={item.cover_url || item.thumbnail_url || item.media_url} /> : <ImageIcon size={17} />}</span>
                <span><b title={item.message}>{item.message || "Untitled video"}</b><small>{item.external_content_id}</small></span>
              </span>
            </td>
            <td>{item.published_at ? formatDate(item.published_at) : "—"}</td>
            <td>{item.views === null ? "—" : formatNumber(item.views)}</td><td>{item.reach === null ? "—" : formatNumber(item.reach)}</td><td>{formatNumber(item.likes_count)}</td><td>{formatNumber(item.comments_count)}</td><td>{formatNumber(item.shares_count)}</td><td><span className="facebook-table-score">{formatNumber(item.interactions)}</span></td>
          </tr>
        ))}
      </tbody></table></div>
    </article>
  );
}

export function CommunityTables({ data, platform }: { data: PlatformDashboard; platform: "instagram" | "tiktok" }) {
  const instagram = platform === "instagram";
  return (
    <div className="facebook-two-grid">
      <SimplePulseTable
        columns={["#", "Username", instagram ? "Messages" : "Comments", "Likes"]}
        rows={data.community.top_commenters.map((item, index) => [index + 1, item.name, item.comments, item.likes])}
        subtitle={`${instagram ? "Instagram" : "TikTok"} comment activity leaderboard`}
        title={instagram ? "Most Comments and Messages" : "Most Active Commenters"}
      />
      <SimplePulseTable
        columns={["#", "Username", "Comment", "Likes"]}
        rows={data.community.top_liked_comments.map((item, index) => [index + 1, item.name, item.comment || "—", item.likes])}
        subtitle="Comment like leaderboard"
        title="Most Liked Comments"
      />
    </div>
  );
}

export function SectionTitle({ children }: { children: string }) {
  return <h2 className="facebook-section-title">{children}</h2>;
}

function PageSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Overview</SectionTitle>}
      <KpiGrid rows={pageKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: "#38bdf8" }]} localZoom subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard data={data} keys={FOLLOWER_FLOW_KEYS} subtitle="Follows, unfollows and net movement" title="New Followers Trend" />
      </div>
      <PulseTrendCard bar data={data} keys={[{ id: "reach", label: "Page Reach", color: "#8b5cf6" }, { id: "views", label: "Page Views", color: "#5eead4" }]} subtitle="Page Reach and Page Views trend" title="Performance Trends" wide />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={pageViewRows(data)} subtitle="Organic vs paid views" title="Page View Type" />
        <PulseTrendCard data={data} keys={[{ id: "views_organic", label: "Organic Views", color: "#3b82f6" }, { id: "views_paid", label: "Paid Views", color: "#f59e0b" }]} subtitle="Organic and paid view delivery" title="Views Source Trend" />
      </div>
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={reachTypeRows(data)} subtitle="Organic vs paid Reach" title="Reach Distribution" />
        <PulseTrendCard data={data} keys={[{ id: "reach_paid", label: "Paid Reach", color: "#ef4444" }, { id: "reach_organic", label: "Organic Reach", color: "#22c55e" }]} subtitle="Paid Reach and Organic Reach" title="Reach Source Trend" />
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
        <PulsePieCard rows={summaryPieRows(data.content_summary.by_type)} subtitle="Content mix by format" title="Content Type" />
        <PulseTrendCard data={data} keys={[{ id: "views", label: "Page Views", color: "#ec4899" }, { id: "reach", label: "Page Reach", color: "#8b5cf6" }]} subtitle="Daily page views and reach" title="Views & Reach Trend" />
      </div>
      <div className="facebook-two-three-grid">
        <PulseTrendCard data={data} keys={[{ id: "interactions", label: "Interactions", color: "#f59e0b" }]} subtitle="Likes, comments and shares over time" title="Interaction Trend" />
        <PulsePieCard legendColumns={3} rows={engagementRows(data.content)} subtitle="Interaction mix" title="Engagement Split" />
      </div>
      <div className="facebook-three-grid">
        <PulsePieCard rows={summaryPieRows(data.content_summary.reach_by_type, ["#f59e0b", "#ec4899", "#38bdf8", "#14b8a6"])} subtitle="Reach by content type" title="Content Type Reach" />
        <UnavailableInsightCard copy="Sentiment is not inferred without a configured analysis model." subtitle="Not provided by TikTok Organic API" title="Comment Sentiment" />
        <SimplePulseTable columns={["Hashtag", "Count"]} emptyCopy="No hashtags in collected captions." rows={hashtagRows(data)} subtitle="Hashtags found in collected captions" title="Top Hashtags" />
      </div>
      <PerformingContentTable content={data.content} />
    </section>
  );
}

function AudienceSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Audience</SectionTitle>}
      <KpiGrid rows={audienceKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: "#38bdf8" }]} localZoom subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard data={data} keys={FOLLOWER_FLOW_KEYS} subtitle="Follows, unfollows and net movement" title="New Followers Trend" />
      </div>
      <div className="facebook-two-grid">
        <PulsePieCard
          rows={breakdownPieRows(data.breakdowns, ["like_type"], ["#8357f6", "#f59e0b"])}
          subtitle="Like source split"
          title="Page Like Types (Organic vs Paid)"
        />
        <PulseHeatmapCard breakdowns={data.audience_capabilities.activity === "available" ? data.breakdowns : []} />
      </div>
      <div className="facebook-two-grid">
        <SimplePulseTable columns={["#", "Country", "Value"]} rows={breakdownRows(data.breakdowns, "country")} subtitle="Country ranking" title="Top Countries" />
        <SimplePulseTable columns={["#", "City", "Value"]} rows={breakdownRows(data.breakdowns, "city")} subtitle="City ranking" title="Top Cities" />
      </div>
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "reach_paid", label: "Paid Reach", color: "#ef4444" }]} subtitle="Paid delivery trend" title="Paid Reach Trend" />
        <PulseTrendCard data={data} keys={[{ id: "reach_organic", label: "Organic Reach", color: "#22c55e" }]} subtitle="Organic delivery trend" title="Organic Reach Trend" />
      </div>
    </section>
  );
}

export function FacebookPulseDashboard({ data, tab }: { data: PlatformDashboard; tab: FacebookTab }) {
  const cover = tab === "cover";
  return (
    <div className="facebook-pulse-dashboard">
      {(tab === "page" || cover) && <PageSection data={data} withTitle={cover} />}
      {(tab === "content" || cover) && <ContentSection data={data} withTitle={cover} />}
      {(tab === "audience" || cover) && <AudienceSection data={data} withTitle={cover} />}
    </div>
  );
}
