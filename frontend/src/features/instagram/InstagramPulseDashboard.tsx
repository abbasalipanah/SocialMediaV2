import {
  Activity,
  Eye,
  Heart,
  Info,
  MessageCircle,
  Share2,
  Target,
  Users,
} from "lucide-react";
import { geoNaturalEarth1, geoPath } from "d3-geo";
import { useMemo } from "react";
import { feature } from "#topology";
import type { GeometryCollection, Topology } from "topojson-specification";
import countriesAtlas from "world-atlas/countries-110m.json";

import type {
  DashboardBreakdown,
  DashboardContent,
  DashboardMetric,
  MetricId,
  PlatformDashboard,
} from "../../api";
import { AudienceDemographicsCard } from "../dashboard/AudienceDemographicsCard";
import {
  CommunityTables,
  KpiGrid,
  PerformingContentTable,
  PulseEmpty,
  PulseHeatmapCard,
  PulseCardHeading,
  PulsePieCard,
  PulseTrendCard,
  SectionTitle,
  SimplePulseTable,
  UnavailableInsightCard,
  breakdownRows,
  derivedContentTotals,
  hashtagRows,
  summaryPieRows,
  type PulseKpi,
} from "../facebook/FacebookPulseDashboard";
import { formatDate, formatNumber } from "../dashboard/format";
import { InstagramStoriesWorkspace } from "./InstagramStoriesWorkspace";

type InstagramTab = "cover" | "page" | "content" | "stories" | "audience";
type PieRow = { label: string; value: number; color: string };

function metric(data: PlatformDashboard, id: MetricId): DashboardMetric | undefined {
  return data.metrics.find((item) => item.metric_id === id);
}

function firstMetric(data: PlatformDashboard, ids: MetricId[]): DashboardMetric | undefined {
  return ids.map((id) => metric(data, id)).find((item) => item?.value !== null && item?.value !== undefined);
}

function pulseKpi(
  data: PlatformDashboard,
  ids: MetricId[],
  id: string,
  label: string,
  icon: PulseKpi["icon"],
  color: string,
): PulseKpi {
  const current = firstMetric(data, ids);
  return {
    id,
    label,
    value: current?.value ?? null,
    delta: current?.delta_pct ?? null,
    icon,
    color,
  };
}

function overviewKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    pulseKpi(data, ["followers"], "followers", "Followers", Users, "#38bdf8"),
    pulseKpi(data, ["new_followers"], "new_followers", "New Followers", Users, "#14b8a6"),
    pulseKpi(data, ["reach"], "reach", "Page Reach", Eye, "#8b5cf6"),
    pulseKpi(data, ["views", "profile_views"], "views", "Page Views", Eye, "#ec4899"),
    pulseKpi(data, ["interactions"], "interactions", "Interactions", MessageCircle, "#f59e0b"),
    { id: "frequency", label: "Frequency", value: null, delta: null, icon: Target, color: "#6366f1" },
  ];
}

function contentKpis(data: PlatformDashboard): PulseKpi[] {
  const totals = derivedContentTotals(data.content);
  const collectedTotal = (field: "views" | "reach") => {
    const values = data.content.flatMap((item) => item[field] === null ? [] : [item[field]]);
    return values.length > 0 ? values.reduce((sum, value) => sum + value, 0) : null;
  };
  const views = firstMetric(data, ["views"])?.value ?? collectedTotal("views");
  const reach = firstMetric(data, ["reach"])?.value ?? collectedTotal("reach");
  return [
    { id: "post_views", label: "Views", value: views, delta: null, icon: Eye, color: "#ec4899" },
    { id: "post_reach", label: "Reach", value: reach, delta: null, icon: Target, color: "#38bdf8" },
    { id: "like_reactions", label: "Likes", value: totals.likes, delta: null, icon: Heart, color: "#ef4444" },
    { id: "comments", label: "Comments", value: totals.comments, delta: null, icon: MessageCircle, color: "#3b82f6" },
    { id: "shares", label: "Shares", value: totals.shares, delta: null, icon: Share2, color: "#22c55e" },
    { id: "engagement_rate", label: "Engagement Rate", value: views && views > 0 ? totals.interactions / views : null, delta: null, icon: Activity, color: "#6366f1", unit: "ratio" },
  ];
}

function audienceKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    pulseKpi(data, ["followers"], "followers", "Followers", Users, "#38bdf8"),
    pulseKpi(data, ["new_followers"], "new_followers", "New Followers", Users, "#14b8a6"),
    pulseKpi(data, ["views", "page_views"], "views", "Views", Eye, "#06b6d4"),
    pulseKpi(data, ["reach"], "reach", "Reach", Target, "#8b5cf6"),
    pulseKpi(data, ["profile_views"], "profile_views", "Profile Views", Eye, "#ec4899"),
  ];
}

