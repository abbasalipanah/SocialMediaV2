import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  CalendarDays,
  Eye,
  Facebook,
  Heart,
  Instagram,
  Layers3,
  MessageCircle,
  MousePointerClick,
  PieChart,
  Share2,
  Sparkles,
  Users,
  type LucideIcon,
} from "lucide-react";

import type {
  DashboardContent,
  DashboardMetric,
  DashboardSeries,
  MetricId,
  OverviewDashboard,
  Platform,
  ReportingInsight,
} from "../../api";
import { FollowerAvatarStack } from "../../ui";
import { CoverageNotice } from "../dashboard/DashboardFrame";
import { ExportPng } from "../dashboard/ExportPng";
import { RANGE_OPTIONS, type RangeKey } from "../dashboard/catalog";
import { formatDate, formatNumber, humanize } from "../dashboard/format";

const PLATFORM_COLORS: Record<Platform, string> = {
  facebook: "#1877f2",
  instagram: "#d946ef",
  tiktok: "#111827",
};

const PLATFORM_NAMES: Record<Platform, string> = {
  facebook: "Facebook",
  instagram: "Instagram",
  tiktok: "TikTok",
};

function metric(metrics: DashboardMetric[], id: MetricId): DashboardMetric | undefined {
  return metrics.find((item) => item.metric_id === id);
}

function value(metrics: DashboardMetric[], id: MetricId): number | null {
  return metric(metrics, id)?.value ?? null;
}

function displayValue(metricValue: number | null, suffix = ""): string {
  return metricValue === null ? "—" : `${formatNumber(metricValue)}${suffix}`;
}

function changeLabel(item: DashboardMetric | undefined): string {
  if (!item || item.delta_pct === null) return "No comparison";
  return `${Math.abs(item.delta_pct).toFixed(1)}%`;
}

function PlatformIcon({ platform, size = 17 }: { platform: Platform; size?: number }) {
  if (platform === "facebook") return <Facebook size={size} />;
  if (platform === "instagram") return <Instagram size={size} />;
  return <span aria-hidden="true" className="social-tiktok-mark">♪</span>;
}

type KpiDefinition = {
  label: string;
  value: string;
  metric?: DashboardMetric;
  icon: LucideIcon;
  tone: string;
};

function KpiCard({ definition }: { definition: KpiDefinition }) {
  const delta = definition.metric?.delta_pct ?? null;
  return (
    <article className="social-kpi-card">
      <div className="social-kpi-topline">
        <span className={`social-kpi-icon tone-${definition.tone}`}><definition.icon size={20} /></span>
        <span className={`social-kpi-change${delta === null ? " neutral" : delta >= 0 ? " positive" : " negative"}`}>
          {delta !== null && (delta >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />)}
          {changeLabel(definition.metric)}
        </span>
      </div>
      <strong>{definition.value}</strong>
      <span className="social-kpi-label">{definition.label}</span>
    </article>
  );
}

type ChartLine = {
  name: string;
  color: string;
  points: DashboardSeries["points"];
};

function chartLines(data: OverviewDashboard, metricIds: MetricId[]): ChartLine[] {
  return data.platforms.flatMap((platformData) => {
    const platform = platformData.meta.platform;
    if (!platform) return [];
    const series = metricIds
      .map((metricId) => platformData.series.find((item) => item.metric_id === metricId))
      .find(Boolean);
    return series
      ? [{ name: PLATFORM_NAMES[platform], color: PLATFORM_COLORS[platform], points: series.points }]
      : [];
  });
}

