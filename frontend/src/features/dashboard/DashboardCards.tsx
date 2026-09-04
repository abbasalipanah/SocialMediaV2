import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  MessageCircle,
  RefreshCcw,
  TriangleAlert,
} from "lucide-react";

import type {
  DashboardBreakdown,
  DashboardContent,
  DashboardMetric,
  OverviewDashboard,
  PlatformDashboard,
  Platform,
} from "../../api";
import { METRIC_LABELS, PLATFORM_LABELS, PRIMARY_METRICS, TREND_METRICS } from "./catalog";
import { formatDate, formatMetric, formatNumber, humanize } from "./format";
import { TrendChart } from "./TrendChart";

type DashboardData = OverviewDashboard | PlatformDashboard;

function selectedMetrics(data: DashboardData, scope: Platform | "overview"): DashboardMetric[] {
  const byId = new Map(data.metrics.map((metric) => [metric.metric_id, metric]));
  const preferred = PRIMARY_METRICS[scope].flatMap((id) => {
    const metric = byId.get(id);
    return metric ? [metric] : [];
  });
  return preferred.length > 0 ? preferred : data.metrics.slice(0, 6);
}

export function MetricBand({ data, scope }: { data: DashboardData; scope: Platform | "overview" }) {
  const metrics = selectedMetrics(data, scope);
  if (metrics.length === 0) {
    return <HonestEmpty title="Metrics are not available" copy="No metric observations were returned for this scope and date range." />;
  }
  return (
    <section aria-label="Key performance indicators" className="metric-grid">
      {metrics.map((metric) => (
        <article className={`metric-card status-${metric.data_status}`} key={metric.metric_id}>
          <div className="metric-label">
            <span>{METRIC_LABELS[metric.metric_id]}</span>
            <Activity aria-hidden="true" size={16} />
          </div>
          <strong>{formatMetric(metric)}</strong>
          <div className="metric-comparison">
            {metric.delta_pct === null ? (
              <span>Comparison unavailable</span>
            ) : (
              <span className={metric.delta_pct >= 0 ? "positive" : "negative"}>
                {metric.delta_pct >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                {Math.abs(metric.delta_pct).toFixed(1)}%
              </span>
            )}
            {metric.data_status === "partial" && <em>Partial</em>}
          </div>
        </article>
      ))}
    </section>
  );
}

export function TrendSection({ data }: { data: DashboardData }) {
  const availableSeries = "series" in data
    ? data.series
    : data.platforms.flatMap((platform) => platform.series);
  const trends = availableSeries
    .filter((series) => TREND_METRICS.includes(series.metric_id))
    .slice(0, 4);
  if (trends.length === 0) {
    return <HonestEmpty title="Trends are not available" copy="There are no daily observations for this scope and range." />;
  }
  return (
    <section aria-labelledby="trends-title" className="dashboard-section">
      <SectionHeading eyebrow="Performance" title="Growth and engagement trends" id="trends-title" />
      <div className="trend-grid">
        {trends.map((series, index) => <TrendChart key={`${series.metric_id}-${index}`} series={series} />)}
      </div>
    </section>
  );
}

export function HealthSection({ data }: { data: DashboardData }) {
  const rows = "platforms" in data ? data.platforms : [data];
  return (
    <section aria-labelledby="health-title" className="dashboard-section">
      <SectionHeading eyebrow="Operations" title="Platform health" id="health-title" />
      <div className="health-grid">
        {rows.map((row) => {
          const platform = row.meta.platform;
          if (!platform) return null;
          const healthy = row.meta.data_status === "available" && row.meta.freshness === "fresh";
          return (
            <article className="dashboard-card health-card" key={platform}>
              <div className={`health-icon ${healthy ? "healthy" : "attention"}`}>
                {healthy ? <CheckCircle2 size={20} /> : <TriangleAlert size={20} />}
              </div>
              <div>
                <h3>{PLATFORM_LABELS[platform]}</h3>
                <p>{humanize(row.meta.data_status)} data · {humanize(row.meta.freshness)}</p>
                <small><Clock3 size={13} /> {formatDate(row.meta.last_sync_at)}</small>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function AudienceSection({ breakdowns }: { breakdowns: DashboardBreakdown[] }) {
  if (breakdowns.length === 0) {
    return <HonestEmpty title="Audience data is unavailable" copy="The provider did not return an audience breakdown for this scope." />;
  }
  return (
    <section aria-labelledby="audience-title" className="dashboard-section">
      <SectionHeading eyebrow="Audience" title="Audience breakdown" id="audience-title" />
      <div className="breakdown-grid">
        {breakdowns.map((breakdown) => (
          <article className="dashboard-card breakdown-card" key={`${breakdown.metric_id}-${breakdown.dimension}`}>
            <h3>{humanize(breakdown.dimension)}</h3>
            <div className="breakdown-list">
              {breakdown.items.slice(0, 7).map((item) => {
                const ratio = item.percentage === null ? null : Math.max(0, Math.min(100, item.percentage));
                return (
                  <div className="breakdown-row" key={item.key}>
                    <div><span>{humanize(item.key)}</span><strong>{ratio === null ? formatNumber(item.value) : `${ratio.toFixed(1)}%`}</strong></div>
                    {ratio !== null && <span className="breakdown-track"><i style={{ width: `${ratio}%` }} /></span>}
                  </div>
                );
              })}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function ContentSection({ content, storyOnly = false }: { content: DashboardContent[]; storyOnly?: boolean }) {
  const rows = storyOnly ? content.filter((item) => item.content_type.toLowerCase() === "story") : content;
  if (rows.length === 0) {
    return <HonestEmpty title={storyOnly ? "No stories in this range" : "No content in this range"} copy="Nothing was returned for the selected account and date range." />;
  }
  return (
    <section aria-labelledby="content-title" className="dashboard-section">
      <SectionHeading eyebrow="Content intelligence" title={storyOnly ? "Stories" : "Recent and top content"} id="content-title" />
      <div className="content-grid">
        {rows.slice(0, 8).map((item) => (
          <article className="dashboard-card content-card" key={`${item.account_id}-${item.external_content_id}`}>
            <div className="content-media">
              {item.media_url ? <img alt="" loading="lazy" src={item.media_url} /> : <span>{humanize(item.content_type)}</span>}
            </div>
            <div className="content-copy">
              <div className="content-meta"><span>{humanize(item.content_type)}</span><time>{item.published_at ? formatDate(item.published_at) : "Date unavailable"}</time></div>
              <p>{item.message || "Caption unavailable"}</p>
              <dl>
                <div><dt>Likes</dt><dd>{item.likes_count === null ? "Unavailable" : formatNumber(item.likes_count)}</dd></div>
                <div><dt>Comments</dt><dd>{item.comments_count === null ? "Unavailable" : formatNumber(item.comments_count)}</dd></div>
                <div><dt>Shares</dt><dd>{item.shares_count === null ? "Unavailable" : formatNumber(item.shares_count)}</dd></div>
                <div><dt>Interactions</dt><dd>{item.interactions === null ? "Unavailable" : formatNumber(item.interactions)}</dd></div>
              </dl>
              {item.permalink && <a href={item.permalink} rel="noreferrer" target="_blank">View original</a>}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function CommunitySection({ data }: { data: DashboardData }) {
  const summary = data.community;
  if (summary.data_status === "unavailable") {
    return <HonestEmpty title="Community summary is unavailable" copy="Comment coverage was not returned for this scope." />;
  }
  const rows = [
    ["Total comments", summary.total_comments],
    ["Answered", summary.answered_comments],
    ["Awaiting response", summary.unanswered_comments],
    ["Comment likes", summary.comment_likes],
  ] as const;
  return (
    <section aria-labelledby="community-title" className="dashboard-section">
      <SectionHeading eyebrow="Community" title="Comment activity" id="community-title" />
      <div className="community-card dashboard-card">
        <div className="community-symbol"><MessageCircle size={24} /></div>
        {rows.map(([label, value]) => <div className="community-stat" key={label}><span>{label}</span><strong>{formatNumber(value)}</strong></div>)}
      </div>
    </section>
  );
}

export function HonestEmpty({ title, copy }: { title: string; copy: string }) {
  return (
    <section className="honest-empty" role="status">
      <RefreshCcw aria-hidden="true" size={22} />
      <div><h3>{title}</h3><p>{copy}</p></div>
    </section>
  );
}

export function SectionHeading({ eyebrow, title, id }: { eyebrow: string; title: string; id: string }) {
  return <div className="section-heading"><div><p>{eyebrow}</p><h2 id={id}>{title}</h2></div></div>;
}
