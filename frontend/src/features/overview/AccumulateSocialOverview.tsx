import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  Eye,
  Facebook,
  Heart,
  Instagram,
  Lightbulb,
  MessageCircle,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useMemo, useState } from "react";

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
import { Dialog } from "../../ui";
import { CoverageNotice } from "../dashboard/DashboardFrame";
import { ExportPng } from "../dashboard/ExportPng";
import { RANGE_OPTIONS, type RangeKey } from "../dashboard/catalog";
import { formatDate, formatNumber, humanize } from "../dashboard/format";

const PLATFORM_DISPLAY_ORDER: Platform[] = ["instagram", "facebook", "tiktok"];

const PLATFORM_NAMES: Record<Platform, string> = {
  facebook: "Facebook",
  instagram: "Instagram",
  tiktok: "TikTok",
};

const PLATFORM_COLORS: Record<Platform, string> = {
  facebook: "#2563eb",
  instagram: "#ec4899",
  tiktok: "#111827",
};

type SeriesPoint = DashboardSeries["points"][number];

type ChartLine = {
  name: string;
  color: string;
  points: SeriesPoint[];
};

type TrendMode = "performance" | "reach" | "engagement" | "audience";

function metric(metrics: DashboardMetric[], id: MetricId): DashboardMetric | undefined {
  return metrics.find((item) => item.metric_id === id);
}

function value(metrics: DashboardMetric[], id: MetricId): number | null {
  return metric(metrics, id)?.value ?? null;
}

function firstMetric(metrics: DashboardMetric[], ids: MetricId[]): DashboardMetric | undefined {
  return ids.map((id) => metric(metrics, id)).find((item) => item?.value !== null && item?.value !== undefined);
}

function displayValue(metricValue: number | null): string {
  return metricValue === null ? "—" : formatNumber(metricValue);
}