function linePoints(values: number[], minimum: number, maximum: number): string {
  const spread = maximum - minimum || 1;
  return values
    .map((item, index) => {
      const x = values.length === 1 ? 180 : 18 + (index / (values.length - 1)) * 344;
      const y = 142 - ((item - minimum) / spread) * 116;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function AudienceGrowthChart({ lines }: { lines: ChartLine[] }) {
  const allValues = lines.flatMap((line) => line.points.map((point) => point.value));
  const minimum = allValues.length > 0 ? Math.min(...allValues) : 0;
  const maximum = allValues.length > 0 ? Math.max(...allValues) : 1;
  const labels = lines[0]?.points.map((point) => point.observed_on) ?? [];
  return (
    <article className="social-chart-card">
      <div className="social-card-heading">
        <div><h2>Audience Growth</h2><p>Net follower growth</p></div>
      </div>
      {allValues.length === 0 ? (
        <div className="social-chart-empty">No follower observations in this range.</div>
      ) : (
        <>
          <svg aria-label="Audience growth by platform" className="social-line-chart" preserveAspectRatio="none" role="img" viewBox="0 0 380 160">
            {[26, 55, 84, 113, 142].map((y) => <line key={y} x1="18" x2="362" y1={y} y2={y} />)}
            {lines.map((line) => (
              <polyline
                fill="none"
                key={line.name}
                points={linePoints(line.points.map((point) => point.value), minimum, maximum)}
                stroke={line.color}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2.5"
              />
            ))}
          </svg>
          <div className="social-chart-axis">
            <span>{labels[0] ?? ""}</span>
            <span>{labels[Math.floor((labels.length - 1) / 2)] ?? ""}</span>
            <span>{labels.at(-1) ?? ""}</span>
          </div>
          <div className="social-chart-legend">
            {lines.map((line) => <span key={line.name}><i style={{ background: line.color }} />{line.name}</span>)}
          </div>
        </>
      )}
    </article>
  );
}

function CrossChannelChart({ lines }: { lines: ChartLine[] }) {
  const visibleLines = lines.map((line) => ({ ...line, points: line.points.slice(-7) }));
  const maximum = Math.max(1, ...visibleLines.flatMap((line) => line.points.map((point) => point.value)));
  const slots = Math.max(1, ...visibleLines.map((line) => line.points.length));
  return (
    <article className="social-chart-card">
      <div className="social-card-heading">
        <div><h2>Cross-Channel</h2><p>Daily interaction</p></div>
      </div>
      {visibleLines.every((line) => line.points.length === 0) ? (
        <div className="social-chart-empty">No interaction observations in this range.</div>
      ) : (
        <>
          <div aria-label="Cross-channel daily interaction" className="social-bar-chart" role="img">
            {Array.from({ length: slots }, (_, index) => (
              <div className="social-bar-slot" key={index}>
                {visibleLines.map((line) => {
                  const point = line.points[index];
                  return (
                    <i
                      key={line.name}
                      style={{ background: line.color, height: `${point ? Math.max(5, (point.value / maximum) * 100) : 0}%` }}
                      title={point ? `${line.name}: ${formatNumber(point.value)}` : `${line.name}: unavailable`}
                    />
                  );
                })}
              </div>
            ))}
          </div>
          <div className="social-chart-legend">
            {visibleLines.map((line) => <span key={line.name}><i style={{ background: line.color }} />{line.name}</span>)}
          </div>
        </>
      )}
    </article>
  );
}

const DONUT_COLORS = ["#6366f1", "#ec4899", "#0ea5e9", "#f59e0b", "#10b981", "#64748b"];

function contentDistribution(content: DashboardContent[]) {
  const counts = new Map<string, number>();
  content.forEach((item) => counts.set(humanize(item.content_type), (counts.get(humanize(item.content_type)) ?? 0) + 1));
  const total = Math.max(1, content.length);
  return Array.from(counts.entries()).map(([label, count], index) => ({
    label,
    count,
    percentage: (count / total) * 100,
    color: DONUT_COLORS[index % DONUT_COLORS.length] ?? "#64748b",
  }));
}

function donutBackground(distribution: ReturnType<typeof contentDistribution>): string {
  if (distribution.length === 0) return "#eef2f7";
  let start = 0;
  const stops = distribution.map((item) => {
    const end = start + item.percentage;
    const stop = `${item.color} ${start.toFixed(2)}% ${end.toFixed(2)}%`;
    start = end;
    return stop;
  });
  return `conic-gradient(${stops.join(", ")})`;
}

function ContentTypeChart({ content }: { content: DashboardContent[] }) {
  const distribution = contentDistribution(content);
  return (
    <article className="social-chart-card">
      <div className="social-card-heading">
        <div><h2>Content Type</h2><p>Post breakdown</p></div>
        <span className="social-heading-icon"><PieChart size={20} /></span>
      </div>
      <div className="social-donut-wrap">
        <div className="social-donut" style={{ background: donutBackground(distribution) }}>
          <div><strong>{content.length}</strong><span>Content</span></div>
        </div>
      </div>
      <div className="social-donut-legend">
        {distribution.length === 0 ? <span>No content distribution data.</span> : distribution.map((item) => (
          <div key={item.label}><span><i style={{ background: item.color }} />{item.label}</span><strong>{item.percentage.toFixed(0)}%</strong></div>
        ))}
      </div>
    </article>
  );
}

function AIInsightBanner({ insight, loading, error }: { insight?: ReportingInsight; loading: boolean; error: boolean }) {
  const copy = loading
    ? "Loading the stored insight for this Brand and date range…"
    : error
      ? "Reporting is available, but the stored insight could not be loaded."
      : insight?.summary || "No generated insight exists for this Brand and date range.";
  return (
    <article className="social-ai-card">
      <div className="social-ai-content">
        <span className="social-ai-icon"><Sparkles size={27} /></span>
        <div>
          <div className="social-ai-title"><h2>AI Insights</h2><span>{insight ? humanize(insight.status) : "Stored only"}</span></div>
          <p>{copy}</p>
          {insight?.recommendations && <small>{insight.recommendations}</small>}
        </div>
      </div>
    </article>
  );
}

function ActionBreakdown({ data }: { data: OverviewDashboard }) {
  const totals = data.content.reduce(
    (current, item) => ({
      likes: current.likes + item.likes_count,
      comments: current.comments + item.comments_count,
      shares: current.shares + item.shares_count,
    }),
    { likes: 0, comments: 0, shares: 0 },
  );
  const actions = [
    { label: "Likes", value: totals.likes, icon: Heart, tone: "rose" },
    { label: "Comments", value: totals.comments, icon: MessageCircle, tone: "blue" },
    { label: "Clicks", value: value(data.metrics, "website_clicks"), icon: MousePointerClick, tone: "indigo" },
    { label: "Shares", value: totals.shares, icon: Share2, tone: "amber" },
    { label: "Saves", value: null, icon: Layers3, tone: "emerald" },
    { label: "Reactions", value: value(data.metrics, "reactions"), icon: Activity, tone: "violet" },
  ];
  return (
    <article className="social-action-card">
      <h2><MousePointerClick size={16} />Action Breakdown</h2>
      <div>
        {actions.map((action) => (
          <span className="social-action-item" key={action.label}>
            <i className={`tone-${action.tone}`}><action.icon size={14} /></i>
            <span><strong>{displayValue(action.value)}</strong><small>{action.label}</small></span>
          </span>
        ))}
      </div>
    </article>
  );
}

function contentPlatformMap(data: OverviewDashboard): Map<number, Platform> {
  const map = new Map<number, Platform>();
  data.platforms.forEach((platformData) => {
    if (!platformData.meta.platform) return;
    platformData.content.forEach((item) => map.set(item.account_id, platformData.meta.platform as Platform));
  });
  return map;
}

function TopPosts({ data }: { data: OverviewDashboard }) {
  const platforms = contentPlatformMap(data);
  const posts = [...data.content].sort((left, right) => right.interactions - left.interactions).slice(0, 10);
  return (
    <section className="social-table-card">
      <h2>Top Performing Posts</h2>
      <div className="social-table-scroll">
        <table>
          <thead><tr><th>#</th><th>Post Name</th><th>Platform</th><th>Date</th><th>Type</th><th>Likes</th><th>Interactions</th><th>Engagement Rate</th></tr></thead>
          <tbody>
            {posts.length === 0 && <tr><td className="social-table-empty" colSpan={8}>No top post data available for the selected date range.</td></tr>}
            {posts.map((post, index) => {
              const platform = platforms.get(post.account_id);
              return (
                <tr key={`${post.account_id}-${post.external_content_id}`}>
                  <td>{index + 1}</td>
                  <td>
                    <div className="social-post-cell">
                      <span className="social-post-thumb">{post.media_url ? <img alt="" src={post.media_url} /> : <Layers3 size={17} />}</span>
                      {post.permalink ? <a href={post.permalink} rel="noreferrer" target="_blank">{post.message || "Caption unavailable"}</a> : <span>{post.message || "Caption unavailable"}</span>}
                    </div>
                  </td>
                  <td>{platform ? <span className={`social-platform-label platform-${platform}`}><PlatformIcon platform={platform} />{PLATFORM_NAMES[platform]}</span> : "—"}</td>
                  <td>{post.published_at ? formatDate(post.published_at) : "—"}</td>
                  <td>{humanize(post.content_type)}</td>
                  <td>{formatNumber(post.likes_count)}</td>
                  <td className="social-cell-strong">{formatNumber(post.interactions)}</td>
                  <td title="Impression coverage is not available in the content contract">—</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PlatformBreakdown({ data }: { data: OverviewDashboard }) {
  return (
    <section className="social-platform-section">
      <h2><Layers3 size={20} />Platform Breakdown</h2>
      <div className="social-platform-grid">
        {data.platforms.map((platformData) => {
          const platform = platformData.meta.platform;
          if (!platform) return null;
          const followers = value(platformData.metrics, "followers");
          const interactions = value(platformData.metrics, "interactions") ?? value(platformData.metrics, "video_engagements_total");
          return (
            <article key={platform}>
              <div className="social-platform-card-top">
                <span className={`social-platform-card-icon platform-${platform}`}><PlatformIcon platform={platform} size={25} /></span>
                <span className={`social-health-pill status-${platformData.meta.data_status}`}>{humanize(platformData.meta.data_status)}</span>
              </div>
              <h3>{PLATFORM_NAMES[platform]}</h3>
              <p>{humanize(platformData.meta.freshness)} · Last sync {formatDate(platformData.meta.last_sync_at)}</p>
              <dl>
                <div><dt>Audience</dt><dd>{displayValue(followers)}</dd></div>
                <div><dt>Interactions</dt><dd>{displayValue(interactions)}</dd></div>
              </dl>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function AccumulateSocialOverview({
  data,
  range,
  onRange,
  brandName,
  insights,
  insightsLoading,
  insightsError,
}: {
  data: OverviewDashboard;
  range: RangeKey;
  onRange: (range: RangeKey) => void;
  brandName: string;
  insights: ReportingInsight[];
  insightsLoading: boolean;
  insightsError: boolean;
}) {
  const audienceMetric = metric(data.metrics, "followers");
  const reachMetric = metric(data.metrics, "reach");
  const viewsMetric = metric(data.metrics, "views");
  const interactionsMetric = metric(data.metrics, "interactions");
  const newFollowersMetric = metric(data.metrics, "new_followers");
  const coverage = data.platforms.filter((item) => item.meta.data_status === "available").length;
  const kpis: KpiDefinition[] = [
    { label: "Reach", value: displayValue(reachMetric?.value ?? null), metric: reachMetric, icon: Eye, tone: "indigo" },
    { label: "Views", value: displayValue(viewsMetric?.value ?? null), metric: viewsMetric, icon: BarChart3, tone: "blue" },
    { label: "Interactions", value: displayValue(interactionsMetric?.value ?? null), metric: interactionsMetric, icon: Activity, tone: "rose" },
    { label: "New Followers", value: displayValue(newFollowersMetric?.value ?? null), metric: newFollowersMetric, icon: Users, tone: "emerald" },
    { label: "Data Coverage", value: `${coverage}/${data.platforms.length}`, icon: Layers3, tone: "violet" },
  ];
  const audienceLines = chartLines(data, ["new_followers", "followers"]);
  const interactionLines = chartLines(data, ["interactions", "video_engagements_total"]);

  return (
    <main className="social-overview-page">
      <header className="social-overview-header">
        <div>
          <h1>Social Media Overview</h1>
          <p>Unified performance monitor across all connected channels.</p>
        </div>
        <div className="social-overview-controls">
          <label className="social-range-card">
            <span className="social-range-icon"><CalendarDays size={18} /></span>
            <span><small>Date Period</small><select aria-label="Date period" onChange={(event) => onRange(event.target.value as RangeKey)} value={range}>{RANGE_OPTIONS.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></span>
            <span className="social-connected-icons" aria-label="Connected platforms">
              {data.platforms.slice(0, 3).map((platformData) => platformData.meta.platform && <i className={`platform-${platformData.meta.platform}`} key={platformData.meta.platform}><PlatformIcon platform={platformData.meta.platform} size={15} /></i>)}
            </span>
          </label>
          <ExportPng metrics={data.metrics} subtitle={`${brandName} · ${data.meta.date_range.start_on} to ${data.meta.date_range.end_on}`} title="Social Media Overview" />
        </div>
      </header>

      <CoverageNotice status={data.meta.data_status} warnings={data.meta.warnings} />

      <section aria-label="Key performance indicators" className="social-kpi-grid">
        <article className="social-kpi-card social-audience-kpi">
          <FollowerAvatarStack />
          <strong>{displayValue(audienceMetric?.value ?? null)}</strong>
          <span className="social-kpi-label">Total Audience</span>
        </article>
        {kpis.map((definition) => <KpiCard definition={definition} key={definition.label} />)}
      </section>

      <section className="social-chart-grid">
        <AudienceGrowthChart lines={audienceLines} />
        <CrossChannelChart lines={interactionLines} />
        <ContentTypeChart content={data.content} />
      </section>

      <section className="social-insight-grid">
        <AIInsightBanner error={insightsError} insight={insights[0]} loading={insightsLoading} />
        <ActionBreakdown data={data} />
      </section>

      <TopPosts data={data} />
      <PlatformBreakdown data={data} />
    </main>
  );
}
