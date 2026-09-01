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
import { countryDisplayName, countryLookupKey } from "../dashboard/countryPresentation";
import {
  V1_CHART_COLORS,
  V1_FOLLOWER_FLOW_KEYS,
  followerFlowSubtitle,
} from "../dashboard/visualPalette";
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
  breakdownRows,
  countryBreakdownRows,
  comparisonDelta,
  derivedContentTotals,
  hashtagRows,
  sentimentPieRows,
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
    unit: current?.unit === "ratio" ? "ratio" : undefined,
  };
}

function overviewKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    pulseKpi(data, ["followers"], "followers", "Followers", Users, "#38bdf8"),
    pulseKpi(data, ["new_followers"], "new_followers", "New Followers", Users, "#14b8a6"),
    pulseKpi(data, ["reach"], "reach", "Page Reach", Eye, "#8b5cf6"),
    pulseKpi(data, ["views", "profile_views"], "views", "Page Views", Eye, "#ec4899"),
    pulseKpi(data, ["interactions"], "interactions", "Interactions", MessageCircle, "#f59e0b"),
    pulseKpi(data, ["engagement_rate"], "engagement_rate", "Engagement Rate", Activity, "#6366f1"),
  ];
}

function contentKpis(data: PlatformDashboard): PulseKpi[] {
  const totals = derivedContentTotals(data.content);
  const collectedTotal = (field: "views" | "reach") => {
    const values = data.content.flatMap((item) => item[field] === null ? [] : [item[field]]);
    return values.length > 0 ? values.reduce((sum, value) => sum + value, 0) : null;
  };
  const viewsMetric = firstMetric(data, ["views"]);
  const reachMetric = firstMetric(data, ["reach"]);
  const viewsFromMetric = viewsMetric?.value !== null && viewsMetric?.value !== undefined;
  const reachFromMetric = reachMetric?.value !== null && reachMetric?.value !== undefined;
  const views = viewsMetric?.value ?? data.content_metrics.views.value ?? collectedTotal("views");
  const reach = reachMetric?.value ?? data.content_metrics.reach.value ?? collectedTotal("reach");
  const interactions = data.content_metrics.interactions.value ?? totals.interactions;
  const engagementRate = views && views > 0 ? interactions / views : null;
  const previousViews = viewsFromMetric
    ? viewsMetric.previous_value
    : data.content_metrics.views.previous_value;
  const previousInteractions = data.content_metrics.interactions.previous_value;
  const previousEngagementRate = previousViews && previousViews > 0 && previousInteractions !== null
    ? previousInteractions / previousViews
    : null;
  return [
    { id: "post_views", label: "Views", value: views, delta: viewsFromMetric ? viewsMetric.delta_pct : data.content_metrics.views.delta_pct, icon: Eye, color: "#ec4899" },
    { id: "post_reach", label: "Reach", value: reach, delta: reachFromMetric ? reachMetric.delta_pct : data.content_metrics.reach.delta_pct, icon: Target, color: "#38bdf8" },
    { id: "like_reactions", label: "Likes", value: data.content_metrics.likes.value ?? totals.likes, delta: data.content_metrics.likes.delta_pct, icon: Heart, color: V1_CHART_COLORS.likes },
    { id: "comments", label: "Comments", value: data.content_metrics.comments.value ?? totals.comments, delta: data.content_metrics.comments.delta_pct, icon: MessageCircle, color: "#3b82f6" },
    { id: "shares", label: "Shares", value: data.content_metrics.shares.value ?? totals.shares, delta: data.content_metrics.shares.delta_pct, icon: Share2, color: "#22c55e" },
    { id: "engagement_rate", label: "Engagement Rate", value: engagementRate, delta: comparisonDelta(engagementRate, previousEngagementRate), icon: Activity, color: "#6366f1", unit: "ratio" },
  ];
}

function audienceKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    pulseKpi(data, ["followers"], "followers", "Followers", Users, "#38bdf8"),
    pulseKpi(data, ["new_followers"], "new_followers", "New Followers", Users, "#14b8a6"),
    pulseKpi(data, ["views", "page_views"], "views", "Views", Eye, "#06b6d4"),
    pulseKpi(data, ["reach"], "reach", "Reach", Target, "#8b5cf6"),
    pulseKpi(data, ["profile_views"], "profile_views", "Profile Views", Eye, "#ec4899"),
    pulseKpi(data, ["engagement_rate"], "engagement_rate", "Engagement Rate", Activity, "#6366f1"),
  ];
}

function engagementRows(content: DashboardContent[]): PieRow[] {
  const totals = derivedContentTotals(content);
  return [
    { label: "Likes", value: totals.likes, color: V1_CHART_COLORS.likes },
    { label: "Comments", value: totals.comments, color: V1_CHART_COLORS.comments },
    { label: "Shares", value: totals.shares, color: V1_CHART_COLORS.shares },
  ].filter((item) => item.value > 0);
}

const BREAKDOWN_COLORS = ["#8b5cf6", "#14b8a6", "#f59e0b", "#ec4899", "#38bdf8", "#6366f1"];

function insightBreakdownRows(
  data: PlatformDashboard,
  metricId: "views" | "reach",
  dimension: "follow_type" | "media_product_type",
): PieRow[] {
  const breakdown = data.breakdowns.find((item) =>
    item.metric_id === metricId && item.dimension.toLowerCase() === dimension);
  const providerRows = (breakdown?.items ?? []).map((item, index) => ({
    label: item.key
      .toLowerCase()
      .split("_")
      .map((part) => part ? `${part[0]?.toUpperCase()}${part.slice(1)}` : part)
      .join(" ")
      .replace("Non Follower", "Non-follower"),
    value: item.value,
    color: BREAKDOWN_COLORS[index % BREAKDOWN_COLORS.length] ?? "#64748b",
  }));
  if (providerRows.some((item) => item.value > 0) || dimension !== "media_product_type") {
    return providerRows;
  }

  // V1 stored per-content reach/views and the immutable V2 import preserves
  // those values in content_summary. Current Meta collection writes the newer
  // media_product_type breakdown. Falling back only when that provider
  // breakdown is absent/zero lets migrated Brands render their real historical
  // content mix immediately, while native data wins as soon as the timer writes it.
  const legacyRows = metricId === "views"
    ? data.content_summary.views_by_type
    : data.content_summary.reach_by_type;
  return legacyRows
    .filter((item) => item.value > 0)
    .map((item, index) => ({
      label: item.name,
      value: item.value,
      color: BREAKDOWN_COLORS[index % BREAKDOWN_COLORS.length] ?? "#64748b",
    }));
}

function findBreakdown(breakdowns: DashboardBreakdown[], hints: string[]): DashboardBreakdown | undefined {
  for (const hint of hints) {
    const found = breakdowns.find((item) =>
      `${item.dimension} ${item.metric_id}`.toLowerCase().includes(hint));
    if (found) return found;
  }
  return undefined;
}