function engagementRows(content: DashboardContent[]): PieRow[] {
  const totals = derivedContentTotals(content);
  return [
    { label: "Like", value: totals.likes, color: "#3b82f6" },
    { label: "Comments", value: totals.comments, color: "#6366f1" },
    { label: "Shares", value: totals.shares, color: "#22c55e" },
  ].filter((item) => item.value > 0);
}

function reachRows(data: PlatformDashboard): PieRow[] {
  const source = data.source_breakdown?.reach;
  if (!source) return [];
  return [
    source.organic === null ? null : { label: "Organic Reach", value: source.organic, color: "#22c55e" },
    !data.source_breakdown?.paid_available || source.paid === null ? null : { label: "Paid Reach", value: source.paid, color: "#ef4444" },
  ].filter((item): item is PieRow => item !== null);
}

function pageViewRows(data: PlatformDashboard): PieRow[] {
  const source = data.source_breakdown?.views;
  if (!source) return [];
  return [
    source.organic === null ? null : { label: "Organic", value: source.organic, color: "#ec4899" },
    !data.source_breakdown?.paid_available || source.paid === null ? null : { label: "Paid", value: source.paid, color: "#8b5cf6" },
  ].filter((item): item is PieRow => item !== null);
}

function findBreakdown(breakdowns: DashboardBreakdown[], hints: string[]): DashboardBreakdown | undefined {
  return breakdowns.find((item) => {
    const value = `${item.dimension} ${item.metric_id}`.toLowerCase();
    return hints.some((hint) => value.includes(hint));
  });
}

const COUNTRY_ALIASES: Record<string, string> = {
  turkiye: "turkey",
  türkiye: "turkey",
  usa: "united states of america",
  "united states": "united states of america",
  uk: "united kingdom",
};

function normalizedCountry(value: string): string {
  const normalized = value.trim().toLocaleLowerCase("en-US");
  return COUNTRY_ALIASES[normalized] ?? normalized;
}

const worldTopology = countriesAtlas as unknown as Topology<{
  countries: GeometryCollection<{ name?: string }>;
}>;
const worldCountries = feature(worldTopology, worldTopology.objects.countries);

export function WorldMapWidget({ breakdown }: { breakdown?: DashboardBreakdown }) {
  const rows = useMemo(
    () => [...(breakdown?.items ?? [])].sort((left, right) => right.value - left.value).slice(0, 5),
    [breakdown],
  );
  const lookup = useMemo(
    () => new Map(rows.map((row) => [normalizedCountry(row.key), row])),
    [rows],
  );
  const paths = useMemo(() => {
    const projection = geoNaturalEarth1().fitExtent([[8, 8], [752, 332]], worldCountries);
    const generator = geoPath(projection);
    return worldCountries.features.map((country) => ({
      d: generator(country) ?? "",
      name: String(country.properties?.name ?? ""),
    }));
  }, []);
  const maximum = Math.max(1, ...rows.map((row) => row.value));

  return (
    <article className="facebook-pulse-card instagram-world-widget">
      <div className="instagram-widget-title"><h3>Audience by Country</h3><Info aria-label="Geographic audience distribution information" size={14} /></div>
      {rows.length === 0 ? <PulseEmpty copy="No data available" /> : (
        <div className="instagram-world-layout">
          <div className="instagram-world-map">
            <svg aria-label="Audience by Country world map" role="img" viewBox="0 0 760 340">
              {paths.map((country) => {
                const row = lookup.get(normalizedCountry(country.name));
                const ratio = row ? row.value / maximum : 0;
                const fill = row ? (ratio > 0.65 ? "#6366f1" : ratio > 0.25 ? "#a5b4fc" : "#c7d2fe") : "#f1f5f9";
                return <path d={country.d} fill={fill} key={country.name} stroke="#d9e2ec" strokeWidth="0.65"><title>{row ? `${row.key}: ${formatNumber(row.value)}` : country.name}</title></path>;
              })}
            </svg>
          </div>
          <div className="instagram-top-regions">
            <span>Top Regions</span>
            <div>
              {rows.map((row) => (
                <div key={row.key}>
                  <p><b>{row.key}</b><em>{formatNumber(row.value)}</em></p>
                  <i><b style={{ width: `${Math.max(4, (row.value / maximum) * 100)}%` }} /></i>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

function PageSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Overview</SectionTitle>}
      <KpiGrid rows={overviewKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: "#38bdf8" }]} localZoom subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard data={data} keys={[{ id: "new_followers", label: "Follows", color: "#3b82f6" }]} subtitle="Follows, unfollows and net movement" title="New Followers Trend" />
      </div>
      <PulseTrendCard bar data={data} keys={[{ id: "reach", label: "Page Reach", color: "#8b5cf6" }, { id: "views", label: "Page Views", color: "#5eead4" }]} subtitle="Page Reach and Page Views trend" title="Performance Trends" wide />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={pageViewRows(data)} subtitle="Organic vs paid views" title="Page View Type" />
        <PulseTrendCard data={data} keys={[{ id: "views_organic", label: "Organic Views", color: "#3b82f6" }, { id: "views_paid", label: "Paid Views", color: "#f59e0b" }]} subtitle="Organic Views + Paid Views" title="Views Source Trend" />
      </div>
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={reachRows(data)} subtitle="Organic vs paid Reach" title="Reach Distribution" />
        <PulseTrendCard data={data} keys={[{ id: "reach_paid", label: "Paid Reach", color: "#ef4444" }, { id: "reach_organic", label: "Organic Reach", color: "#22c55e" }]} subtitle="Paid Reach + Organic Reach" title="Reach Source Trend" />
      </div>
    </section>
  );
}

function ContentSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  const contentData = useMemo(
    () => ({
      ...data,
      content: data.content.filter((item) => !item.content_type.toLowerCase().includes("story")),
    }),
    [data],
  );
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Content</SectionTitle>}
      <KpiGrid rows={contentKpis(contentData)} />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={summaryPieRows(data.content_summary.by_type)} subtitle="Content type breakdown" title="Content Type" />
        <PulseTrendCard data={data} keys={[{ id: "views", label: "Page Views", color: "#ec4899" }, { id: "reach", label: "Page Reach", color: "#8b5cf6" }]} subtitle="Daily page views and reach" title="Views & Reach Trend" />
      </div>
      <div className="facebook-two-three-grid">
        <PulseTrendCard data={data} keys={[{ id: "interactions", label: "Interactions", color: "#f59e0b" }]} subtitle="Likes, comments and shares over time" title="Interaction Trend" />
        <PulsePieCard legendColumns={3} rows={engagementRows(contentData.content)} subtitle="Interaction mix" title="Engagement Split" />
      </div>
      <div className="facebook-three-grid">
        <PulsePieCard rows={summaryPieRows(data.content_summary.reach_by_type, ["#ec4899", "#38bdf8", "#14b8a6", "#8b5cf6"])} subtitle="Reach by content type" title="Content Type Reach" />
        <UnavailableInsightCard copy="Sentiment is not inferred without a configured analysis model." subtitle="Not provided by TikTok Organic API" title="Comment Sentiment" />
        <SimplePulseTable columns={["Hashtag", "Count"]} emptyCopy="No hashtags in collected captions." rows={hashtagRows(data)} subtitle="Hashtags found in collected captions" title="Top Hashtags" />
      </div>
      <PerformingContentTable content={contentData.content} />
    </section>
  );
}

function AudienceSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  const countries = findBreakdown(data.breakdowns, ["country"]);
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Audience</SectionTitle>}
      <KpiGrid rows={audienceKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: "#38bdf8" }]} localZoom subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard data={data} keys={[{ id: "new_followers", label: "Follows", color: "#3b82f6" }]} subtitle="Follows, unfollows and net movement" title="New Followers Trend" />
      </div>
      <div className="facebook-two-grid">
        <AudienceDemographicsCard breakdowns={data.breakdowns} />
        <WorldMapWidget breakdown={countries} />
      </div>
      <div className="facebook-two-grid">
        <PulseHeatmapCard breakdowns={data.breakdowns} />
        <PulseTrendCard data={data} keys={[{ id: "reach_organic", label: "Organic Reach", color: "#22c55e" }]} subtitle="Organic delivery trend" title="Organic Reach Trend" />
      </div>
      <div className="facebook-two-grid">
        <SimplePulseTable columns={["#", "Country", "Value"]} rows={breakdownRows(data.breakdowns, "country")} subtitle="Country ranking" title="Top Countries" />
        <SimplePulseTable columns={["#", "City", "Value"]} rows={breakdownRows(data.breakdowns, "city")} subtitle="City ranking" title="Top Cities" />
      </div>
      <div className="facebook-two-grid">
        <PulsePieCard rows={reachRows(data)} subtitle="Reach delivery split" title="Reach Source (Organic vs Paid)" />
        <PulseTrendCard data={data} keys={[{ id: "reach_paid", label: "Paid Reach", color: "#ef4444" }]} subtitle="Paid delivery trend" title="Paid Reach Trend" />
      </div>
      <CommunityTables data={data} platform="instagram" />
    </section>
  );
}

export function InstagramPulseDashboard({ data, tab }: { data: PlatformDashboard; tab: InstagramTab }) {
  const cover = tab === "cover";
  return (
    <div className="facebook-pulse-dashboard instagram-pulse-dashboard">
      {(tab === "page" || cover) && <PageSection data={data} withTitle={cover} />}
      {(tab === "content" || cover) && <ContentSection data={data} withTitle={cover} />}
      {tab === "stories" && <InstagramStoriesWorkspace data={data} />}
      {(tab === "audience" || cover) && <AudienceSection data={data} withTitle={cover} />}
    </div>
  );
}
