import {
  Activity,
  Eye,
  GalleryVerticalEnd,
  Heart,
  MessageCircle,
  Reply,
  Share2,
  Target,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import type { DashboardBreakdown, DashboardContent, DashboardMetric, MetricId, PlatformDashboard } from "../../api";
import {
  CommentQueue,
  ContentWinners,
  KpiGrid,
  PerformingContentTable,
  PulseEmpty,
  PulsePieCard,
  PulseTrendCard,
  SectionTitle,
  SimplePulseTable,
  breakdownRows,
  derivedContentTotals,
  type PulseKpi,
} from "../facebook/FacebookPulseDashboard";
import { formatDate, formatNumber, humanize } from "../dashboard/format";

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
  return [
    { id: "total_content", label: "Total Content", value: data.content.length, delta: null, icon: Activity, color: "#8b5cf6" },
    { id: "post_views", label: "Post Views", value: null, delta: null, icon: Eye, color: "#ec4899" },
    { id: "post_reach", label: "Post Reach", value: null, delta: null, icon: Target, color: "#38bdf8" },
    { id: "like_reactions", label: "Like & Reactions", value: totals.likes, delta: null, icon: Heart, color: "#ef4444" },
    { id: "comments", label: "Comments", value: totals.comments, delta: null, icon: MessageCircle, color: "#3b82f6" },
    { id: "shares", label: "Shares", value: totals.shares, delta: null, icon: Share2, color: "#22c55e" },
  ];
}

function audienceKpis(data: PlatformDashboard): PulseKpi[] {
  return [
    pulseKpi(data, ["followers"], "followers", "Followers", Users, "#38bdf8"),
    pulseKpi(data, ["new_followers"], "new_followers", "New Followers", Users, "#14b8a6"),
    pulseKpi(data, ["page_views", "views"], "page_views", "Page Views", Eye, "#06b6d4"),
    pulseKpi(data, ["reach_paid"], "reach_paid", "Paid Reach", Target, "#ef4444"),
    pulseKpi(data, ["reach_organic"], "reach_organic", "Organic Reach", Activity, "#22c55e"),
    { id: "frequency", label: "Frequency", value: null, delta: null, icon: Target, color: "#8b5cf6" },
  ];
}

function storyRows(data: PlatformDashboard): DashboardContent[] {
  return data.content.filter((item) => item.content_type.toLowerCase().includes("story"));
}