function normalizedCountry(value: string): string {
  return countryLookupKey(value);
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
                return <path d={country.d} fill={fill} key={country.name} stroke="#d9e2ec" strokeWidth="0.65"><title>{row ? `${countryDisplayName(row.key)}: ${formatNumber(row.value)}` : country.name}</title></path>;
              })}
            </svg>
          </div>
          <div className="instagram-top-regions">
            <span>Top Regions</span>
            <div>
              {rows.map((row) => (
                <div key={row.key}>
                  <p><b>{countryDisplayName(row.key)}</b><em>{formatNumber(row.value)}</em></p>
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
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: V1_CHART_COLORS.followers }]} localZoom subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard connectGaps data={data} keys={[...V1_FOLLOWER_FLOW_KEYS]} subtitle={followerFlowSubtitle(data)} title="New Followers Trend" />
      </div>
      <PulseTrendCard bar data={data} keys={[{ id: "reach", label: "Page Reach", color: V1_CHART_COLORS.reach }, { id: "views", label: "Page Views", color: V1_CHART_COLORS.views }]} subtitle="Page Reach and Page Views trend" title="Performance Trends" wide />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={insightBreakdownRows(data, "views", "follow_type")} subtitle="Follower vs non-follower views" title="Views Audience Split" />
        <PulsePieCard rows={insightBreakdownRows(data, "views", "media_product_type")} subtitle="Views by Instagram surface" title="Views by Content Type" />
      </div>
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={insightBreakdownRows(data, "reach", "follow_type")} subtitle="Follower vs non-follower reach" title="Reach Audience Split" />
        <PulsePieCard rows={insightBreakdownRows(data, "reach", "media_product_type")} subtitle="Reach by Instagram surface" title="Reach by Content Type" />
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
        <PulseTrendCard data={data} keys={[{ id: "views", label: "Page Views", color: V1_CHART_COLORS.views }, { id: "reach", label: "Page Reach", color: V1_CHART_COLORS.reach }]} subtitle="Daily page views and reach" title="Views & Reach Trend" />
      </div>
      <div className="facebook-two-three-grid">
        <PulseTrendCard data={data} keys={[{ id: "interactions", label: "Interactions", color: "#f59e0b" }]} subtitle="Likes, comments and shares over time" title="Interaction Trend" />
        <PulsePieCard legendColumns={3} rows={engagementRows(contentData.content)} subtitle="Interaction mix" title="Engagement Split" />
      </div>
      <div className="facebook-three-grid">
        <PulsePieCard rows={summaryPieRows(data.content_summary.reach_by_type, ["#ec4899", "#38bdf8", "#14b8a6", "#8b5cf6"])} subtitle="Reach by content type" title="Content Type Reach" />
        <PulsePieCard rows={sentimentPieRows(data.breakdowns)} subtitle="Classified comment distribution" title="Comment Sentiment" />
        <SimplePulseTable columns={["Hashtag", "Count"]} emptyCopy="No hashtags in collected captions." rows={hashtagRows(data)} subtitle="Hashtags found in collected captions" title="Top Hashtags" />
      </div>
      <PerformingContentTable content={contentData.content} />
    </section>
  );
}

function AudienceSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  const countries = findBreakdown(data.breakdowns, [
    "follower_demographics_country",
    "audience_country",
    "country",
  ]);
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Audience</SectionTitle>}
      <KpiGrid rows={audienceKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: V1_CHART_COLORS.followers }]} localZoom subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard connectGaps data={data} keys={[...V1_FOLLOWER_FLOW_KEYS]} subtitle={followerFlowSubtitle(data)} title="New Followers Trend" />
      </div>
      <div className="facebook-two-grid">
        <AudienceDemographicsCard breakdowns={data.breakdowns} />
        <WorldMapWidget breakdown={countries} />
      </div>
      <div className="facebook-two-grid">
        <PulseHeatmapCard breakdowns={data.breakdowns} />
        <PulseTrendCard data={data} keys={[{ id: "reach", label: "Reach", color: "#8b5cf6" }]} subtitle="Daily unique accounts reached" title="Reach Trend" />
      </div>
      <div className="facebook-two-grid">
        <SimplePulseTable columns={["#", "Country", "Value"]} rows={countryBreakdownRows(data.breakdowns)} subtitle="Country ranking" title="Top Countries" />
        <SimplePulseTable columns={["#", "City", "Value"]} rows={breakdownRows(data.breakdowns, "city")} subtitle="City ranking" title="Top Cities" />
      </div>
      <div className="facebook-two-grid">
        <PulsePieCard rows={insightBreakdownRows(data, "reach", "follow_type")} subtitle="Follower vs non-follower reach" title="Reach Audience Split" />
        <PulsePieCard rows={insightBreakdownRows(data, "reach", "media_product_type")} subtitle="Reach by Instagram surface" title="Reach by Content Type" />
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
      {cover && <section className="facebook-pulse-section"><SectionTitle>Stories</SectionTitle><InstagramStoriesWorkspace data={data} /></section>}
      {(tab === "audience" || cover) && <AudienceSection data={data} withTitle={cover} />}
    </div>
  );
}
