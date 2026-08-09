import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Bookmark,
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
import { useState } from "react";

import type {
  DashboardContent,
  DashboardMetric,
  DashboardSeries,
  MetricId,
  OverviewDashboard,
  Platform,
  ReportingInsight,
} from "../../api";
import { Link } from "../../routing";
import { Dialog, FollowerAvatarStack } from "../../ui";
import { CoverageNotice } from "../dashboard/DashboardFrame";
import { ExportPng } from "../dashboard/ExportPng";
import { RANGE_OPTIONS, type RangeKey } from "../dashboard/catalog";
import { formatDate, formatNumber, humanize } from "../dashboard/format";

const PLATFORM_COLORS: Record<Platform, string> = {
  facebook: "#5eead4",
  instagram: "#818cf8",
  tiktok: "#111827",
};

const PLATFORM_DISPLAY_ORDER: Platform[] = ["instagram", "facebook", "tiktok"];

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

function PlatformIcon({ platform, size = 17 }: { platform: Platform; size?: number }) {
  if (platform === "facebook") return <Facebook size={size} />;
  if (platform === "instagram") return <Instagram size={size} />;
  return <span aria-hidden="true" className="social-tiktok-mark">♪</span>;
}

type KpiDefinition = {
  label: string;
  value: string;
  metric?: DashboardMetric;
  badge?: string;
  delta?: number | null;
  icon: LucideIcon;
  tone: string;
};

