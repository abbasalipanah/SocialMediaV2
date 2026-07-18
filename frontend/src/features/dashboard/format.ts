import type { DashboardMetric } from "../../api";

export function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function formatMetric(metric: DashboardMetric): string {
  if (metric.value === null || metric.data_status === "unavailable") return "Unavailable";
  if (metric.unit === "ratio") {
    return new Intl.NumberFormat(undefined, {
      style: "percent",
      maximumFractionDigits: 1,
    }).format(metric.value);
  }
  return formatNumber(metric.value);
}

export function formatDate(value: string | null): string {
  if (!value) return "Never synced";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

export function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
