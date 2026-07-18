import type { DashboardSeries } from "../../api";
import { METRIC_LABELS } from "./catalog";
import { formatNumber } from "./format";

function chartPoints(values: number[], width: number, height: number): string {
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const spread = maximum - minimum || 1;
  return values
    .map((value, index) => {
      const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
      const y = height - ((value - minimum) / spread) * (height - 12) - 6;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export function TrendChart({ series }: { series: DashboardSeries }) {
  const values = series.points.map((point) => point.value);
  const latest = values.at(-1);
  return (
    <article className="dashboard-card trend-card">
      <div className="card-heading">
        <div>
          <p className="card-kicker">Trend</p>
          <h3>{METRIC_LABELS[series.metric_id]}</h3>
        </div>
        <strong>{latest === undefined ? "Unavailable" : formatNumber(latest)}</strong>
      </div>
      {values.length > 0 ? (
        <svg
          aria-label={`${METRIC_LABELS[series.metric_id]} trend with ${values.length} observations`}
          className="trend-chart"
          preserveAspectRatio="none"
          role="img"
          viewBox="0 0 420 130"
        >
          <defs>
            <linearGradient id={`fill-${series.metric_id}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#766ce3" stopOpacity=".26" />
              <stop offset="100%" stopColor="#766ce3" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d={`M ${chartPoints(values, 420, 130).replaceAll(" ", " L ")} L 420 130 L 0 130 Z`}
            fill={`url(#fill-${series.metric_id})`}
          />
          <polyline
            fill="none"
            points={chartPoints(values, 420, 130)}
            stroke="#6257d9"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="3"
          />
        </svg>
      ) : (
        <p className="card-empty">No observations in this range.</p>
      )}
      {series.points.length > 1 && (
        <div className="chart-axis">
          <span>{series.points[0]?.observed_on}</span>
          <span>{series.points.at(-1)?.observed_on}</span>
        </div>
      )}
    </article>
  );
}
