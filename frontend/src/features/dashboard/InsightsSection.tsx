import { Lightbulb, Sparkles } from "lucide-react";

import type { ReportingInsight } from "../../api";
import { HonestEmpty, SectionHeading } from "./DashboardCards";
import { formatDate, humanize } from "./format";

export function InsightsSection({
  insights,
  loading,
  error,
}: {
  insights: ReportingInsight[];
  loading: boolean;
  error: boolean;
}) {
  if (loading) return <div aria-label="Loading insights" className="dashboard-skeleton skeleton-chart" />;
  if (error) return <HonestEmpty title="AI Insights could not be loaded" copy="Dashboard reporting remains available. Insights were not inferred locally." />;
  if (insights.length === 0) return <HonestEmpty title="AI Insights are not available" copy="No generated insight exists for this Brand and date range." />;
  return (
    <section aria-labelledby="insights-title" className="dashboard-section">
      <SectionHeading eyebrow="AI Insights" title="Reporting intelligence" id="insights-title" />
      <div className="insight-grid">
        {insights.slice(0, 3).map((insight) => (
          <article className="dashboard-card insight-card" key={insight.insight_id}>
            <div className="insight-icon"><Sparkles size={20} /></div>
            <div>
              <div className="content-meta"><span>{humanize(insight.status)}</span><time>{formatDate(insight.completed_at ?? insight.created_at)}</time></div>
              <h3>{insight.summary || "Insight summary unavailable"}</h3>
              {insight.recommendations && <p><Lightbulb size={16} /> {insight.recommendations}</p>}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
