import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Eye,
  Heart,
  Image as ImageIcon,
  MessageCircle,
  MousePointerClick,
  Share2,
  Target,
  ThumbsUp,
  Users,
  type LucideIcon,
} from "lucide-react";

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
  };
}

function pageKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    kpiFromMetric(data, "followers", "Followers", Users, "#38bdf8"),
    kpiFromMetric(data, "new_followers", "New Followers", Users, "#14b8a6"),
    kpiFromMetric(data, "reach", "Page Reach", Eye, "#8b5cf6"),
    kpiFromMetric(data, "views", "Page Views", Eye, "#ec4899", ["page_views"]),
    kpiFromMetric(data, "interactions", "Interactions", MessageCircle, "#f59e0b"),
    { id: "frequency", label: "Frequency", value: null, delta: null, icon: Target, color: "#6366f1" },
  ];
}

function contentKpis(data: PlatformDashboard): PulseKpi[] {
  const totals = derivedContentTotals(data.content);
  return [
    { id: "total_posts", label: "Total Posts", value: data.content.length, delta: null, icon: Activity, color: "#8b5cf6" },
    { id: "post_views", label: "Post Views", value: null, delta: null, icon: Eye, color: "#ec4899" },
    { id: "like_reactions", label: "Like Reactions", value: totals.likes, delta: null, icon: ThumbsUp, color: "#ef4444" },
    { id: "comments", label: "Comments", value: totals.comments, delta: null, icon: MessageCircle, color: "#3b82f6" },
    { id: "shares", label: "Shares", value: totals.shares, delta: null, icon: Share2, color: "#22c55e" },
    { id: "post_reach", label: "Post Reach", value: null, delta: null, icon: Target, color: "#38bdf8" },
  ];
}

function audienceKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    kpiFromMetric(data, "followers", "Followers", Users, "#38bdf8"),
    kpiFromMetric(data, "new_followers", "New Followers", Users, "#14b8a6"),
    kpiFromMetric(data, "page_views", "Page Views", Eye, "#06b6d4", ["views"]),
    kpiFromMetric(data, "reach_paid", "Paid Reach", Target, "#ef4444"),
    kpiFromMetric(data, "reach_organic", "Organic Reach", Activity, "#22c55e"),
    { id: "frequency", label: "Frequency", value: null, delta: null, icon: Target, color: "#8b5cf6" },
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
          {item.delta === null ? "No comparison" : `${Math.abs(item.delta).toFixed(1)}%`}
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

type TrendKey = { id: MetricId; label: string; color: string };

function seriesFor(data: PlatformDashboard, id: MetricId): DashboardSeries | undefined {
  return data.series.find((item) => item.metric_id === id);
}