function formatDateOnly(rawDate: string): string {
  return new Intl.DateTimeFormat("en-US", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${rawDate.slice(0, 10)}T00:00:00Z`));
}

function percentValue(rate: number | null): string {
  return rate === null ? "—" : `${(rate * 100).toFixed(1)}%`;
}

function orderedPlatforms(data: OverviewDashboard) {
  return [...data.platforms].sort((left, right) => {
    const leftIndex = left.meta.platform ? PLATFORM_DISPLAY_ORDER.indexOf(left.meta.platform) : 99;
    const rightIndex = right.meta.platform ? PLATFORM_DISPLAY_ORDER.indexOf(right.meta.platform) : 99;
    return leftIndex - rightIndex;
  });
}

function PlatformIcon({ platform, size = 17 }: { platform: Platform; size?: number }) {
  if (platform === "facebook") return <Facebook size={size} />;
  if (platform === "instagram") return <Instagram size={size} />;
  return <span aria-hidden="true" className="social-tiktok-mark">♪</span>;
}

function linePoints(values: number[], minimum: number, maximum: number, width = 360, height = 126): string {
  const spread = maximum - minimum || 1;
  return values
    .map((item, index) => {
      const x = values.length === 1 ? width / 2 : 8 + (index / (values.length - 1)) * (width - 16);
      const y = height - 8 - ((item - minimum) / spread) * (height - 16);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function MiniSparkline({ points, color }: { points: SeriesPoint[]; color: string }) {
  if (points.length === 0) return <span className="overview-sparkline-empty">No trend data</span>;
  const values = points.map((point) => point.value);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const coordinates = linePoints(values, minimum, maximum, 180, 44);
  return (
    <svg aria-hidden="true" className="overview-mini-sparkline" preserveAspectRatio="none" viewBox="0 0 180 44">
      <polyline fill="none" points={coordinates} stroke={color} strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" />
      {values.length === 1 && <circle cx="90" cy="22" fill={color} r="2.5" />}
    </svg>
  );
}

function seriesForPlatform(
  platformData: OverviewDashboard["platforms"][number],
  metricIds: MetricId[],
): DashboardSeries | undefined {
  return metricIds.map((id) => platformData.series.find((series) => series.metric_id === id)).find(Boolean);
}

function aggregatePoints(data: OverviewDashboard, metricIds: MetricId[]): SeriesPoint[] {
  const totals = new Map<string, number>();
  orderedPlatforms(data).forEach((platformData) => {
    const series = seriesForPlatform(platformData, metricIds);
    series?.points.forEach((point) => totals.set(point.observed_on, (totals.get(point.observed_on) ?? 0) + point.value));
  });
  return [...totals.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([observed_on, pointValue]) => ({ observed_on, value: pointValue }));
}

function ratioPoints(numerator: SeriesPoint[], denominator: SeriesPoint[]): SeriesPoint[] {
  const denominatorByDate = new Map(denominator.map((point) => [point.observed_on, point.value]));
  return numerator.flatMap((point) => {
    const denominatorValue = denominatorByDate.get(point.observed_on);
    return denominatorValue && denominatorValue > 0
      ? [{ observed_on: point.observed_on, value: (point.value / denominatorValue) * 100 }]
      : [];
  });
}

function platformEngagementRate(platformData: OverviewDashboard["platforms"][number]): number | null {
  const reported = firstMetric(platformData.metrics, ["engagement_rate", "video_engagement_rate"])?.value;
  if (reported !== null && reported !== undefined) return reported;
  const interactions = firstMetric(platformData.metrics, ["interactions", "video_engagements_total"])?.value;
  const reach = value(platformData.metrics, "reach");
  return interactions !== null && interactions !== undefined && reach !== null && reach > 0
    ? interactions / reach
    : null;
}

function deltaClass(delta: number | null): string {
  if (delta === null) return "neutral";
  return delta >= 0 ? "positive" : "negative";
}

function Delta({ delta, suffix = "%" }: { delta: number | null; suffix?: string }) {
  return (
    <span className={`overview-delta ${deltaClass(delta)}`}>
      {delta === null ? null : delta >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
      {delta === null ? "No comparison" : `${Math.abs(delta).toFixed(1)}${suffix}`}
    </span>
  );
}

type KpiDefinition = {
  label: string;
  display: string;
  delta: number | null;
  deltaSuffix?: string;
  icon: LucideIcon;
  tone: string;
  color: string;
  points: SeriesPoint[];
};

function KpiCard({ definition }: { definition: KpiDefinition }) {
  return (
    <article className="social-kpi-card overview-kpi-card">
      <div className="overview-kpi-heading">
        <span className={`overview-kpi-icon tone-${definition.tone}`}><definition.icon size={18} /></span>
        <span className="social-kpi-label">{definition.label}</span>
      </div>
      <strong>{definition.display}</strong>
      <Delta delta={definition.delta} suffix={definition.deltaSuffix} />
      <small>vs previous period</small>
      <MiniSparkline color={definition.color} points={definition.points} />
    </article>
  );
}

function healthSummary(metrics: DashboardMetric[], engagementDeltaPp: number | null) {
  const signals = [
    metric(metrics, "followers")?.delta_pct ?? null,
    metric(metrics, "reach")?.delta_pct ?? null,
    metric(metrics, "interactions")?.delta_pct ?? null,
    engagementDeltaPp,
  ].filter((item): item is number => item !== null);
  if (signals.length < 2) {
    return { label: "Limited Data", tone: "limited", detail: "Not enough comparable signals in this period." };
  }
  const improving = signals.filter((item) => item >= 0).length;
  if (improving >= Math.ceil(signals.length * 0.75)) {
    return { label: "Healthy", tone: "healthy", detail: `${improving} of ${signals.length} core signals are stable or improving.` };
  }
  if (improving >= Math.ceil(signals.length / 2)) {
    return { label: "Stable", tone: "stable", detail: `${improving} of ${signals.length} core signals are stable or improving.` };
  }
  return { label: "Needs Attention", tone: "attention", detail: `${signals.length - improving} of ${signals.length} core signals declined.` };
}

function HealthCard({ metrics, engagementDeltaPp }: { metrics: DashboardMetric[]; engagementDeltaPp: number | null }) {
  const health = healthSummary(metrics, engagementDeltaPp);
  return (
    <article className={`social-kpi-card overview-health-card health-${health.tone}`} title="Health summarizes comparable audience, reach, interaction and engagement trends.">
      <span className="social-kpi-label">Overall Organic Health</span>
      <div className="overview-health-value"><span><Heart size={26} /></span><strong>{health.label}</strong></div>
      <p>{health.detail}</p>
    </article>
  );
}

type ChangeSignal = {
  platform: Platform;
  label: string;
  delta: number;
};

function changedSignals(data: OverviewDashboard): ChangeSignal[] {
  const candidates: Array<{ ids: MetricId[]; label: string }> = [
    { ids: ["reach"], label: "reach" },
    { ids: ["interactions", "video_engagements_total"], label: "interactions" },
    { ids: ["followers", "new_followers"], label: "audience" },
    { ids: ["views", "video_views_total"], label: "views" },
  ];
  return orderedPlatforms(data).flatMap((platformData) => {
    const platform = platformData.meta.platform;
    if (!platform) return [];
    const strongest = candidates
      .flatMap((candidate) => {
        const candidateMetric = candidate.ids.map((id) => metric(platformData.metrics, id)).find((item) => item?.delta_pct !== null);
        return candidateMetric?.delta_pct === null || candidateMetric?.delta_pct === undefined
          ? []
          : [{ platform, label: candidate.label, delta: candidateMetric.delta_pct }];
      })
      .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta))[0];
    return strongest ? [strongest] : [];
  }).slice(0, 3);
}

function WhatChanged({ data }: { data: OverviewDashboard }) {
  const signals = changedSignals(data);
  return (
    <article className="overview-card overview-changed-card">
      <div className="overview-card-title"><h2><Sparkles size={15} />What Changed?</h2></div>
      <div className="overview-change-list">
        {signals.length === 0 && <p className="overview-empty-copy">No comparable platform changes are available.</p>}
        {signals.map((signal) => (
          <div key={`${signal.platform}-${signal.label}`}>
            <span className={`overview-platform-icon platform-${signal.platform}`}><PlatformIcon platform={signal.platform} size={16} /></span>
            <p><strong>{PLATFORM_NAMES[signal.platform]}</strong> {signal.label} {signal.delta >= 0 ? "increased" : "declined"}.</p>
            <Delta delta={signal.delta} />
          </div>
        ))}
      </div>
    </article>
  );
}

function channelStatus(platformData: OverviewDashboard["platforms"][number]) {
  const followerDelta = metric(platformData.metrics, "followers")?.delta_pct ?? null;
  const performanceDelta = firstMetric(platformData.metrics, ["interactions", "video_engagements_total"])?.delta_pct ?? null;
  const signals = [followerDelta, performanceDelta].filter((item): item is number => item !== null);
  if (signals.length === 0) return { label: "Limited", tone: "limited" };
  if (Math.min(...signals) <= -5) return { label: "Attention", tone: "attention" };
  if (Math.max(...signals) >= 2) return { label: "Growing", tone: "healthy" };
  return { label: "Stable", tone: "stable" };
}

function ChannelHealth({ data }: { data: OverviewDashboard }) {
  return (
    <article className="overview-card overview-channel-health">
      <div className="overview-card-title"><h2>Channel Health</h2><span>Current period</span></div>
      <div className="overview-channel-grid">
        {orderedPlatforms(data).map((platformData) => {
          const platform = platformData.meta.platform;
          if (!platform) return null;
          const status = channelStatus(platformData);
          const followers = metric(platformData.metrics, "followers");
          const engagement = platformEngagementRate(platformData);
          const audiencePoints = seriesForPlatform(platformData, ["followers", "new_followers"])?.points ?? [];
          return (
            <Link className="overview-channel-card" key={platform} to={`/${platform}`}>
              <div className="overview-channel-name"><span className={`overview-platform-icon platform-${platform}`}><PlatformIcon platform={platform} size={16} /></span><strong>{PLATFORM_NAMES[platform]}</strong></div>
              <span className={`overview-status status-${status.tone}`}>{status.label}</span>
              <dl><div><dt>Audience</dt><dd>{displayValue(followers?.value ?? null)}</dd></div><div><dt>Engagement</dt><dd>{percentValue(engagement)}</dd></div></dl>
              <Delta delta={followers?.delta_pct ?? null} />
              <MiniSparkline color={PLATFORM_COLORS[platform]} points={audiencePoints} />
            </Link>
          );
        })}
      </div>
    </article>
  );
}

function performanceLines(data: OverviewDashboard, mode: TrendMode): ChartLine[] {
  return orderedPlatforms(data).flatMap((platformData) => {
    const platform = platformData.meta.platform;
    if (!platform) return [];
    let points: SeriesPoint[] = [];
    if (mode === "performance") points = seriesForPlatform(platformData, ["interactions", "video_engagements_total"])?.points ?? [];
    if (mode === "reach") points = seriesForPlatform(platformData, ["reach"])?.points ?? [];
    if (mode === "audience") points = seriesForPlatform(platformData, ["followers", "new_followers"])?.points ?? [];
    if (mode === "engagement") {
      const interactions = seriesForPlatform(platformData, ["interactions", "video_engagements_total"])?.points ?? [];
      const reach = seriesForPlatform(platformData, ["reach"])?.points ?? [];
      points = ratioPoints(interactions, reach);
    }
    return points.length > 0 ? [{ name: PLATFORM_NAMES[platform], color: PLATFORM_COLORS[platform], points }] : [];
  });
}

function PerformanceTrend({ data }: { data: OverviewDashboard }) {
  const [mode, setMode] = useState<TrendMode>("performance");
  const lines = performanceLines(data, mode);
  const allValues = lines.flatMap((line) => line.points.map((point) => point.value));
  const minimum = allValues.length > 0 ? Math.min(...allValues) : 0;
  const maximum = allValues.length > 0 ? Math.max(...allValues) : 1;
  const labels = lines[0]?.points.map((point) => point.observed_on) ?? [];
  return (
    <article className="overview-card overview-performance-card">
      <div className="overview-card-title overview-performance-heading">
        <h2>Performance Trend</h2>
        <div aria-label="Performance metric" className="overview-trend-tabs" role="group">
          {(["performance", "reach", "engagement", "audience"] as TrendMode[]).map((item) => (
            <button className={mode === item ? "active" : ""} key={item} onClick={() => setMode(item)} type="button">{humanize(item)}</button>
          ))}
        </div>
      </div>
      <div className="overview-chart-legend">
        {lines.map((line) => <span key={line.name}><i style={{ background: line.color }} />{line.name}</span>)}
      </div>
      {allValues.length === 0 ? (
        <div className="overview-chart-empty">No {mode} trend is available for this range.</div>
      ) : (
        <>
          <div className="overview-performance-plot">
            <span>{mode === "engagement" ? `${maximum.toFixed(1)}%` : formatNumber(maximum)}</span>
            <svg aria-label={`${humanize(mode)} trend by platform`} preserveAspectRatio="none" role="img" viewBox="0 0 620 180">
              {[18, 54, 90, 126, 162].map((y) => <line key={y} x1="8" x2="612" y1={y} y2={y} />)}
              {lines.map((line) => (
                <polyline
                  fill="none"
                  key={line.name}
                  points={linePoints(line.points.map((point) => point.value), minimum, maximum, 620, 180)}
                  stroke={line.color}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2.5"
                />
              ))}
            </svg>
          </div>
          <div className="overview-chart-axis"><span>{labels[0] ?? ""}</span><span>{labels[Math.floor((labels.length - 1) / 2)] ?? ""}</span><span>{labels.at(-1) ?? ""}</span></div>
        </>
      )}
    </article>
  );
}

function contentSnapshot(content: DashboardContent[]) {
  const totals = new Map<string, number>();
  content.forEach((item) => {
    const label = humanize(item.content_type || "Unknown");
    totals.set(label, (totals.get(label) ?? 0) + item.interactions);
  });
  const ranked = [...totals.entries()].sort((left, right) => right[1] - left[1]);
  const visible = ranked.length <= 4
    ? ranked
    : [...ranked.slice(0, 3), ["Other", ranked.slice(3).reduce((sum, [, interactions]) => sum + interactions, 0)] as [string, number]];
  const total = visible.reduce((sum, [, interactions]) => sum + interactions, 0);
  return visible.map(([label, interactions]) => ({ label, interactions, share: total > 0 ? (interactions / total) * 100 : 0 }));
}

function ContentSnapshot({ content }: { content: DashboardContent[] }) {
  const rows = contentSnapshot(content);
  return (
    <article className="overview-card overview-content-snapshot">
      <div className="overview-card-title"><div><h2>Content Snapshot</h2><p>Performance by content type</p></div></div>
      <div className="overview-snapshot-header"><span>Content type</span><span>Interactions</span><span>Share</span></div>
      <div className="overview-snapshot-rows">
        {rows.length === 0 && <p className="overview-empty-copy">No content was reported in this range.</p>}
        {rows.map((row, index) => (
          <div key={row.label}><span><i className={`snapshot-tone-${index}`} />{row.label}</span><strong>{formatNumber(row.interactions)}</strong><em>{row.share.toFixed(1)}%</em></div>
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

function TopContent({ data }: { data: OverviewDashboard }) {
  const platforms = contentPlatformMap(data);
  const posts = [...data.content].sort((left, right) => right.interactions - left.interactions).slice(0, 3);
  return (
    <article className="overview-card overview-top-content">
      <div className="overview-card-title"><div><h2>Top Performing Content</h2><p>Selected period</p></div></div>
      <div className="overview-top-list">
        {posts.length === 0 && <p className="overview-empty-copy">No ranked content is available.</p>}
        {posts.map((post, index) => {
          const platform = platforms.get(post.account_id);
          const thumbnail = post.cover_url || post.thumbnail_url || post.media_url;
          const engagement = post.reach && post.reach > 0 ? post.interactions / post.reach : null;
          const title = post.message || `${humanize(post.content_type)} content`;
          return (
            <div key={`${post.account_id}-${post.external_content_id}`}>
              <span className="overview-rank">{index + 1}</span>
              <span className="overview-content-thumb">{thumbnail ? <img alt="" src={thumbnail} /> : <Target size={18} />}</span>
              <div className="overview-content-name">
                {post.permalink ? <a href={post.permalink} rel="noreferrer" target="_blank">{title}</a> : <strong>{title}</strong>}
                <span>{platform && <><i className={`platform-${platform}`}><PlatformIcon platform={platform} size={12} /></i>{PLATFORM_NAMES[platform]}</>}</span>
              </div>
              <dl><div><dt>Reach</dt><dd>{displayValue(post.reach)}</dd></div><div><dt>Interactions</dt><dd>{formatNumber(post.interactions)}</dd></div><div><dt>Eng. rate</dt><dd>{percentValue(engagement)}</dd></div></dl>
            </div>
          );
        })}
      </div>
    </article>
  );
}

function splitRecommendations(raw: string | null): string[] {
  if (!raw?.trim()) return [];
  const trimmed = raw.trim();
  const normalize = (item: unknown): string | null => {
    if (typeof item === "string" && item.trim()) return item.trim();
    if (!item || typeof item !== "object") return null;
    const candidate = item as { title?: unknown; description?: unknown };
    const title = typeof candidate.title === "string" ? candidate.title.trim() : "";
    const description = typeof candidate.description === "string" ? candidate.description.trim() : "";
    if (title && description) return `${title}: ${description}`;
    return title || description || null;
  };
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (Array.isArray(parsed)) return parsed.map(normalize).filter((item): item is string => item !== null);
    if (parsed && typeof parsed === "object" && "recommendations" in parsed) {
      const recommendations = (parsed as { recommendations?: unknown }).recommendations;
      if (Array.isArray(recommendations)) return recommendations.map(normalize).filter((item): item is string => item !== null);
    }
  } catch {
    // Legacy records store plain text; continue with conservative parsing.
  }
  const lines = trimmed.split(/\r?\n/).map((item) => item.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, "").trim()).filter(Boolean);
  if (lines.length > 1) return lines;
  return trimmed.split(/(?<=[.!?])\s+/).map((item) => item.trim()).filter(Boolean);
}

function alertTitle(recommendation: string): string {
  const separator = recommendation.match(/^(.{4,58}?)(?::| — | - )\s+(.+)$/);
  if (separator?.[1]) return separator[1].replace(/[.!?]+$/, "");
  const words = recommendation.replace(/[.!?]+$/, "").split(/\s+/);
  return words.length <= 7 ? words.join(" ") : `${words.slice(0, 7).join(" ")}…`;
}

function alertDescription(recommendation: string): string {
  const separator = recommendation.match(/^(.{4,58}?)(?::| — | - )\s+(.+)$/);
  return separator?.[2] || recommendation;
}

function insightRecommendations(insights: ReportingInsight[]) {
  const seen = new Set<string>();
  return insights.flatMap((insight) => splitRecommendations(insight.recommendations).map((text) => ({ insight, text })))
    .filter((item) => {
      const key = item.text.toLocaleLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function InsightDialog({
  brandName,
  error,
  insights,
  loading,
  onClose,
  open,
}: {
  brandName: string;
  error: boolean;
  insights: ReportingInsight[];
  loading: boolean;
  onClose: () => void;
  open: boolean;
}) {
  return (
    <Dialog description={`${brandName} · stored reports only`} onClose={onClose} open={open} title="AI Insights">
      <div className="social-insight-dialog-content">
        {loading ? <div className="social-insight-dialog-state">Loading stored insights…</div> : null}
        {!loading && error ? <div className="social-insight-dialog-state error">Stored insights could not be loaded.</div> : null}
        {!loading && !error && insights.length === 0 ? <div className="social-insight-dialog-state">No generated insight exists for this Brand and date range.</div> : null}
        {!loading && !error && insights.length > 0 ? (
          <div className="overview-insight-dialog-list">
            {insights.map((insight) => (
              <article key={insight.insight_id}>
                <div><span>{humanize(insight.status)}</span><small>{insight.date_from || "—"} – {insight.date_to || "—"}</small></div>
                <h3>Strategic Summary</h3><p>{insight.summary || "No summary was stored for this reporting period."}</p>
                <h3>Recommendations</h3>
                {splitRecommendations(insight.recommendations).length > 0
                  ? <ul>{splitRecommendations(insight.recommendations).map((item) => <li key={item}>{item}</li>)}</ul>
                  : <p>No recommendations were stored for this reporting period.</p>}
              </article>
            ))}
          </div>
        ) : null}
      </div>
    </Dialog>
  );
}

function AlertsAndOpportunities({
  insights,
  loading,
  error,
  onOpen,
}: {
  insights: ReportingInsight[];
  loading: boolean;
  error: boolean;
  onOpen: () => void;
}) {
  const recommendations = insightRecommendations(insights).slice(0, 3);
  const displayedInsight = recommendations[0]?.insight ?? insights[0];
  const icons = [Lightbulb, TrendingUp, Users];
  return (
    <article className="overview-card overview-alerts-card">
      <div className="overview-card-title">
        <div><h2>Alerts &amp; Opportunities</h2><p><Sparkles size={11} />Stored AI insights{displayedInsight?.date_to ? ` · through ${formatDateOnly(displayedInsight.date_to)}` : ""}</p></div>
        {insights.length > 0 && <button onClick={onOpen} type="button">View all <ArrowRight size={13} /></button>}
      </div>
      <div className="overview-alert-list">
        {loading && <p className="overview-empty-copy">Loading stored AI opportunities…</p>}
        {!loading && error && <p className="overview-empty-copy error">Stored AI opportunities are temporarily unavailable.</p>}
        {!loading && !error && recommendations.length === 0 && <p className="overview-empty-copy">No AI opportunities were stored for this Brand and date range.</p>}
        {!loading && !error && recommendations.map((recommendation, index) => {
          const Icon = icons[index] ?? Lightbulb;
          return (
            <button key={`${recommendation.insight.insight_id}-${recommendation.text}`} onClick={onOpen} type="button">
              <span className={`overview-alert-icon alert-tone-${index}`}><Icon size={17} /></span>
              <span><strong>{alertTitle(recommendation.text)}</strong><small>{alertDescription(recommendation.text)}</small></span>
              <ArrowRight size={15} />
            </button>
          );
        })}
      </div>
    </article>
  );
}

function PlatformSummary({ data }: { data: OverviewDashboard }) {
  return (
    <section aria-label="Platform summary" className="social-platform-grid overview-platform-summary">
      {orderedPlatforms(data).map((platformData) => {
        const platform = platformData.meta.platform;
        if (!platform) return null;
        const followers = metric(platformData.metrics, "followers");
        const engagement = platformEngagementRate(platformData);
        const points = seriesForPlatform(platformData, ["followers", "new_followers"])?.points ?? [];
        return (
          <Link className="social-platform-card overview-platform-card" key={platform} to={`/${platform}`}>
            <div className="overview-platform-card-heading"><span className={`overview-platform-icon platform-${platform}`}><PlatformIcon platform={platform} size={18} /></span><strong>{PLATFORM_NAMES[platform]}</strong><ArrowUpRight size={16} /></div>
            <div className="overview-platform-metrics"><span><strong>{displayValue(followers?.value ?? null)}</strong><small>Followers</small></span><span><strong>{percentValue(engagement)}</strong><small>Eng. rate</small></span></div>
            <Delta delta={followers?.delta_pct ?? null} suffix="% audience" />
            <MiniSparkline color={PLATFORM_COLORS[platform]} points={points} />
          </Link>
        );
      })}
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
  const impressionsMetric = firstMetric(data.metrics, ["views", "video_views_total"]);
  const interactionsMetric = firstMetric(data.metrics, ["interactions", "video_engagements_total"]);
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
  const engagementDeltaPp = engagementRate !== null && previousEngagementRate !== null
    ? (engagementRate - previousEngagementRate) * 100
    : null;

  const audiencePoints = useMemo(() => aggregatePoints(data, ["followers", "new_followers"]), [data]);
  const reachPoints = useMemo(() => aggregatePoints(data, ["reach"]), [data]);
  const impressionPoints = useMemo(() => aggregatePoints(data, ["views", "video_views_total"]), [data]);
  const interactionPoints = useMemo(() => aggregatePoints(data, ["interactions", "video_engagements_total"]), [data]);
  const engagementPoints = useMemo(() => ratioPoints(interactionPoints, reachPoints), [interactionPoints, reachPoints]);

  const kpis: KpiDefinition[] = [
    { label: "Total Audience", display: displayValue(audienceMetric?.value ?? null), delta: audienceMetric?.delta_pct ?? null, icon: Users, tone: "violet", color: "#7c3aed", points: audiencePoints },
    { label: "Total Reach", display: displayValue(reachMetric?.value ?? null), delta: reachMetric?.delta_pct ?? null, icon: Eye, tone: "blue", color: "#2563eb", points: reachPoints },
    { label: "Total Impressions", display: displayValue(impressionsMetric?.value ?? null), delta: impressionsMetric?.delta_pct ?? null, icon: Target, tone: "indigo", color: "#4f46e5", points: impressionPoints },
    { label: "Total Interactions", display: displayValue(interactionsMetric?.value ?? null), delta: interactionsMetric?.delta_pct ?? null, icon: MessageCircle, tone: "emerald", color: "#14b8a6", points: interactionPoints },
    { label: "Avg. Engagement", display: percentValue(engagementRate), delta: engagementDeltaPp, deltaSuffix: " pp", icon: Heart, tone: "rose", color: "#ec4899", points: engagementPoints },
  ];

  return (
    <main className="social-overview-page executive-overview">
      <header className="social-overview-header">
        <div><h1>Social Media Overview</h1><p>Organic performance across connected social channels.</p></div>
        <div className="social-overview-controls">
          <label className="social-range-card">
            <span className="social-range-icon"><CalendarDays size={18} /></span>
            <span><small>Date period</small><select aria-label="Date period" onChange={(event) => onRange(event.target.value as RangeKey)} value={range}>{RANGE_OPTIONS.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></span>
          </label>
          <nav aria-label="Connected social channels" className="overview-platform-pills">
            {orderedPlatforms(data).map((platformData) => platformData.meta.platform && (
              <Link key={platformData.meta.platform} to={`/${platformData.meta.platform}`}><PlatformIcon platform={platformData.meta.platform} size={14} />{PLATFORM_NAMES[platformData.meta.platform]}</Link>
            ))}
          </nav>
          <ExportPng metrics={data.metrics} subtitle={`${brandName} · ${data.meta.date_range.start_on} to ${data.meta.date_range.end_on}`} title="Social Media Overview" />
        </div>
      </header>

      {data.meta.data_status !== "available" && <CoverageNotice status={data.meta.data_status} warnings={data.meta.warnings} />}

      <section aria-label="Key performance indicators" className="social-kpi-grid overview-kpi-grid">
        <HealthCard engagementDeltaPp={engagementDeltaPp} metrics={data.metrics} />
        {kpis.map((definition) => <KpiCard definition={definition} key={definition.label} />)}
      </section>

      <section className="overview-analysis-grid">
        <WhatChanged data={data} />
        <ChannelHealth data={data} />
        <PerformanceTrend data={data} />
      </section>

      <section className="overview-content-grid">
        <ContentSnapshot content={data.content} />
        <TopContent data={data} />
        <AlertsAndOpportunities error={insightsError} insights={insights} loading={insightsLoading} onOpen={() => setInsightOpen(true)} />
      </section>

      <PlatformSummary data={data} />
      <InsightDialog brandName={brandName} error={insightsError} insights={insights} loading={insightsLoading} onClose={() => setInsightOpen(false)} open={insightOpen} />
    </main>
  );
}
