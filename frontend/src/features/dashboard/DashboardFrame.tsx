import { AlertTriangle, CalendarDays, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import type { DashboardMetric, DataStatus } from "../../api";
import { PRESET_RANGE_OPTIONS, type PresetRangeKey } from "./catalog";
import { ExportPng } from "./ExportPng";
import { formatDate, humanize } from "./format";

export function DashboardHeader({
  title,
  description,
  range,
  onRange,
  status,
  freshness,
  lastSync,
  metrics,
  exportSubtitle,
}: {
  title: string;
  description: string;
  range: PresetRangeKey;
  onRange: (range: PresetRangeKey) => void;
  status: DataStatus;
  freshness: string;
  lastSync: string | null;
  metrics: DashboardMetric[];
  exportSubtitle: string;
}) {
  return (
    <header className="dashboard-header">
      <div>
        <p className="eyebrow">Social Media</p>
        <h1>{title}</h1>
        <p>{description}</p>
        <div className="freshness-line">
          <span className={`data-status status-${status}`}>{humanize(status)}</span>
          <span>{humanize(freshness)}</span>
          <span>Last sync: {formatDate(lastSync)}</span>
        </div>
      </div>
      <div className="dashboard-actions">
        <label className="range-control">
          <CalendarDays size={16} />
          <span className="sr-only">Date range</span>
          <select onChange={(event) => onRange(event.target.value as PresetRangeKey)} value={range}>
            {PRESET_RANGE_OPTIONS.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
          </select>
        </label>
        <ExportPng metrics={metrics} subtitle={exportSubtitle} title={title} />
      </div>
    </header>
  );
}

export function DashboardLoading({ title }: { title: string }) {
  return (
    <main aria-busy="true" aria-label={`Loading ${title}`} className="page-shell">
      <header className="loading-dashboard-heading">
        <p className="eyebrow">Social Media</p>
        <h1>{title}</h1>
        <div className="dashboard-skeleton skeleton-heading" />
      </header>
      <div className="metric-grid">
        {Array.from({ length: 6 }, (_, index) => <div className="dashboard-skeleton skeleton-metric" key={index} />)}
      </div>
      <div className="trend-grid">
        {Array.from({ length: 2 }, (_, index) => <div className="dashboard-skeleton skeleton-chart" key={index} />)}
      </div>
    </main>
  );
}

export function DashboardError({ retry }: { retry: () => void }) {
  return (
    <main className="page-shell">
      <section className="dashboard-error" role="alert">
        <AlertTriangle size={26} />
        <div><h1>Dashboard could not be loaded</h1><p>No values were inferred. Retry the scoped reporting query.</p></div>
        <button className="secondary-button" onClick={retry} type="button"><RefreshCw size={16} /> Retry</button>
      </section>
    </main>
  );
}

export function DashboardTabs({
  tabs,
  active,
  onSelect,
  children,
}: {
  tabs: Array<{ id: string; label: string }>;
  active: string;
  onSelect: (id: string) => void;
  children: ReactNode;
}) {
  return (
    <>
      <div aria-label="Dashboard sections" className="dashboard-tabs" role="tablist">
        {tabs.map((tab) => (
          <button
            aria-selected={active === tab.id}
            className={active === tab.id ? "active" : ""}
            key={tab.id}
            onClick={() => onSelect(tab.id)}
            role="tab"
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div aria-live="polite" role="tabpanel">{children}</div>
    </>
  );
}