function trendPointString(
  points: DashboardSeries["points"],
  minimum: number,
  maximum: number,
): string {
  const spread = maximum - minimum || 1;
  return points.map((point, index) => {
    const x = points.length === 1 ? 365 : 50 + (index / (points.length - 1)) * 630;
    const y = 170 - ((point.value - minimum) / spread) * 142;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

export function PulseTrendCard({
  data,
  title,
  subtitle,
  keys,
  wide = false,
  bar = false,
}: {
  data: PlatformDashboard;
  title: string;
  subtitle: string;
  keys: TrendKey[];
  wide?: boolean;
  bar?: boolean;
}) {
  const lines = keys.flatMap((key) => {
    const series = seriesFor(data, key.id);
    return series ? [{ ...key, points: series.points }] : [];
  });
  const values = lines.flatMap((line) => line.points.map((point) => point.value));
  const minimum = values.length > 0 ? Math.min(0, ...values) : 0;
  const maximum = values.length > 0 ? Math.max(...values) : 1;
  const dates = lines[0]?.points.map((point) => point.observed_on) ?? [];
  const barSlots = Math.max(1, ...lines.map((line) => line.points.length));
  return (
    <article className={`facebook-pulse-card facebook-trend-card${wide ? " wide" : ""}`}>
      <div className="facebook-pulse-card-heading"><h3>{title}</h3><p>{subtitle}</p></div>
      {values.length === 0 ? <PulseEmpty copy="No observations are available for this metric and date range." /> : bar ? (
        <div className="facebook-pulse-bars" aria-label={title} role="img">
          {Array.from({ length: barSlots }, (_, index) => (
            <span key={index}>{lines.map((line) => {
              const point = line.points[index];
              return <i key={line.id} style={{ background: line.color, height: `${point ? Math.max(4, (point.value / maximum) * 100) : 0}%` }} />;
            })}</span>
          ))}
        </div>
      ) : (
        <svg aria-label={title} className="facebook-pulse-line" preserveAspectRatio="none" role="img" viewBox="0 0 730 190">
          {[28, 63, 98, 133, 168].map((y) => <line key={y} x1="50" x2="680" y1={y} y2={y} />)}
          {lines.map((line) => <polyline fill="none" key={line.id} points={trendPointString(line.points, minimum, maximum)} stroke={line.color} strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" />)}
        </svg>
      )}
      {values.length > 0 && (
        <>
          <div className="facebook-pulse-axis"><span>{dates[0] ?? ""}</span><span>{dates[Math.floor((dates.length - 1) / 2)] ?? ""}</span><span>{dates.at(-1) ?? ""}</span></div>
          <div className="facebook-pulse-legend">{lines.map((line) => <span key={line.id}><i style={{ background: line.color }} />{line.label}</span>)}</div>
        </>
      )}
    </article>
  );
}

export function PulseEmpty({ copy }: { copy: string }) {
  return <div className="facebook-pulse-empty">{copy}</div>;
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

export function PulsePieCard({ title, subtitle, rows }: { title: string; subtitle?: string; rows: PieRow[] }) {
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  return (
    <article className="facebook-pulse-card facebook-pie-card">
      <div className="facebook-pulse-card-heading"><h3>{title}</h3><p>{subtitle}</p></div>
      {total <= 0 ? <PulseEmpty copy="No supported breakdown data is available." /> : (
        <>
          <div className="facebook-pie-wrap"><div className="facebook-pie" style={{ background: pieBackground(rows) }}><span><strong>{formatNumber(total)}</strong><small>Total</small></span></div></div>
          <div className="facebook-pie-legend">{rows.map((row) => <div key={row.label}><span><i style={{ background: row.color }} />{row.label}</span><strong>{((row.value / total) * 100).toFixed(0)}%</strong></div>)}</div>
        </>
      )}
    </article>
  );
}

function metricPie(data: PlatformDashboard, rows: Array<{ id: MetricId; label: string; color: string }>): PieRow[] {
  return rows.flatMap((row) => {
    const current = metricValue(data.metrics, [row.id]);
    return current !== null && current > 0 ? [{ label: row.label, value: current, color: row.color }] : [];
  });
}

function contentTypeRows(content: DashboardContent[]): PieRow[] {
  const counts = new Map<string, number>();
  content.forEach((item) => counts.set(humanize(item.content_type), (counts.get(humanize(item.content_type)) ?? 0) + 1));
  return Array.from(counts.entries()).map(([label, count], index) => ({ label, value: count, color: PALETTE[index % PALETTE.length] ?? "#64748b" }));
}

function engagementRows(content: DashboardContent[]): PieRow[] {
  const totals = derivedContentTotals(content);
  return [
    { label: "Likes", value: totals.likes, color: "#ef4444" },
    { label: "Comments", value: totals.comments, color: "#3b82f6" },
    { label: "Shares", value: totals.shares, color: "#22c55e" },
  ].filter((item) => item.value > 0);
}

export function SimplePulseTable({ title, subtitle, columns, rows }: { title: string; subtitle?: string; columns: string[]; rows: Array<Array<string | number>> }) {
  return (
    <article className="facebook-pulse-card facebook-simple-table">
      <div className="facebook-pulse-card-heading"><h3>{title}</h3><p>{subtitle}</p></div>
      <div className="facebook-table-scroll"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.length === 0 ? <tr><td colSpan={columns.length}>No supported data available</td></tr> : rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div>
    </article>
  );
}

export function breakdownRows(breakdowns: DashboardBreakdown[], hint: string): Array<Array<string | number>> {
  const breakdown = breakdowns.find((item) => item.dimension.toLowerCase().includes(hint));
  return breakdown?.items.slice(0, 10).map((item, index) => [index + 1, humanize(item.key), formatNumber(item.value)]) ?? [];
}

function HeatmapCard() {
  return (
    <article className="facebook-pulse-card facebook-heatmap-card">
      <div className="facebook-pulse-card-heading"><h3>Best Time to Engage</h3><p>Hourly activity density</p></div>
      <PulseEmpty copy="The reporting contract does not return hourly audience activity." />
    </article>
  );
}

export function PerformingContentTable({ content }: { content: DashboardContent[] }) {
  const rows = [...content].sort((left, right) => right.interactions - left.interactions);
  return (
    <article className="facebook-pulse-table-card">
      <div className="facebook-table-title"><h3>All Performing Content</h3><span>Performance</span></div>
      <div className="facebook-table-scroll"><table><thead><tr><th>#</th><th>Cover</th><th>Caption</th><th>Date</th><th>Type</th><th>Post Views</th><th>Post Reach</th><th>Likes</th><th>Comments</th><th>Shares</th><th>Engagement</th></tr></thead><tbody>
        {rows.length === 0 ? <tr><td colSpan={11}>No content data</td></tr> : rows.map((item, index) => (
          <tr key={`${item.account_id}-${item.external_content_id}`}>
            <td>{index + 1}</td>
            <td><span className="facebook-content-cover">{item.media_url ? <img alt="" src={item.media_url} /> : <ImageIcon size={17} />}</span></td>
            <td><span className="facebook-caption" title={item.message}>{item.message || "Caption unavailable"}</span></td>
            <td>{item.published_at ? formatDate(item.published_at) : "—"}</td>
            <td><span className="facebook-type-chip">{humanize(item.content_type)}</span></td>
            <td>—</td><td>—</td><td>{formatNumber(item.likes_count)}</td><td>{formatNumber(item.comments_count)}</td><td>{formatNumber(item.shares_count)}</td><td>—</td>
          </tr>
        ))}
      </tbody></table></div>
    </article>
  );
}

export function ContentWinners({ content }: { content: DashboardContent[] }) {
  const sorted = (field: "likes_count" | "comments_count" | "shares_count") => [...content].sort((left, right) => right[field] - left[field])[0];
  const definitions = [
    { goal: "Most Liked", metric: "Likes", row: sorted("likes_count"), field: "likes_count" as const },
    { goal: "Most Discussed", metric: "Comments", row: sorted("comments_count"), field: "comments_count" as const },
    { goal: "Most Shared", metric: "Shares", row: sorted("shares_count"), field: "shares_count" as const },
  ].filter((item) => item.row);
  return (
    <article className="facebook-pulse-table-card">
      <div className="facebook-table-title stacked"><h3>Content Winners by Objective</h3><p>Best post per objective from current data window</p></div>
      <div className="facebook-table-scroll"><table><thead><tr><th>Objective</th><th>Post</th><th>Metric</th><th>Value</th><th>Context</th></tr></thead><tbody>
        {definitions.length === 0 ? <tr><td colSpan={5}>No content data</td></tr> : definitions.map((item) => <tr key={item.goal}><td><strong>{item.goal}</strong></td><td><span className="facebook-caption">{item.row?.message || "Caption unavailable"}</span></td><td>{item.metric}</td><td><strong>{item.row ? formatNumber(item.row[item.field]) : "—"}</strong></td><td>Current selected date range</td></tr>)}
      </tbody></table></div>
    </article>
  );
}

export function CommentQueue({ title, count, available }: { title: string; count: number; available: boolean }) {
  return (
    <article className="facebook-pulse-table-card facebook-comment-card">
      <div className="facebook-table-title stacked"><h3>{title}</h3><p>{available ? `${formatNumber(count)} comments in summary` : "Comment coverage unavailable"}</p></div>
      <PulseEmpty copy="Comment-level rows are not exposed by this dashboard response." />
    </article>
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
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: "#38bdf8" }]} subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard data={data} keys={[{ id: "new_followers", label: "New Followers", color: "#14b8a6" }]} subtitle="Net follower movement" title="New Followers Trend" />
      </div>
      <PulseTrendCard bar data={data} keys={[{ id: "reach", label: "Page Reach", color: "#8b5cf6" }, { id: "views", label: "Page Views", color: "#5eead4" }]} subtitle="Page Reach and Page Views trend" title="Performance Trends" wide />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={metricPie(data, [{ id: "views_organic", label: "Organic Views", color: "#3b82f6" }, { id: "views_paid", label: "Paid Views", color: "#f59e0b" }])} subtitle="Organic vs paid views" title="Page View Type" />
        <PulseTrendCard data={data} keys={[{ id: "views_organic", label: "Organic Views", color: "#3b82f6" }, { id: "views_paid", label: "Paid Views", color: "#f59e0b" }]} subtitle="Organic and paid view delivery" title="Views Source Trend" />
      </div>
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={metricPie(data, [{ id: "reach_organic", label: "Organic Reach", color: "#22c55e" }, { id: "reach_paid", label: "Paid Reach", color: "#ef4444" }])} subtitle="Organic vs paid Reach" title="Reach Distribution" />
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
        <PulsePieCard rows={contentTypeRows(data.content)} subtitle="Content mix by format" title="Content Type" />
        <PulseTrendCard data={data} keys={[{ id: "views", label: "Page Views", color: "#ec4899" }, { id: "reach", label: "Page Reach", color: "#8b5cf6" }]} subtitle="Daily page views and reach" title="Views & Reach Trend" />
      </div>
      <div className="facebook-two-three-grid">
        <PulseTrendCard data={data} keys={[{ id: "interactions", label: "Interactions", color: "#f59e0b" }]} subtitle="Daily interaction trend" title="Interactions Trend" />
        <PulsePieCard rows={engagementRows(data.content)} subtitle="Comments and shares distribution" title="Engagement Split" />
      </div>
      <div className="facebook-three-grid">
        <PulsePieCard rows={[]} subtitle="Reach distribution by content type" title="Content Type Reach" />
        <PulsePieCard rows={[]} subtitle="Positive, neutral and negative comment mix" title="Comment Sentiment" />
        <SimplePulseTable columns={["Hashtag", "Count"]} rows={[]} subtitle="Hashtag performance ranking" title="Top Hashtags" />
      </div>
      <PerformingContentTable content={data.content} />
      <ContentWinners content={data.content} />
      <div className="facebook-two-grid">
        <CommentQueue available={data.community.data_status !== "unavailable"} count={data.community.unanswered_comments} title="Unanswered Comments Queue" />
        <CommentQueue available={data.community.data_status !== "unavailable"} count={data.community.answered_comments} title="Answered Comments Log" />
      </div>
    </section>
  );
}

function AudienceSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Audience</SectionTitle>}
      <KpiGrid rows={audienceKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: "#38bdf8" }]} subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard data={data} keys={[{ id: "new_followers", label: "New Followers", color: "#14b8a6" }]} subtitle="Net follower movement" title="New Followers Trend" />
      </div>
      <div className="facebook-two-grid">
        <PulsePieCard rows={[]} subtitle="Like source split" title="Page Like Types (Organic vs Paid)" />
        <HeatmapCard />
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
