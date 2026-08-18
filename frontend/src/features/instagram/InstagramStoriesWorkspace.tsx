import {
  Activity,
  Bookmark,
  CheckCircle2,
  Clock3,
  Copy,
  Database,
  ExternalLink,
  Eye,
  Forward,
  GalleryVerticalEnd,
  Heart,
  MessageCircle,
  MousePointerClick,
  Reply,
  Share2,
  Sparkles,
  Target,
  TrendingDown,
  UserPlus,
  UserRound,
} from "lucide-react";
import { useEffect, useMemo, useState, type ComponentType } from "react";

import type { DashboardStories, DashboardStoryItem, PlatformDashboard } from "../../api";
import { PulseEmpty, PulsePieVisualization, PulseTrendCard } from "../facebook/FacebookPulseDashboard";
import { formatNumber } from "../dashboard/format";

function storyValue(value: number | null): string {
  return value === null ? "—" : formatNumber(value);
}

function percentage(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(1)}%`;
}

function rate(numerator: number | null, denominator: number | null): number | null {
  if (numerator === null || denominator === null || denominator <= 0) return null;
  return (numerator / denominator) * 100;
}

function formatDateTime(value: string | null): string {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function durationLabel(milliseconds: number): string {
  if (milliseconds <= 0) return "Expired";
  const minutes = Math.floor(milliseconds / 60_000);
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

function storyStatus(story: DashboardStoryItem | null, generatedAt: string) {
  if (!story?.created_time) return { live: false, expires: "Not available" };
  const publishedAt = new Date(story.created_time).getTime();
  const observedAt = new Date(generatedAt).getTime();
  if (!Number.isFinite(publishedAt) || !Number.isFinite(observedAt)) {
    return { live: false, expires: "Not available" };
  }
  const remaining = publishedAt + 24 * 60 * 60 * 1_000 - observedAt;
  return { live: remaining > 0, expires: durationLabel(remaining) };
}

function StoryMetric({
  icon: Icon,
  label,
  value,
  percentageValue = false,
  tone,
}: {
  icon: ComponentType<{ size?: number }>;
  label: string;
  value: number | null;
  percentageValue?: boolean;
  tone: "violet" | "blue" | "rose" | "amber";
}) {
  return (
    <article className={`instagram-story-metric tone-${tone}`}>
      <div><span><Icon size={18} /></span><small>{label}</small></div>
      <strong>{percentageValue ? percentage(value) : storyValue(value)}</strong>
    </article>
  );
}

type StoryActionValues = Pick<
  DashboardStoryItem,
  "follows" | "profile_visits" | "replies" | "saves" | "shares" | "sticker_taps"
>;

function StoryActionGrid({ values }: { values: StoryActionValues }) {
  const actions = [
    { label: "Replies", value: values.replies, icon: Reply, tone: "violet" },
    { label: "Shares", value: values.shares, icon: Share2, tone: "emerald" },
    { label: "Profile Visits", value: values.profile_visits, icon: UserRound, tone: "blue" },
    { label: "Follows", value: values.follows, icon: UserPlus, tone: "green" },
    { label: "Sticker Taps", value: values.sticker_taps, icon: MousePointerClick, tone: "rose" },
    { label: "Saves", value: values.saves, icon: Bookmark, tone: "slate" },
  ] as const;
  return (
    <div className="instagram-story-action-grid">
      {actions.map(({ icon: Icon, label, tone, value }) => (
        <div key={label}><span className={`tone-${tone}`}><Icon size={17} /></span><small>{label}</small><strong>{storyValue(value)}</strong>{value === null && <em>Not provided</em>}</div>
      ))}
    </div>
  );
}

function StoryArtwork({ story, compact = false }: { story: DashboardStoryItem; compact?: boolean }) {
  return (
    <div className={`instagram-story-artwork${compact ? " compact" : ""}`}>
      {story.cover_url ? <img alt="" src={story.cover_url} /> : (
        <div className="instagram-story-artwork-placeholder">
          <Sparkles size={compact ? 16 : 26} />
          {!compact && <strong>{story.title || "Instagram Story"}</strong>}
        </div>
      )}
      {!compact && (
        <div className="instagram-story-artwork-caption">
          <span>{story.title || "Instagram Story"}</span>
          {story.permalink && <small><ExternalLink size={11} /> View on Instagram</small>}
        </div>
      )}
    </div>
  );
}

function LatestStoryPanel({
  stories,
  selected,
  onSelect,
}: {
  stories: DashboardStoryItem[];
  selected: number;
  onSelect: (index: number) => void;
}) {
  const active = stories[selected] ?? null;
  return (
    <article className="instagram-story-surface instagram-story-feature">
      <header className="instagram-story-card-header">
        <div><h3>Latest Story</h3><small>Story {stories.length === 0 ? 0 : selected + 1} of {stories.length}</small></div>
        {active?.data_status === "available" && <b><i /> Collected</b>}
      </header>
      {!active ? <PulseEmpty copy="No stories were collected in this period." /> : (
        <div className="instagram-story-feature-layout">
          <div className="instagram-story-selected-artwork"><StoryArtwork story={active} /></div>
          <div className="instagram-story-feature-details">
            <div className="instagram-story-metric-grid">
              <StoryMetric icon={Eye} label="Story Views" tone="violet" value={active.views} />
              <StoryMetric icon={Target} label="Reach" tone="blue" value={active.reach} />
              <StoryMetric icon={Activity} label="Completion Rate" percentageValue tone="rose" value={active.completion_rate} />
              <StoryMetric icon={Heart} label="Interactions" tone="amber" value={active.interactions} />
            </div>
            <div className="instagram-story-selected-actions">
              <h4>Selected story actions</h4>
              <StoryActionGrid values={active} />
            </div>
          </div>
          <div className="instagram-story-gallery">
            <h4>Story gallery</h4>
            <div>
              {stories.map((story, index) => (
                <button
                  aria-label={`Story ${index + 1}: ${story.title || "Untitled"}`}
                  aria-pressed={selected === index}
                  className={selected === index ? "selected" : ""}
                  key={story.content_id}
                  onClick={() => onSelect(index)}
                  type="button"
                >
                  <StoryArtwork compact story={story} />
                  <small>{index + 1}</small>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

function StoryLiveStatus({
  data,
  story,
  generatedAt,
  lastSyncAt,
}: {
  data: DashboardStories;
  story: DashboardStoryItem | null;
  generatedAt: string;
  lastSyncAt: string | null;
}) {
  const status = storyStatus(story, generatedAt);
  const copyId = () => {
    if (story?.content_id && navigator.clipboard) void navigator.clipboard.writeText(story.content_id);
  };
  return (
    <article className="instagram-story-surface instagram-story-live-card">
      <header className="instagram-story-section-heading">
        <h3>Story Live Status</h3>
        <span className={status.live ? "live" : "expired"}><i />{status.live ? "LIVE" : "HISTORY"}</span>
      </header>
      <dl className="instagram-story-status-list">
        <div><dt><CheckCircle2 size={16} />Published</dt><dd>{formatDateTime(story?.created_time ?? null)}</dd></div>
        <div><dt><Clock3 size={16} />{status.live ? "Expires in" : "Availability"}</dt><dd>{status.expires}</dd></div>
        <div><dt><Database size={16} />Last sync</dt><dd>{formatDateTime(lastSyncAt)}</dd></div>
        <div><dt><GalleryVerticalEnd size={16} />Snapshots collected</dt><dd>{data.trend.labels.length}</dd></div>
        <div><dt><MousePointerClick size={16} />Story ID</dt><dd><span>{story?.content_id ?? "Not available"}</span>{story?.content_id && <button aria-label="Copy Story ID" onClick={copyId} type="button"><Copy size={14} /></button>}</dd></div>
      </dl>
      {story?.permalink ? <a className="instagram-story-data-link" href={story.permalink} rel="noreferrer" target="_blank"><ExternalLink size={15} />View story</a> : <span className="instagram-story-data-link disabled"><ExternalLink size={15} />Story link unavailable</span>}
    </article>
  );
}

function StoryHealth({ story, summary }: { story: DashboardStoryItem | null; summary: DashboardStories["summary"] }) {
  const completionRate = story?.completion_rate ?? summary.completion_rate;
  const navigationTotal = story?.navigation ?? null;
  const exitRate = rate(story?.exits ?? null, navigationTotal);
  const forwardRate = rate(story?.taps_forward ?? null, navigationTotal);
  const interactionRate = rate(story?.interactions ?? null, story?.views ?? null);
  const values = [
    { label: "Exit Rate", value: exitRate, icon: TrendingDown, tone: "slate" },
    { label: "Forward Rate", value: forwardRate, icon: Forward, tone: "blue" },
    { label: "Interaction Rate", value: interactionRate, icon: Sparkles, tone: "amber" },
  ] as const;
  // Completion is the one figure here that is a share of a whole: the viewers
  // who reached the end against those who dropped out. The other three are
  // independent ratios, so they stay as figures rather than joining the chart.
  const completionRows = completionRate === null ? [] : [
    { color: "#7c3aed", label: "Completed", value: Math.max(0, completionRate) },
    { color: "#e2e8f0", label: "Dropped off", value: Math.max(0, 100 - completionRate) },
  ];
  // Counts rather than the percentages already shown above: the rates say how
  // the story performed, these say how much of it there was to measure.
  const volumes = [
    { icon: Eye, label: "Views", value: story?.views ?? null },
    { icon: Target, label: "Reach", value: story?.reach ?? null },
    { icon: MessageCircle, label: "Replies", value: story?.replies ?? null },
  ] as const;
  return (
    <article className="instagram-story-surface instagram-story-health">
      <header className="instagram-story-section-heading"><h3>Story Health</h3><small>Selected story</small></header>
      <div className="instagram-story-health-layout">
        <div className="instagram-story-health-chart">
          <PulsePieVisualization
            emptyCopy="Provider did not return a completion rate."
            rows={completionRows}
            title="Story Completion"
          />
        </div>
        <div className="instagram-story-health-grid">
          {values.map(({ icon: Icon, label, tone, value }) => (
            <div key={label}><span className={`tone-${tone}`}><Icon size={16} /></span><p><small>{label}</small><strong>{percentage(value)}</strong></p></div>
          ))}
        </div>
      </div>
      <div className="instagram-story-health-notes">
        {volumes.map(({ icon: Icon, label, value }) => (
          <span key={label}>
            <Icon size={15} />
            <b>{storyValue(value)}</b>
            <small>{label}</small>
          </span>
        ))}
      </div>
    </article>
  );
}

function Behaviour({ data }: { data: DashboardStories }) {
  const navigation = [
    { label: "Tap Forward", value: data.navigation.taps_forward, color: "#7c3aed" },
    { label: "Swipe Forward", value: data.navigation.swipe_forward, color: "#2dd4bf" },
    { label: "Tap Back", value: data.navigation.taps_back, color: "#f59e0b" },
    { label: "Exits", value: data.navigation.exits, color: "#ec4899" },
  ];
  const navigationRows = navigation.flatMap((item) => item.value === null ? [] : [{
    color: item.color,
    label: item.label,
    value: item.value,
  }]);
  return (
    <article className="instagram-story-surface instagram-story-behaviour">
      <header className="instagram-story-section-heading"><div><h3>Behaviour</h3><small>Totals across the selected date range</small></div></header>
      <h4>Navigation Split</h4>
      <div className="instagram-story-navigation-pie">
        <PulsePieVisualization
          emptyCopy="No navigation data for this period."
          rows={navigationRows}
          title="Story Navigation Split"
        />
      </div>
      <h4>Period Action Totals</h4>
      <StoryActionGrid values={data.actions} />
    </article>
  );
}

function storyPerformance(story: DashboardStoryItem, averageViews: number | null) {
  if (story.views === null || averageViews === null || averageViews === 0) return { label: "Unavailable", tone: "neutral" };
  const ratio = story.views / averageViews;
  if (ratio >= 1.15) return { label: "Above avg", tone: "positive" };
  if (ratio <= 0.85) return { label: "Below avg", tone: "negative" };
  return { label: "Average", tone: "neutral" };
}

function History({ stories }: { stories: DashboardStoryItem[] }) {
  const viewValues = stories.flatMap((story) => story.views === null ? [] : [story.views]);
  const averageViews = viewValues.length ? viewValues.reduce((sum, value) => sum + value, 0) / viewValues.length : null;
  return (
    <article className="instagram-story-surface instagram-story-history" id="instagram-story-history">
      <header className="instagram-story-section-heading"><div><h3>History</h3><small>All stories in this period</small></div><span>{stories.length} stories</span></header>
      <div className="instagram-story-history-scroll">
        <table><thead><tr><th>#</th><th>Cover</th><th>Published</th><th>Views</th><th>Reach</th><th>Completion</th><th>Actions</th><th>Exit Rate</th><th>Performance</th></tr></thead><tbody>
          {stories.length === 0 ? <tr><td colSpan={9}>No story history in this period.</td></tr> : stories.map((story, index) => {
            const navigationTotal = story.navigation;
            const performance = storyPerformance(story, averageViews);
            return (
              <tr key={story.content_id}>
                <td>{index + 1}</td>
                <td><StoryArtwork compact story={story} /></td>
                <td><strong>{formatDateTime(story.created_time)}</strong><small>{story.title || "Instagram Story"}</small></td>
                <td>{storyValue(story.views)}</td><td>{storyValue(story.reach)}</td><td>{percentage(story.completion_rate)}</td><td>{storyValue(story.interactions)}</td><td>{percentage(rate(story.exits, navigationTotal))}</td>
                <td><span className={`instagram-story-performance ${performance.tone}`}>{performance.label}</span></td>
              </tr>
            );
          })}
        </tbody></table>
      </div>
    </article>
  );
}

export function InstagramStoriesWorkspace({ data }: { data: PlatformDashboard }) {
  const storiesData = data.stories;
  const stories = storiesData?.items ?? [];
  const [selected, setSelected] = useState(0);
  useEffect(() => setSelected(0), [stories.length]);
  const active = stories[selected] ?? null;
  const trendData = useMemo<PlatformDashboard | null>(() => storiesData ? ({
    ...data,
    series: [
      {
        metric_id: "views",
        semantic_type: "flow",
        methodology: "provider_reported",
        points: storiesData.trend.labels.flatMap((observed_on, index) => {
          const value = storiesData.trend.views[index];
          return value === null || value === undefined ? [] : [{ observed_on, value }];
        }),
      },
      {
        metric_id: "reach",
        semantic_type: "flow",
        methodology: "provider_reported",
        points: storiesData.trend.labels.flatMap((observed_on, index) => {
          const value = storiesData.trend.reach[index];
          return value === null || value === undefined ? [] : [{ observed_on, value }];
        }),
      },
    ],
  }) : null, [data, storiesData]);

  if (!storiesData) {
    return <section className="instagram-stories-workspace"><article className="instagram-story-surface instagram-story-unavailable"><GalleryVerticalEnd size={28} /><h3>Instagram Stories</h3><p>Story reporting is unavailable for the selected account and period.</p></article></section>;
  }

  return (
    <section className="instagram-stories-workspace">
      <div className="instagram-stories-primary-grid">
        <LatestStoryPanel onSelect={setSelected} selected={selected} stories={stories} />
        <StoryLiveStatus data={storiesData} generatedAt={data.meta.generated_at} lastSyncAt={data.meta.last_sync_at} story={active} />
      </div>
      <div className="instagram-stories-secondary-grid">
        <div className="instagram-story-evolution">
          {trendData && <PulseTrendCard data={trendData} keys={[{ id: "views", label: "Views", color: "#7c3aed" }, { id: "reach", label: "Reach", color: "#0ea5e9" }]} subtitle="Collected views and reach over the selected period" title="Evolution" />}
        </div>
        <StoryHealth story={active} summary={storiesData.summary} />
      </div>
      <div className="instagram-stories-lower-grid">
        <Behaviour data={storiesData} />
        <History stories={stories} />
      </div>
    </section>
  );
}