function storyKpis(data: PlatformDashboard): PulseKpi[] {
  const stories = storyRows(data);
  return [
    { id: "stories_count", label: "Stories Count", value: stories.length, delta: null, icon: GalleryVerticalEnd, color: "#8b5cf6" },
    { id: "story_views", label: "Story Views", value: null, delta: null, icon: Eye, color: "#ec4899" },
    { id: "story_reach", label: "Story Reach", value: null, delta: null, icon: Target, color: "#38bdf8" },
    { id: "story_interactions", label: "Story Interactions", value: null, delta: null, icon: Heart, color: "#ef4444" },
    { id: "story_replies", label: "Story Replies", value: null, delta: null, icon: Reply, color: "#3b82f6" },
    { id: "story_completion_rate", label: "Story Completion Rate", value: null, delta: null, icon: Activity, color: "#22c55e" },
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
  const organic = metric(data, "reach_organic")?.value ?? null;
  const paid = metric(data, "reach_paid")?.value ?? null;
  return [
    { label: "Organic Reach", value: organic ?? 0, color: "#22c55e" },
    { label: "Paid Reach", value: paid ?? 0, color: "#ef4444" },
  ].filter((item) => item.value > 0);
}

function findBreakdown(breakdowns: DashboardBreakdown[], hints: string[]): DashboardBreakdown | undefined {
  return breakdowns.find((item) => {
    const value = `${item.dimension} ${item.metric_id}`.toLowerCase();
    return hints.some((hint) => value.includes(hint));
  });
}

function BreakdownBarsCard({
  breakdown,
  copy,
  subtitle,
  title,
}: {
  breakdown?: DashboardBreakdown;
  copy: string;
  subtitle: string;
  title: string;
}) {
  const rows = breakdown?.items.slice(0, 10) ?? [];
  const maximum = Math.max(1, ...rows.map((item) => item.value));
  return (
    <article className="facebook-pulse-card instagram-breakdown-card">
      <div className="facebook-pulse-card-heading"><h3>{title}</h3><p>{subtitle}</p></div>
      {rows.length === 0 ? <PulseEmpty copy={copy} /> : (
        <div className="instagram-breakdown-bars">
          {rows.map((row) => (
            <div key={row.key}>
              <span>{humanize(row.key)}</span>
              <i><b style={{ width: `${Math.max(3, (row.value / maximum) * 100)}%` }} /></i>
              <strong>{formatNumber(row.value)}</strong>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

function EmptyTrendCard({ subtitle, title }: { subtitle: string; title: string }) {
  return (
    <article className="facebook-pulse-card facebook-trend-card">
      <div className="facebook-pulse-card-heading"><h3>{title}</h3><p>{subtitle}</p></div>
      <PulseEmpty copy="The reporting contract does not expose this Instagram metric." />
    </article>
  );
}

function PageSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Overview</SectionTitle>}
      <KpiGrid rows={overviewKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: "#38bdf8" }]} subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard data={data} keys={[{ id: "new_followers", label: "Follows", color: "#3b82f6" }]} subtitle="Follows, unfollows and net movement" title="New Followers Trend" />
      </div>
      <PulseTrendCard bar data={data} keys={[{ id: "reach", label: "Page Reach", color: "#8b5cf6" }, { id: "views", label: "Page Views", color: "#5eead4" }]} subtitle="Page Reach and Page Views trend" title="Performance Trends" wide />
      <div className="facebook-one-three-grid">
        <PulsePieCard rows={[]} subtitle="Organic vs paid views" title="Page View Type" />
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
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Content</SectionTitle>}
      <KpiGrid rows={contentKpis(data)} />
      <div className="facebook-two-three-grid">
        <PulseTrendCard data={data} keys={[{ id: "interactions", label: "Interactions", color: "#f59e0b" }]} subtitle="Daily interaction trend" title="Interactions Trend" />
        <PulsePieCard rows={engagementRows(data.content)} title="Engagement Split" />
      </div>
      <div className="facebook-three-grid">
        <PulsePieCard rows={[]} title="Content Type Reach" />
        <PulsePieCard rows={[]} title="Comment Sentiment" />
        <SimplePulseTable columns={["Hashtag", "Count"]} rows={[]} title="Top Hashtags" />
      </div>
      <PerformingContentTable content={data.content} />
      <ContentWinners content={data.content} />
      <div className="facebook-two-grid">
        <CommentQueue available={data.community.data_status !== "unavailable"} count={data.community.unanswered_comments} title="Unanswered Comments Queue" />
        <CommentQueue available={data.community.data_status !== "unavailable"} count={data.community.answered_comments} title="Answered Comments Log" />
      </div>
    </section>
  );
}

function StoryPreview({ children, title }: { children: ReactNode; title: string }) {
  return (
    <article className="facebook-pulse-card instagram-story-preview">
      <div className="facebook-pulse-card-heading"><h3>{title}</h3></div>
      {children}
    </article>
  );
}

function StoryBody({ story }: { story: DashboardContent }) {
  return (
    <div className="instagram-story-body">
      <div className="instagram-story-media">{story.media_url ? <img alt="Story cover" src={story.media_url} /> : <GalleryVerticalEnd size={32} />}</div>
      <div><strong>{story.message || "Story"}</strong><span>{story.published_at ? formatDate(story.published_at) : "Date unavailable"}</span><small>Story-level views, reach and navigation are unavailable.</small></div>
    </div>
  );
}

function StoriesSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  const stories = useMemo(() => storyRows(data), [data]);
  const [selected, setSelected] = useState(0);
  useEffect(() => setSelected(0), [stories.length]);
  useEffect(() => {
    if (stories.length <= 1) return undefined;
    const timer = window.setInterval(() => setSelected((current) => (current + 1) % stories.length), 6000);
    return () => window.clearInterval(timer);
  }, [stories.length]);
  const active = stories[selected] ?? null;
  const latest = stories[0] ?? null;
  const shares = stories.reduce((sum, item) => sum + item.shares_count, 0);
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Stories</SectionTitle>}
      <KpiGrid rows={storyKpis(data)} />
      <div className="facebook-two-three-grid">
        <EmptyTrendCard subtitle="Story Views and Story Reach momentum" title="Story Performance Trends" />
        <StoryPreview title="Last Story">{latest ? <StoryBody story={latest} /> : <PulseEmpty copy="No story cover data" />}</StoryPreview>
      </div>
      <div className="facebook-three-grid">
        <PulsePieCard rows={[]} title="Story Navigation Split" />
        <PulsePieCard rows={shares > 0 ? [{ label: "Shares", value: shares, color: "#f59e0b" }] : []} title="Story Actions" />
        <StoryPreview title="Story Sliders">
          {active ? (
            <><StoryBody story={active} /><div className="instagram-story-controls"><button disabled={selected === 0} onClick={() => setSelected((current) => Math.max(0, current - 1))} type="button">Previous</button><span>{selected + 1} / {stories.length}</span><button disabled={selected === stories.length - 1} onClick={() => setSelected((current) => Math.min(stories.length - 1, current + 1))} type="button">Next</button></div></>
          ) : <PulseEmpty copy="No story covers" />}
        </StoryPreview>
      </div>
      <SimplePulseTable
        columns={["#", "Cover", "Story", "Date", "Story Views", "Story Reach", "Interactions", "Replies"]}
        rows={stories.map((story, index) => [index + 1, story.media_url ? "Media" : "—", story.message || "Story", story.published_at ? formatDate(story.published_at) : "—", "—", "—", "—", "—"])}
        title="Stories"
      />
    </section>
  );
}