function KpiCard({ definition }: { definition: KpiDefinition }) {
  const delta = definition.delta ?? definition.metric?.delta_pct ?? null;
  return (
    <article className="social-kpi-card">
      <div className="social-kpi-topline">
        <span className={`social-kpi-icon tone-${definition.tone}`}><definition.icon size={20} /></span>
        <span className={`social-kpi-change${delta === null ? " neutral" : delta >= 0 ? " positive" : " negative"}`}>
          {definition.badge ?? (
            <>
              {delta !== null && (delta >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />)}
              {delta === null ? "No comparison" : `${Math.abs(delta).toFixed(1)}%`}
            </>
          )}
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
  return orderedPlatforms(data).flatMap((platformData) => {
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

function orderedPlatforms(data: OverviewDashboard) {
  return [...data.platforms].sort((left, right) => {
    const leftIndex = left.meta.platform ? PLATFORM_DISPLAY_ORDER.indexOf(left.meta.platform) : -1;
    const rightIndex = right.meta.platform ? PLATFORM_DISPLAY_ORDER.indexOf(right.meta.platform) : -1;
    return leftIndex - rightIndex;
  });
}

function bucketLines(lines: ChartLine[], limit = 12): ChartLine[] {
  return lines.map((line) => {
    if (line.points.length <= limit) return line;
    const points = Array.from({ length: limit }, (_, index) => {
      const start = Math.floor((index * line.points.length) / limit);
      const end = Math.max(start + 1, Math.floor(((index + 1) * line.points.length) / limit));
      const bucket = line.points.slice(start, end);
      const first = bucket[0];
      const last = bucket.at(-1);
      return {
        observed_on: first?.observed_on === last?.observed_on
          ? first?.observed_on ?? ""
          : `${first?.observed_on ?? ""} – ${last?.observed_on ?? ""}`,
        value: bucket.reduce((total, point) => total + point.value, 0),
      };
    });
    return { ...line, points };
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

function ChartLegend({ lines }: { lines: ChartLine[] }) {
  return (
    <div className="social-chart-legend">
      {lines.map((line) => <span key={line.name}><i style={{ background: line.color }} />{line.name}</span>)}
    </div>
  );
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
        {allValues.length > 0 && <ChartLegend lines={lines} />}
      </div>
      {allValues.length === 0 ? (
        <div className="social-chart-empty">No follower observations in this range.</div>
      ) : (
        <>
          <svg aria-label="Audience growth by platform" className="social-line-chart" preserveAspectRatio="none" role="img" viewBox="0 0 380 160">
            <defs>
              {lines.map((line, index) => (
                <linearGradient id={`overview-line-${index}`} key={line.name} x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor={line.color} stopOpacity="0.2" />
                  <stop offset="100%" stopColor={line.color} stopOpacity="0" />
                </linearGradient>
              ))}
            </defs>
            {[26, 55, 84, 113, 142].map((y) => <line key={y} x1="18" x2="362" y1={y} y2={y} />)}
            {lines.map((line, index) => {
              const points = linePoints(line.points.map((point) => point.value), minimum, maximum);
              return (
                <g key={line.name}>
                  <polygon fill={`url(#overview-line-${index})`} points={`${points} 362,142 18,142`} />
                  <polyline fill="none" points={points} stroke={line.color} strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" />
                </g>
              );
            })}
          </svg>
          <div className="social-chart-axis">
            <span>{labels[0] ?? ""}</span>
            <span>{labels[Math.floor((labels.length - 1) / 2)] ?? ""}</span>
            <span>{labels.at(-1) ?? ""}</span>
          </div>
        </>
      )}
    </article>
  );
}

function CrossChannelChart({ lines }: { lines: ChartLine[] }) {
  const visibleLines = bucketLines(lines);
  const maximum = Math.max(1, ...visibleLines.flatMap((line) => line.points.map((point) => point.value)));
  const slots = Math.max(1, ...visibleLines.map((line) => line.points.length));
  const labels = visibleLines[0]?.points.map((point) => point.observed_on) ?? [];
  return (
    <article className="social-chart-card">
      <div className="social-card-heading">
        <div><h2>Cross-Channel</h2><p>Daily interaction</p></div>
        {visibleLines.some((line) => line.points.length > 0) && <ChartLegend lines={visibleLines} />}
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
          <div className="social-chart-axis">
            <span>{labels[0] ?? ""}</span>
            <span>{labels[Math.floor((labels.length - 1) / 2)] ?? ""}</span>
            <span>{labels.at(-1) ?? ""}</span>
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
  const ranked = Array.from(counts.entries()).sort((left, right) => right[1] - left[1]);
  const visible = ranked.length <= 4
    ? ranked
    : [
        ...ranked.slice(0, 3),
        ["Other", ranked.slice(3).reduce((sum, [, count]) => sum + count, 0)] as [string, number],
      ];
  return visible.map(([label, count], index) => ({
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

function AIInsightBanner({
  insight,
  loading,
  error,
  onOpen,
}: {
  insight?: ReportingInsight;
  loading: boolean;
  error: boolean;
  onOpen: () => void;
}) {
  return (
    <article className="social-ai-card">
      <div className="social-ai-content">
        <span className="social-ai-icon"><Sparkles size={27} /></span>
        <div>
          <div className="social-ai-title"><h2>AI Insights</h2><span>{insight ? humanize(insight.status) : "New"}</span></div>
          <p>Leverage our predictive algorithms to detect trends before they peak. Auto-scale your best performing content across all connected channels instantly.</p>
        </div>
        <button className="social-ai-button" disabled={loading} onClick={onOpen} type="button">
          <Sparkles size={15} /> {loading ? "Loading…" : "Open AI Insights"}
        </button>
      </div>
      {error && <span className="social-ai-error">Stored insight is temporarily unavailable.</span>}
    </article>
  );
}

function AIInsightDialog({
  open,
  brandName,
  insight,
  loading,
  error,
  onClose,
}: {
  open: boolean;
  brandName: string;
  insight?: ReportingInsight;
  loading: boolean;
  error: boolean;
  onClose: () => void;
}) {
  return (
    <Dialog description={brandName} onClose={onClose} open={open} title="AI Insights">
      <div className="social-insight-dialog-content">
        {loading ? (
          <div className="social-insight-dialog-state">Loading stored insight…</div>
        ) : error ? (
          <div className="social-insight-dialog-state error">Stored insight could not be loaded.</div>
        ) : insight ? (
          <div className="social-insight-dialog-body">
            <span>{humanize(insight.status)}</span>
            <h3>Strategic Summary</h3>
            <p>{insight.summary || "No summary was stored for this reporting period."}</p>
            <h3>Recommendations</h3>
            <p>{insight.recommendations || "No recommendations were stored for this reporting period."}</p>
            <small>{insight.date_from || "—"} – {insight.date_to || "—"}</small>
          </div>
        ) : (
          <div className="social-insight-dialog-state">No generated insight exists for this Brand and date range.</div>
        )}
      </div>
    </Dialog>
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
    { label: "Saves", value: null, icon: Bookmark, tone: "emerald" },
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
          <thead><tr><th>#</th><th>Post Name</th><th>Platform</th><th>Date</th><th>Type</th><th>Imp.</th><th>Interactions</th><th>Engagement Rate</th></tr></thead>
          <tbody>
            {posts.length === 0 && <tr><td className="social-table-empty" colSpan={8}>No top post data available for the selected date range.</td></tr>}
            {posts.map((post, index) => {
              const platform = platforms.get(post.account_id);
              const impressionValue = post.views ?? post.reach;
              const engagementRate = post.reach && post.reach > 0
                ? post.interactions / post.reach
                : null;
              const thumbnail = post.cover_url || post.thumbnail_url || post.media_url;
              return (
                <tr key={`${post.account_id}-${post.external_content_id}`}>
                  <td>{index + 1}</td>
                  <td>
                    <div className="social-post-cell">
                      <span className="social-post-thumb">{thumbnail ? <img alt="" src={thumbnail} /> : <Layers3 size={17} />}</span>
                      {post.permalink ? <a href={post.permalink} rel="noreferrer" target="_blank">{post.message || "Caption unavailable"}</a> : <span>{post.message || "Caption unavailable"}</span>}
                    </div>
                  </td>
                  <td>{platform ? <span className={`social-platform-label platform-${platform}`}><PlatformIcon platform={platform} />{PLATFORM_NAMES[platform]}</span> : "—"}</td>
                  <td>{post.published_at ? formatDate(post.published_at) : "—"}</td>
                  <td>{humanize(post.content_type)}</td>
                  <td>{displayValue(impressionValue)}</td>
                  <td className="social-cell-strong">{formatNumber(post.interactions)}</td>
                  <td className="social-cell-strong">{engagementRate === null ? "—" : `${(engagementRate * 100).toFixed(1)}%`}</td>
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
        {orderedPlatforms(data).map((platformData) => {
          const platform = platformData.meta.platform;
          if (!platform) return null;
          const followers = value(platformData.metrics, "followers");
          const interactions = value(platformData.metrics, "interactions") ?? value(platformData.metrics, "video_engagements_total");
          const reach = value(platformData.metrics, "reach");
          const reportedEngagementRate = value(platformData.metrics, "engagement_rate")
            ?? value(platformData.metrics, "video_engagement_rate");
          const engagementRate = reportedEngagementRate ?? (
            interactions !== null && reach !== null && reach > 0
              ? interactions / reach
              : null
          );
          const available = platformData.meta.data_status !== "unavailable";
          const content = (
            <>
              <div className="social-platform-card-top">
                <span className={`social-platform-card-icon platform-${platform}`}><PlatformIcon platform={platform} size={27} /></span>
                <span className="social-platform-card-arrow">{available ? <ArrowUpRight size={20} /> : "SOON"}</span>
              </div>
              <h3>{PLATFORM_NAMES[platform]}</h3>
              {available ? (
                <div className="social-platform-card-metrics">
                  <strong>{displayValue(followers)}</strong><span>followers</span>
                  <p>{engagementRate === null ? "—" : `${(engagementRate * 100).toFixed(1)}%`} <small>engagement rate</small></p>
                </div>
              ) : (
                <p className="social-platform-card-unavailable">Integration is not available for this Brand.</p>
              )}
            </>
          );
          return (
            available ? (
              <Link className="social-platform-card" key={platform} to={`/${platform}`}>{content}</Link>
            ) : (
              <article className="social-platform-card unavailable" key={platform}>{content}</article>
            )
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
  const [insightOpen, setInsightOpen] = useState(false);
  const audienceMetric = metric(data.metrics, "followers");
  const reachMetric = metric(data.metrics, "reach");
  const viewsMetric = metric(data.metrics, "views");
  const interactionsMetric = metric(data.metrics, "interactions");
  const engagementRate = interactionsMetric?.value !== null
    && interactionsMetric?.value !== undefined
    && reachMetric?.value !== null
    && reachMetric?.value !== undefined
    && reachMetric.value > 0
    ? interactionsMetric.value / reachMetric.value
    : null;
  const previousEngagementRate = interactionsMetric?.previous_value !== null
    && interactionsMetric?.previous_value !== undefined
    && reachMetric?.previous_value !== null
    && reachMetric?.previous_value !== undefined
    && reachMetric.previous_value > 0
    ? interactionsMetric.previous_value / reachMetric.previous_value
    : null;
  const engagementDelta = engagementRate !== null
    && previousEngagementRate !== null
    && previousEngagementRate !== 0
    ? ((engagementRate - previousEngagementRate) / Math.abs(previousEngagementRate)) * 100
    : null;
  const activityScore = engagementRate === null
    ? null
    : Math.max(0, Math.min(100, Math.round((engagementRate * 100 * 6) + ((reachMetric?.delta_pct ?? 0) * 0.4))));
  const activityBadge = activityScore === null
    ? "Unavailable"
    : activityScore >= 80
      ? "Excellent"
      : activityScore >= 60
        ? "Good"
        : "Needs Improvement";
  const kpis: KpiDefinition[] = [
    { label: "Total Reach", value: displayValue(reachMetric?.value ?? null), metric: reachMetric, icon: Users, tone: "rose" },
    { label: "Total Impressions", value: displayValue(viewsMetric?.value ?? null), metric: viewsMetric, icon: Eye, tone: "violet" },
    { label: "Total Interactions", value: displayValue(interactionsMetric?.value ?? null), metric: interactionsMetric, icon: MessageCircle, tone: "blue" },
    { label: "Avg. Engagement", value: engagementRate === null ? "—" : `${(engagementRate * 100).toFixed(1)}%`, delta: engagementDelta, icon: MousePointerClick, tone: "indigo" },
    { label: "Activity Score", value: activityScore === null ? "—" : String(activityScore), badge: activityBadge, icon: Layers3, tone: "amber" },
  ];
  const audienceLines = bucketLines(chartLines(data, ["new_followers", "followers"]));
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
              {orderedPlatforms(data).slice(0, 3).map((platformData) => platformData.meta.platform && <i className={`platform-${platformData.meta.platform}`} key={platformData.meta.platform}><PlatformIcon platform={platformData.meta.platform} size={15} /></i>)}
            </span>
          </label>
          <ExportPng metrics={data.metrics} subtitle={`${brandName} · ${data.meta.date_range.start_on} to ${data.meta.date_range.end_on}`} title="Social Media Overview" />
        </div>
      </header>

      {data.meta.data_status !== "available" && (
        <CoverageNotice status={data.meta.data_status} warnings={data.meta.warnings} />
      )}

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
        <AIInsightBanner error={insightsError} insight={insights[0]} loading={insightsLoading} onOpen={() => setInsightOpen(true)} />
        <ActionBreakdown data={data} />
      </section>

      <TopPosts data={data} />
      <PlatformBreakdown data={data} />
      <AIInsightDialog
        brandName={brandName}
        error={insightsError}
        insight={insights[0]}
        loading={insightsLoading}
        onClose={() => setInsightOpen(false)}
        open={insightOpen}
      />
    </main>
  );
}
