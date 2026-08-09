import { Info } from "lucide-react";
import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DashboardBreakdown } from "../../api";
import { formatNumber, humanize } from "./format";

type GenderKey = "men" | "other" | "women";
type DemographicRow = Record<GenderKey, number> & { age: string; audience: number };

const AGE_ORDER = ["13-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"];
const GENDER_SERIES = [
  { key: "women", label: "Women", color: "#60a5fa" },
  { key: "men", label: "Men", color: "#22c55e" },
  { key: "other", label: "Other", color: "#f59e0b" },
] as const;

function ageLabel(rawKey: string): string {
  return rawKey.match(/(?:13-17|18-24|25-34|35-44|45-54|55-64|65\+|65 plus)/i)?.[0]
    .replace(/65 plus/i, "65+") ?? humanize(rawKey);
}

function genderKey(rawKey: string): GenderKey {
  const value = rawKey.trim();
  if (/\bfemale\b|\bwoman\b|\bwomen\b|^f(?:[.\s_|-]|$)/i.test(value)) return "women";
  if (/\bmale\b|\bman\b|\bmen\b|^m(?:[.\s_|-]|$)/i.test(value)) return "men";
  return "other";
}

function rankAge(left: DemographicRow, right: DemographicRow): number {
  const leftRank = AGE_ORDER.indexOf(left.age);
  const rightRank = AGE_ORDER.indexOf(right.age);
  return (leftRank < 0 ? 999 : leftRank) - (rightRank < 0 ? 999 : rightRank);
}

export function AudienceDemographicsCard({ breakdowns }: { breakdowns: DashboardBreakdown[] }) {
  const processed = useMemo(() => {
    const combined = breakdowns.find((item) => {
      const dimension = item.dimension.toLowerCase();
      return dimension.includes("age") && dimension.includes("gender");
    });
    const ageOnly = breakdowns.find((item) => {
      const dimension = item.dimension.toLowerCase();
      return dimension.includes("age") && !dimension.includes("gender");
    });
    const genderOnly = breakdowns.find((item) => {
      const dimension = item.dimension.toLowerCase();
      return dimension.includes("gender") && !dimension.includes("age");
    });
    const rowsByAge = new Map<string, DemographicRow>();
    const totals: Record<GenderKey, number> = { women: 0, men: 0, other: 0 };

    for (const item of combined?.items ?? []) {
      const age = ageLabel(item.key);
      const gender = genderKey(item.key);
      const row = rowsByAge.get(age) ?? { age, audience: 0, women: 0, men: 0, other: 0 };
      row[gender] += item.value;
      row.audience += item.value;
      totals[gender] += item.value;
      rowsByAge.set(age, row);
    }

    if (!combined) {
      for (const item of ageOnly?.items ?? []) {
        const age = ageLabel(item.key);
        rowsByAge.set(age, { age, audience: item.value, women: 0, men: 0, other: 0 });
      }
      for (const item of genderOnly?.items ?? []) totals[genderKey(item.key)] += item.value;
    }

    const rows = [...rowsByAge.values()].sort(rankAge);
    const ageTotal = rows.reduce((sum, row) => sum + row.audience, 0);
    const genderTotal = totals.women + totals.men + totals.other;
    return {
      combined: Boolean(combined),
      rows,
      totals,
      total: ageTotal || genderTotal,
      percentageBase: genderTotal || ageTotal,
      radar: rows.map((row) => ({ age: row.age, value: row.audience })),
    };
  }, [breakdowns]);
  const percentage = (value: number) => processed.percentageBase > 0
    ? (value / processed.percentageBase) * 100
    : 0;
  const summarySeries = processed.percentageBase > 0 && Object.values(processed.totals).some((value) => value > 0)
    ? GENDER_SERIES
    : [{ key: "other", label: "Audience", color: "#60a5fa" }] as const;
  const barSeries = processed.combined
    ? GENDER_SERIES
    : [{ key: "audience", label: "Audience", color: "#60a5fa" }] as const;

  return (
    <article className="facebook-pulse-card instagram-demographics-widget">
      <div className="instagram-widget-title"><h3>Age &amp; Gender</h3><Info aria-label="Audience distribution information" size={14} /></div>
      {processed.rows.length === 0 ? <div className="facebook-pulse-empty">No data available</div> : (
        <div className="instagram-demographics-layout">
          <div className="instagram-demographics-main">
            <div className="instagram-demographics-summary">
              <div><strong>{formatNumber(processed.total)}</strong><span>Followers</span></div>
              <div className="instagram-demographics-percentages">
                {summarySeries.map((item) => (
                  <span key={item.key}><i style={{ background: item.color }} /><b>{percentage(processed.totals[item.key]).toFixed(0)}%</b>{item.label}</span>
                ))}
              </div>
            </div>
            <div className="instagram-demographics-chart">
              <ResponsiveContainer height="100%" width="100%">
                <BarChart data={processed.rows} margin={{ bottom: 0, left: -12, right: 8, top: 10 }}>
                  <CartesianGrid opacity={0.5} stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
                  <XAxis axisLine={false} dataKey="age" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} />
                  <YAxis axisLine={false} tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} />
                  <Tooltip cursor={{ fill: "transparent" }} />
                  <Legend iconType="circle" verticalAlign="top" wrapperStyle={{ fontSize: "11px" }} />
                  {barSeries.map((item) => <Bar barSize={18} dataKey={item.key} fill={item.color} key={item.key} name={item.label} radius={[6, 6, 0, 0]} />)}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="instagram-age-focus">
            <span>Age Focus</span>
            <div className="instagram-age-radar">
              <ResponsiveContainer height="100%" width="100%">
                <RadarChart data={processed.radar} outerRadius="72%">
                  <PolarGrid stroke="#dbe4ee" />
                  <PolarAngleAxis dataKey="age" tick={{ fill: "#64748b", fontSize: 10 }} />
                  <PolarRadiusAxis axisLine={false} tick={false} />
                  <Radar dataKey="value" fill="#60a5fa" fillOpacity={0.35} stroke="#60a5fa" />
                </RadarChart>
              </ResponsiveContainer>
            </div>
            <div className="instagram-age-legend">
              {summarySeries.map((item) => (
                <div key={item.key}><span><i style={{ background: item.color }} />{item.label}</span><b>{percentage(processed.totals[item.key]).toFixed(1)}%</b></div>
              ))}
            </div>
          </div>
        </div>
      )}
    </article>
  );
}