function AudienceSection({ data, withTitle }: { data: PlatformDashboard; withTitle: boolean }) {
  const demographics = findBreakdown(data.breakdowns, ["gender", "age"]);
  const countries = findBreakdown(data.breakdowns, ["country"]);
  return (
    <section className="facebook-pulse-section">
      {withTitle && <SectionTitle>Audience</SectionTitle>}
      <KpiGrid rows={audienceKpis(data)} />
      <div className="facebook-two-grid">
        <PulseTrendCard data={data} keys={[{ id: "followers", label: "Followers", color: "#38bdf8" }]} subtitle="Follower trajectory" title="Followers Trend" />
        <PulseTrendCard data={data} keys={[{ id: "new_followers", label: "Follows", color: "#3b82f6" }]} subtitle="Follows, unfollows and net movement" title="New Followers Trend" />
      </div>
      <div className="facebook-two-grid">
        <BreakdownBarsCard breakdown={demographics} copy="No age and gender data in the selected range." subtitle="Audience distribution" title="Age & Gender" />
        <BreakdownBarsCard breakdown={countries} copy="No country map data in the selected range." subtitle="Geographic audience distribution" title="Audience by Country" />
      </div>
      <div className="facebook-two-grid">
        <BreakdownBarsCard copy="The reporting contract does not return hourly audience activity." subtitle="Hourly activity density" title="Best Time to Engage" />
        <PulseTrendCard data={data} keys={[{ id: "reach_organic", label: "Organic Reach", color: "#22c55e" }]} subtitle="Organic delivery trend" title="Organic Reach Trend" />
      </div>
      <div className="facebook-two-grid">
        <SimplePulseTable columns={["#", "Country", "Value"]} rows={breakdownRows(data.breakdowns, "country")} subtitle="Country ranking" title="Top Countries" />
        <SimplePulseTable columns={["#", "City", "Value"]} rows={breakdownRows(data.breakdowns, "city")} subtitle="City ranking" title="Top Cities" />
      </div>
      <div className="facebook-two-grid">
        <PulsePieCard rows={reachRows(data)} subtitle="Organic vs paid Reach" title="Reach Distribution" />
        <PulseTrendCard data={data} keys={[{ id: "reach_paid", label: "Paid Reach", color: "#ef4444" }]} subtitle="Paid delivery trend" title="Paid Reach Trend" />
      </div>
    </section>
  );
}

export function InstagramPulseDashboard({ data, tab }: { data: PlatformDashboard; tab: InstagramTab }) {
  const cover = tab === "cover";
  return (
    <div className="facebook-pulse-dashboard instagram-pulse-dashboard">
      {(tab === "page" || cover) && <PageSection data={data} withTitle={cover} />}
      {(tab === "content" || cover) && <ContentSection data={data} withTitle={cover} />}
      {(tab === "stories" || cover) && <StoriesSection data={data} withTitle={cover} />}
      {(tab === "audience" || cover) && <AudienceSection data={data} withTitle={cover} />}
    </div>
  );
}
