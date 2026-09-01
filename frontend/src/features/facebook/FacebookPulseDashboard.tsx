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
  Video,
  type LucideIcon,
} from "lucide-react";
import { useId, useMemo, useState, type ReactNode } from "react";
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
import { ANONYMOUS_COMMENT_AUTHOR, maskCommentMentions } from "../dashboard/commentPrivacy";
import { CountryTableLabel, countryCode } from "../dashboard/countryPresentation";
import { formatDate, formatNumber, humanize } from "../dashboard/format";
import {
  V1_BAR_FILL_OPACITY,
  V1_CHART_COLORS,
  V1_FOLLOWER_FLOW_KEYS,
  V1_TREND_FILL_BOTTOM_OPACITY,
  V1_TREND_FILL_TOP_OPACITY,
  V1_TREND_STROKE_WIDTH,
  displayTrendValue,
  followerFlowSubtitle,
  type TrendKey,
} from "../dashboard/visualPalette";

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

export type PieRow = { label: string; value: number; color: string };

type ContentSortKey =
  | "caption"
  | "date"
  | "type"
  | "views"
  | "interactions"
  | "likes"
  | "comments"
  | "shares"
  | "saves"
  | "profile_visits"
  | "engagement";
type ContentSortDirection = "asc" | "desc";

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

function safeContentUrl(rawUrl: string): string | null {
  if (!rawUrl.trim()) return null;
  try {
    const url = new URL(rawUrl);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password
      ? url.toString()
      : null;
  } catch {
    return null;
  }
}

function contentEngagement(item: DashboardContent): number | null {
  const delivery = item.reach !== null && item.reach > 0 ? item.reach : item.views;
  return delivery !== null && delivery > 0 && item.interactions !== null
    ? (item.interactions / delivery) * 100
    : null;
}

function contentPublishedAt(item: DashboardContent): number | null {
  if (!item.published_at) return null;
  const timestamp = Date.parse(item.published_at);
  return Number.isNaN(timestamp) ? null : timestamp;
}

function contentDateLabel(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "—"
    : new Intl.DateTimeFormat("en-US", {
      day: "numeric",
      month: "short",
      timeZone: "UTC",
    }).format(parsed);
}

function contentSortValue(item: DashboardContent, key: ContentSortKey): string | number | null {
  if (key === "caption") return item.message || `Untitled ${humanize(item.content_type).toLowerCase()}`;
  if (key === "date") return contentPublishedAt(item);
  if (key === "type") return humanize(item.content_type);
  if (key === "views") return item.views;
  if (key === "interactions") return item.interactions;
  if (key === "likes") return item.likes_count;
  if (key === "comments") return item.comments_count;
  if (key === "shares") return item.shares_count;
  if (key === "saves") return item.saves_count;
  if (key === "profile_visits") return item.profile_visits;
  return contentEngagement(item);
}

function defaultContentSortDirection(key: ContentSortKey): ContentSortDirection {
  return key === "caption" || key === "type" ? "asc" : "desc";
}

function SortableContentHeader({
  activeDirection,
  label,
  onSort,
}: {
  activeDirection: ContentSortDirection | null;
  label: string;
  onSort: () => void;
}) {
  return (
    <th aria-sort={activeDirection === null ? "none" : activeDirection === "asc" ? "ascending" : "descending"}>
      <button
        aria-label={`Sort by ${label}`}
        className="facebook-content-sort"
        data-sort={activeDirection ?? "none"}
        onClick={onSort}
        type="button"
      >
        {label}
      </button>
    </th>
  );
}

function ContentTypeChip({ contentType }: { contentType: string }) {
  const isVideo = /(?:reel|video)/u.test(contentType.trim().toLowerCase());
  const Icon = isVideo ? Video : Activity;
  return (
    <span className={`facebook-type-chip ${isVideo ? "is-video" : "is-post"}`}>
      <Icon aria-hidden="true" size={12} strokeWidth={1.8} />
      {humanize(contentType)}
    </span>
  );
}

export function derivedContentTotals(content: DashboardContent[]) {
  const total = (values: Array<number | null>): number | null => {
    const available = values.filter((value): value is number => value !== null);
    return available.length > 0 ? available.reduce((sum, value) => sum + value, 0) : null;
  };
  return {
    likes: total(content.map((item) => item.likes_count)),
    comments: total(content.map((item) => item.comments_count)),
    shares: total(content.map((item) => item.shares_count)),
    interactions: total(content.map((item) => item.interactions)),
  };
}

export function comparisonDelta(value: number | null, previous: number | null): number | null {
  return value === null || previous === null || previous === 0
    ? null
    : ((value - previous) / Math.abs(previous)) * 100;
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
  const viewsMetric = metric(data.metrics, "views");
  const reachMetric = metric(data.metrics, "reach");
  const viewsFromMetric = viewsMetric?.value !== null && viewsMetric?.value !== undefined;
  const reachFromMetric = reachMetric?.value !== null && reachMetric?.value !== undefined;
  const views = viewsMetric?.value ?? data.content_metrics.views.value ?? collectedTotal("views");
  const reach = reachMetric?.value ?? data.content_metrics.reach.value ?? collectedTotal("reach");
  const interactions = data.content_metrics.interactions.value ?? totals.interactions;
  const engagementRate = views && views > 0 && interactions !== null ? interactions / views : null;
  const previousViews = viewsFromMetric
    ? viewsMetric.previous_value
    : data.content_metrics.views.previous_value;
  const previousInteractions = data.content_metrics.interactions.previous_value;
  const previousEngagementRate = previousViews && previousViews > 0 && previousInteractions !== null
    ? previousInteractions / previousViews
    : null;
  return [
    { id: "post_views", label: "Views", value: views, delta: viewsFromMetric ? viewsMetric.delta_pct : data.content_metrics.views.delta_pct, icon: Eye, color: "#ec4899" },
    { id: "post_reach", label: "Reach", value: reach, delta: reachFromMetric ? reachMetric.delta_pct : data.content_metrics.reach.delta_pct, icon: Target, color: "#38bdf8" },
    { id: "like_reactions", label: "Likes", value: data.content_metrics.likes.value ?? totals.likes, delta: data.content_metrics.likes.delta_pct, icon: ThumbsUp, color: V1_CHART_COLORS.likes },
    { id: "comments", label: "Comments", value: data.content_metrics.comments.value ?? totals.comments, delta: data.content_metrics.comments.delta_pct, icon: MessageCircle, color: "#3b82f6" },
    { id: "shares", label: "Shares", value: data.content_metrics.shares.value ?? totals.shares, delta: data.content_metrics.shares.delta_pct, icon: Share2, color: "#22c55e" },
    { id: "engagement_rate", label: "Engagement Rate", value: engagementRate, delta: comparisonDelta(engagementRate, previousEngagementRate), icon: Activity, color: "#6366f1", unit: "ratio" },
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
  return <div className="facebook-pulse-kpi-grid">{rows.map((item) => <PulseKpiCard item={item} key={item.id} />)}</div>;
}

function seriesFor(data: PlatformDashboard, id: MetricId): DashboardSeries | undefined {
  return data.series.find((item) => item.metric_id === id);
}

function PulseChartLegend({ lines }: { lines: readonly TrendKey[] }) {
  return (
    <div className="facebook-chart-legend">
      {lines.map((line) => <span key={line.id}><i style={{ background: line.color }} />{line.label}</span>)}
    </div>
  );
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
  connectGaps = false,
}: {
  data: PlatformDashboard;
  title: string;
  subtitle: string;
  keys: TrendKey[];
  wide?: boolean;
  bar?: boolean;
  localZoom?: boolean;
  connectGaps?: boolean;
}) {
  const gradientSeed = useId().replace(/[^a-zA-Z0-9]/g, "");
  const lines = keys.flatMap((key) => {
    const series = seriesFor(data, key.id);
    return series ? [{
      ...key,
      points: series.points.map((point) => ({
        ...point,
        value: displayTrendValue(key, point.value),
      })),
    }] : [];
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
                <Tooltip cursor={false} labelFormatter={(value) => chartDate(String(value))} />
                <Legend content={<PulseChartLegend lines={lines} />} verticalAlign="top" />
                {lines.map((line) => <Bar barSize={10} dataKey={line.id} fill={line.color} fillOpacity={V1_BAR_FILL_OPACITY} key={line.id} name={line.label} radius={[4, 4, 0, 0]} />)}
              </BarChart>
            ) : (
              <AreaChart baseValue={0} data={chartData} margin={{ bottom: 2, left: -12, right: 10, top: 4 }}>
                <defs>
                  {lines.map((line) => (
                    <linearGradient id={`${gradientSeed}-${line.id}`} key={line.id} x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor={line.color} stopOpacity={V1_TREND_FILL_TOP_OPACITY} />
                      <stop offset="100%" stopColor={line.color} stopOpacity={V1_TREND_FILL_BOTTOM_OPACITY} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid opacity={0.55} stroke="#e8edf4" strokeDasharray="3 3" vertical={false} />
                <XAxis axisLine={false} dataKey="observed_on" minTickGap={52} tick={{ fill: "#94a3b8", fontSize: 10 }} tickFormatter={chartDate} tickLine={false} />
                <YAxis axisLine={false} domain={[minimum, maximum]} tick={{ fill: "#7c8aa0", fontSize: 10 }} tickFormatter={(value) => compact(Number(value))} tickLine={false} width={46} />
                <Tooltip labelFormatter={(value) => chartDate(String(value))} />
                <Legend content={<PulseChartLegend lines={lines} />} verticalAlign="top" />
                {lines.map((line) => (
                  <Area activeDot={{ r: 3 }} connectNulls={localZoom || connectGaps} dataKey={line.id} dot={false} fill={`url(#${gradientSeed}-${line.id})`} key={line.id} name={line.label} stroke={line.color} strokeWidth={V1_TREND_STROKE_WIDTH} type="monotone" />
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

type PieSegment = PieRow & {
  endAngle: number;
  index: number;
  percentage: number;
  startAngle: number;
};

function polarPoint(radius: number, angle: number): { x: number; y: number } {
  const radians = ((angle - 90) * Math.PI) / 180;
  return {
    x: 100 + radius * Math.cos(radians),
    y: 100 + radius * Math.sin(radians),
  };
}

function donutSegmentPath(startAngle: number, endAngle: number): string {
  const safeEnd = Math.min(endAngle, startAngle + 359.999);
  const outerStart = polarPoint(78, startAngle);
  const outerEnd = polarPoint(78, safeEnd);
  const innerEnd = polarPoint(52, safeEnd);
  const innerStart = polarPoint(52, startAngle);
  const largeArc = safeEnd - startAngle > 180 ? 1 : 0;
  return [
    `M ${outerStart.x} ${outerStart.y}`,
    `A 78 78 0 ${largeArc} 1 ${outerEnd.x} ${outerEnd.y}`,
    `L ${innerEnd.x} ${innerEnd.y}`,
    `A 52 52 0 ${largeArc} 0 ${innerStart.x} ${innerStart.y}`,
    "Z",
  ].join(" ");
}

function pieSegments(rows: PieRow[], total: number): PieSegment[] {
  let cursor = 0;
  return rows.flatMap((row, index) => {
    if (row.value <= 0) return [];
    const startAngle = cursor;
    const percentage = (row.value / total) * 100;
    cursor += percentage * 3.6;
    return [{ ...row, endAngle: cursor, index, percentage, startAngle }];
  });
}

function activeSegmentOffset(segment: PieSegment): { x: number; y: number } {
  const radians = ((((segment.startAngle + segment.endAngle) / 2) - 90) * Math.PI) / 180;
  return { x: Math.cos(radians) * 7, y: Math.sin(radians) * 7 };
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

export function PulsePieVisualization({
  emptyCopy = "No distribution data in selected range.",
  legendColumns = 2,
  rows,
  title,
}: {
  emptyCopy?: string;
  legendColumns?: 2 | 3;
  rows: PieRow[];
  title: string;
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const total = rows.reduce((sum, row) => sum + Math.max(0, row.value), 0);
  const segments = pieSegments(rows, total);
  const activeRow = activeIndex === null || (rows[activeIndex]?.value ?? 0) <= 0
    ? null
    : rows[activeIndex] ?? null;
  const activePercentage = activeRow === null ? 0 : (activeRow.value / total) * 100;
  return total <= 0 ? <PulseEmpty copy={emptyCopy} /> : (
        <>
          <div className="facebook-pie-wrap">
            <div className="facebook-pie-graphic" onMouseLeave={() => setActiveIndex(null)}>
              <svg aria-label={`${title} chart`} className="facebook-pie-svg" role="img" viewBox="0 0 200 200">
                {segments.map((segment) => {
                  const active = activeIndex === segment.index;
                  const offset = active ? activeSegmentOffset(segment) : { x: 0, y: 0 };
                  return (
                    <path
                      aria-label={`${segment.label}: ${formatNumber(segment.value)}, ${segment.percentage.toFixed(0)}%`}
                      aria-pressed={active}
                      className={`facebook-pie-segment${active ? " is-active" : ""}`}
                      d={donutSegmentPath(segment.startAngle, segment.endAngle)}
                      fill={segment.color}
                      key={`${segment.label}-${segment.index}`}
                      onBlur={() => setActiveIndex(null)}
                      onFocus={() => setActiveIndex(segment.index)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setActiveIndex((current) => current === segment.index ? null : segment.index);
                        }
                      }}
                      onMouseEnter={() => setActiveIndex(segment.index)}
                      onPointerUp={(event) => {
                        if (event.pointerType !== "mouse") {
                          setActiveIndex((current) => current === segment.index ? null : segment.index);
                        }
                      }}
                      role="button"
                      tabIndex={0}
                      transform={`translate(${offset.x.toFixed(2)} ${offset.y.toFixed(2)})`}
                    />
                  );
                })}
              </svg>
              <span className="facebook-pie-center"><strong>{formatNumber(total)}</strong><small>{pieCenterLabel(title)}</small></span>
              {activeRow ? (
                <div className="facebook-pie-tooltip" role="status">
                  <span><i style={{ background: activeRow.color }} />{activeRow.label}</span>
                  <div><strong>{formatNumber(activeRow.value)}</strong><small>{activePercentage.toFixed(0)}%</small></div>
                </div>
              ) : null}
            </div>
          </div>
          <div className={`facebook-pie-legend columns-${legendColumns}`}>{rows.map((row, index) => (
            <button
              aria-label={`Highlight ${row.label}`}
              aria-pressed={activeIndex === index}
              className={activeIndex === index ? "is-active" : ""}
              disabled={row.value <= 0}
              key={`${row.label}-${index}`}
              onBlur={() => setActiveIndex(null)}
              onFocus={() => row.value > 0 && setActiveIndex(index)}
              onMouseEnter={() => row.value > 0 && setActiveIndex(index)}
              onMouseLeave={() => setActiveIndex(null)}
              type="button"
            >
              <span><i style={{ background: row.color }} />{row.label}</span><strong>{((Math.max(0, row.value) / total) * 100).toFixed(0)}%</strong>
            </button>
          ))}</div>
        </>
      );
}

export function PulsePieCard({ legendColumns = 2, title, subtitle, rows }: { legendColumns?: 2 | 3; title: string; subtitle?: string; rows: PieRow[] }) {
  return (
    <article className="facebook-pulse-card facebook-pie-card">
      <PulseCardHeading action={<span className="facebook-pie-heading-icon"><PieChartIcon size={17} /></span>} subtitle={subtitle} title={title} />
      <PulsePieVisualization legendColumns={legendColumns} rows={rows} title={title} />
    </article>
  );
}

function pageViewRows(data: PlatformDashboard): PieRow[] {
  const source = data.source_breakdown?.views;
  const organic = source?.organic ?? metric(data.metrics, "views_organic")?.value ?? null;
  const paid = source?.paid ?? metric(data.metrics, "views_paid")?.value ?? null;
  const rows: Array<PieRow | null> = [
    organic === null ? null : { label: "Organic", value: organic, color: V1_CHART_COLORS.organic },
    paid === null ? null : { label: "Paid", value: paid, color: V1_CHART_COLORS.paid },
  ];
  return rows.filter((item): item is PieRow => item !== null);
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
  const rows: Array<{ label: string; value: number | null; color: string }> = [
    { label: "Likes", value: totals.likes, color: V1_CHART_COLORS.likes },
    { label: "Comments", value: totals.comments, color: V1_CHART_COLORS.comments },
    { label: "Shares", value: totals.shares, color: V1_CHART_COLORS.shares },
  ];
  return rows.flatMap((item) => item.value !== null && item.value > 0
    ? [{ ...item, value: item.value }]
    : []);
}

export function SimplePulseTable({ title, subtitle, columns, rows, emptyCopy = "No data in selected range." }: { title: string; subtitle?: string; columns: string[]; rows: Array<Array<ReactNode>>; emptyCopy?: string }) {
  return (
    <article className="facebook-pulse-card facebook-simple-table">
      <PulseCardHeading subtitle={subtitle} title={title} />
      <div className="facebook-table-scroll"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.length === 0 ? <tr><td colSpan={columns.length}>{emptyCopy}</td></tr> : rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div>
    </article>
  );
}

function dimensionHas(dimension: string, hint: string): boolean {
  const singular: Record<string, string> = {
    ages: "age",
    cities: "city",
    countries: "country",
    genders: "gender",
  };
  return dimension
    .toLowerCase()
    .split(/[^a-z0-9]+/u)
    .map((part) => singular[part] ?? part)
    .includes(hint);
}

export function preferredAudienceBreakdown(
  breakdowns: DashboardBreakdown[],
  hint: "age" | "city" | "country" | "gender",
): DashboardBreakdown | undefined {
  const plural = {
    age: "ages",
    city: "cities",
    country: "countries",
    gender: "genders",
  }[hint];
  const priorities = [
    `follower_demographics_${hint}`,
    `page_fans_${hint}`,
    `audience_${plural}`,
    `audience_${hint}`,
    hint,
  ];
  for (const dimension of priorities) {
    const exact = breakdowns.find((item) => item.dimension.toLowerCase() === dimension);
    if (exact) return exact;
  }
  return breakdowns.find((item) => dimensionHas(item.dimension, hint));
}

export function breakdownRows(breakdowns: DashboardBreakdown[], hint: string): Array<Array<string | number>> {
  const breakdown = ["age", "city", "country", "gender"].includes(hint)
    ? preferredAudienceBreakdown(
      breakdowns,
      hint as "age" | "city" | "country" | "gender",
    )
    : breakdowns.find((item) => dimensionHas(item.dimension, hint));
  return breakdown?.items.slice(0, 10).map((item, index) => [index + 1, humanize(item.key), formatNumber(item.value)]) ?? [];
}

export function countryBreakdownRows(breakdowns: DashboardBreakdown[]): Array<Array<ReactNode>> {
  const breakdown = preferredAudienceBreakdown(breakdowns, "country");
  return breakdown?.items.filter((item) => countryCode(item.key) !== null).slice(0, 10).map((item, index) => [
    index + 1,
    <CountryTableLabel key={item.key} value={item.key} />,
    formatNumber(item.value),
  ]) ?? [];
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

export function sentimentPieRows(breakdowns: DashboardBreakdown[]): PieRow[] {
  const breakdown = breakdowns.find(
    (item) => item.dimension.toLowerCase() === "comment_sentiment",
  );
  const colors: Record<string, string> = {
    positive: "#10b981",
    neutral: "#f59e0b",
    negative: "#ef4444",
  };
  return ["positive", "neutral", "negative"].flatMap((sentiment) => {
    const item = breakdown?.items.find(
      (candidate) => candidate.key.toLowerCase() === sentiment,
    );
    return item && item.value > 0
      ? [{ label: humanize(item.key), value: item.value, color: colors[sentiment] ?? "#64748b" }]
      : [];
  });
}

export function PulseHeatmapCard({ breakdowns }: { breakdowns: DashboardBreakdown[] }) {
  const matched = breakdowns.find((item) => /best_time|heatmap|hourly|activity/.test(item.dimension.toLowerCase()))?.items ?? [];
  // The provider returns the full 7x24 grid with every cell at zero when it has
  // no hourly activity to report. Drawing that grid looks like a rendered but
  // broken chart; saying there is no data is the truth.
  const rows = matched.some((item) => item.value > 0) ? matched : [];
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const dayIndexes: Record<string, number> = { mon: 0, monday: 0, tue: 1, tuesday: 1, wed: 2, wednesday: 2, thu: 3, thursday: 3, fri: 4, friday: 4, sat: 5, saturday: 5, sun: 6, sunday: 6 };
  const matrix = new Map<string, number>();
  rows.forEach((row) => {
    const [rawDay, rawHour] = row.key.split("|");
    const day = dayIndexes[String(rawDay ?? "").trim().toLowerCase()];
    const hour = Number(rawHour);
    if (day === undefined || !Number.isFinite(hour)) return;
    const key = `${day}|${Math.floor(hour / 2) * 2}`;
    matrix.set(key, (matrix.get(key) ?? 0) + row.value);
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
      <PulseCardHeading subtitle="Average content engagement by publishing time" title="Best Time to Engage" />
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

export function PerformingContentTable({
  content,
  variant = "default",
}: {
  content: DashboardContent[];
  variant?: "default" | "x";
}) {
  const x = variant === "x";
  const [sort, setSort] = useState<{ direction: ContentSortDirection; key: ContentSortKey }>({
    direction: "desc",
    key: "date",
  });
  const rows = useMemo(() => [...content].sort((left, right) => {
    const leftValue = contentSortValue(left, sort.key);
    const rightValue = contentSortValue(right, sort.key);
    if (leftValue === null && rightValue === null) return left.external_content_id.localeCompare(right.external_content_id);
    if (leftValue === null) return 1;
    if (rightValue === null) return -1;
    const compared = typeof leftValue === "number" && typeof rightValue === "number"
      ? leftValue - rightValue
      : String(leftValue).localeCompare(String(rightValue), undefined, { sensitivity: "base" });
    if (compared !== 0) return sort.direction === "asc" ? compared : -compared;
    return left.external_content_id.localeCompare(right.external_content_id);
  }), [content, sort]);
  const sortBy = (key: ContentSortKey) => {
    setSort((current) => current.key === key
      ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
      : { key, direction: defaultContentSortDirection(key) });
  };
  const sortDirection = (key: ContentSortKey) => sort.key === key ? sort.direction : null;
  return (
    <article className="facebook-pulse-table-card">
      <PulseTableHeading title={x ? "All Performing Posts" : "All Performing Content"} />
      <div className="facebook-table-scroll"><table className="facebook-performing-content-table"><thead><tr>
        <th>#</th>
        <th>Cover</th>
        <SortableContentHeader activeDirection={sortDirection("caption")} label="Caption" onSort={() => sortBy("caption")} />
        <SortableContentHeader activeDirection={sortDirection("date")} label="Date" onSort={() => sortBy("date")} />
        <SortableContentHeader activeDirection={sortDirection("type")} label="Type" onSort={() => sortBy("type")} />
        <SortableContentHeader activeDirection={sortDirection("views")} label={x ? "Impressions" : "Post Views"} onSort={() => sortBy("views")} />
        <SortableContentHeader activeDirection={sortDirection("interactions")} label="Interactions" onSort={() => sortBy("interactions")} />
        <SortableContentHeader activeDirection={sortDirection("likes")} label="Likes" onSort={() => sortBy("likes")} />
        <SortableContentHeader activeDirection={sortDirection("comments")} label={x ? "Replies" : "Comments"} onSort={() => sortBy("comments")} />
        <SortableContentHeader activeDirection={sortDirection("shares")} label={x ? "Reposts & Quotes" : "Shares"} onSort={() => sortBy("shares")} />
        {x && <SortableContentHeader activeDirection={sortDirection("saves")} label="Bookmarks" onSort={() => sortBy("saves")} />}
        {x && <SortableContentHeader activeDirection={sortDirection("profile_visits")} label="Profile Visits" onSort={() => sortBy("profile_visits")} />}
        <SortableContentHeader activeDirection={sortDirection("engagement")} label="Engagement" onSort={() => sortBy("engagement")} />
      </tr></thead><tbody>
        {rows.length === 0 ? <tr><td colSpan={x ? 13 : 11}>{x ? "No posts were collected in this period." : "No content was collected in this period."}</td></tr> : rows.map((item, index) => {
          const contentUrl = safeContentUrl(item.permalink);
          const title = item.message || `Untitled ${humanize(item.content_type).toLowerCase()}`;
          const cover = (
            <span className="facebook-content-cover">
              {item.cover_url || item.thumbnail_url || item.media_url
                ? <img alt="" src={item.cover_url || item.thumbnail_url || item.media_url} />
                : <ImageIcon size={17} />}
            </span>
          );
          const caption = <b className="facebook-content-caption" title={title}>{title}</b>;
          const engagement = contentEngagement(item);
          return (
            <tr key={`${item.account_id}-${item.external_content_id}`}>
              <td>{index + 1}</td>
              <td>
                {contentUrl
                  ? <a aria-label={`Open cover: ${title}`} className="facebook-content-cover-link" href={contentUrl} rel="noopener noreferrer" target="_blank">{cover}</a>
                  : cover}
              </td>
              <td>
                {contentUrl
                  ? <a aria-label={`Open content: ${title}`} className="facebook-content-caption-link" href={contentUrl} rel="noopener noreferrer" target="_blank">{caption}</a>
                  : caption}
              </td>
              <td title={item.published_at ?? undefined}>{contentDateLabel(item.published_at)}</td>
              <td><ContentTypeChip contentType={item.content_type} /></td>
              <td>{item.views === null ? "—" : formatNumber(item.views)}</td>
              <td>{compact(item.interactions)}</td>
              <td>{compact(item.likes_count)}</td>
              <td>{compact(item.comments_count)}</td>
              <td>{compact(item.shares_count)}</td>
              {x && <td>{compact(item.saves_count)}</td>}
              {x && <td>{compact(item.profile_visits)}</td>}
              <td>{engagement === null ? "—" : <span className="facebook-engagement-score">{engagement.toFixed(1)}%</span>}</td>
            </tr>
          );
        })}
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
        rows={data.community.top_commenters.map((item, index) => [index + 1, ANONYMOUS_COMMENT_AUTHOR, item.comments, item.likes])}
        subtitle={`${instagram ? "Instagram" : "TikTok"} comment activity leaderboard`}
        title={instagram ? "Most Comments and Messages" : "Most Active Commenters"}
      />
      <SimplePulseTable
        columns={["#", "Username", "Comment", "Likes"]}
        rows={data.community.top_liked_comments.map((item, index) => [
          index + 1,
          ANONYMOUS_COMMENT_AUTHOR,
          item.comment ? maskCommentMentions(item.comment) : "—",
          item.likes,
        ])}
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
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: V1_CHART_COLORS.followers }]} localZoom subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard connectGaps data={data} keys={[...V1_FOLLOWER_FLOW_KEYS]} subtitle={followerFlowSubtitle(data)} title="New Followers Trend" />
      </div>
      <PulseTrendCard bar data={data} keys={[{ id: "reach", label: "Page Reach", color: V1_CHART_COLORS.reach }, { id: "views", label: "Page Views", color: V1_CHART_COLORS.views }]} subtitle="Page Reach and Page Views trend" title="Performance Trends" wide />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={pageViewRows(data)} subtitle="Organic vs paid views" title="Page View Type" />
        <PulseTrendCard data={data} keys={[{ id: "views_organic", label: "Organic Views", color: V1_CHART_COLORS.organicViews }, { id: "views_paid", label: "Paid Views", color: V1_CHART_COLORS.paid }]} subtitle="Organic and paid view delivery" title="Views Source Trend" />
      </div>
      <PulseTrendCard data={data} keys={[{ id: "reach", label: "Reach", color: V1_CHART_COLORS.reach }]} subtitle="Unique people reached over time" title="Reach Trend" wide />
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
        <PulseTrendCard data={data} keys={[{ id: "views", label: "Page Views", color: V1_CHART_COLORS.views }, { id: "reach", label: "Page Reach", color: V1_CHART_COLORS.reach }]} subtitle="Daily page views and reach" title="Views & Reach Trend" />
      </div>
      <div className="facebook-two-three-grid">
        <PulseTrendCard data={data} keys={[{ id: "interactions", label: "Interactions", color: "#f59e0b" }]} subtitle="Likes, comments and shares over time" title="Interaction Trend" />
        <PulsePieCard legendColumns={3} rows={engagementRows(data.content)} subtitle="Interaction mix" title="Engagement Split" />
      </div>
      <div className="facebook-three-grid">
        <PulsePieCard rows={summaryPieRows(data.content_summary.views_by_type, ["#f59e0b", "#ec4899", "#38bdf8", "#14b8a6"])} subtitle="Views by content type" title="Content Type Views" />
        <PulsePieCard rows={sentimentPieRows(data.breakdowns)} subtitle="Classified comment distribution" title="Comment Sentiment" />
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
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: V1_CHART_COLORS.followers }]} localZoom subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard connectGaps data={data} keys={[...V1_FOLLOWER_FLOW_KEYS]} subtitle={followerFlowSubtitle(data)} title="New Followers Trend" />
      </div>
      {/* Page like source and hourly activity are not offered for Facebook
          Pages; the API answers with zeroes or nothing. Audience geography
          is offered, on the day period rather than lifetime. */}
      <div className="facebook-two-grid">
        <SimplePulseTable columns={["#", "Country", "Value"]} rows={countryBreakdownRows(data.breakdowns)} subtitle="Country ranking" title="Top Countries" />
        <SimplePulseTable columns={["#", "City", "Value"]} rows={breakdownRows(data.breakdowns, "city")} subtitle="City ranking" title="Top Cities" />
      </div>
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "views_paid", label: "Paid Views", color: V1_CHART_COLORS.paid }]} subtitle="Paid delivery trend" title="Paid Views Trend" />
        <PulseTrendCard data={data} keys={[{ id: "views_organic", label: "Organic Views", color: "#8b5cf6" }]} subtitle="Organic delivery trend" title="Organic Views Trend" />
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
