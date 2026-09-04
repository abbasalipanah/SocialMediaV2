import { lazy, useEffect, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "../../routing";

import type { Platform } from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";
import { FacebookPulseDashboard } from "../facebook/FacebookPulseDashboard";
import { InstagramPulseDashboard } from "../instagram/InstagramPulseDashboard";
import { TikTokPulseDashboard } from "../tiktok/TikTokPulseDashboard";
import { XPulseDashboard } from "../x/XPulseDashboard";
import { YouTubePulseDashboard } from "../youtube/YouTubePulseDashboard";
import {
  DashboardError,
  DashboardLoading,
} from "./DashboardFrame";
import {
  PLATFORM_DESCRIPTIONS,
  PLATFORM_LABELS,
  platformTabs,
  type DashboardTab,
} from "./catalog";
import { DatePeriodControl } from "./DatePeriodControl";
import { useChannelDashboard } from "./useDashboard";
import { useReportingPeriod } from "./useReportingPeriod";
import { ReportExport } from "./ReportExport";

const LinkedInPulseDashboard = lazy(() =>
  import("../linkedin/LinkedInPulseDashboard").then((module) => ({
    default: module.LinkedInPulseDashboard,
  })),
);

function TabContent({ platform, tab, data }: {
  platform: Platform;
  tab: DashboardTab["id"];
  data: NonNullable<ReturnType<typeof useChannelDashboard>["data"]>;
}) {
  const renderers: Record<Platform, () => ReactNode> = {
    facebook: () => (
      <FacebookPulseDashboard
        data={data}
        tab={tab as "cover" | "page" | "content" | "audience"}
      />
    ),
    instagram: () => (
      <InstagramPulseDashboard
        data={data}
        tab={tab as "cover" | "page" | "content" | "stories" | "audience"}
      />
    ),
    tiktok: () => (
      <TikTokPulseDashboard
        data={data}
        tab={tab as "account" | "cover" | "content" | "audience"}
      />
    ),
    x: () => (
      <XPulseDashboard
        data={data}
        tab={tab as "cover" | "profile" | "content" | "audience"}
      />
    ),
    linkedin: () => (
      <LinkedInPulseDashboard
        data={data}
        tab={tab as "cover" | "page" | "content" | "audience"}
      />
    ),
    youtube: () => (
      <YouTubePulseDashboard
        data={data}
        tab={tab as "account" | "cover" | "content" | "audience"}
      />
    ),
  };
  return renderers[platform]();
}

function tabFromSearch(search: string, tabs: DashboardTab[]): DashboardTab["id"] {
  const candidate = new URLSearchParams(search).get("tab")?.toLowerCase();
  return tabs.some((item) => item.id === candidate) ? candidate as DashboardTab["id"] : "cover";
}

export function PlatformPage({ platform }: { platform: Platform }) {
  const { capabilities, selectedBrand, selectedBrandId, rollup } = useBrandScope();
  const location = useLocation();
  const navigate = useNavigate();
  const audienceAvailable = capabilities?.platforms
    .find((item) => item.platform === platform)
    ?.capabilities.some((item) => item.capability === "audience" && ["available", "partial"].includes(item.status)) ?? false;
  const tabs = platformTabs(platform, audienceAvailable);
  const [tab, setTab] = useState<DashboardTab["id"]>(() => tabFromSearch(location.search, tabs));
  const [period, setPeriod] = useReportingPeriod();
  const query = useChannelDashboard(platform, period, tab);

  useEffect(() => {
    setTab(tabFromSearch(location.search, tabs));
  }, [location.search, platform]);

  useEffect(() => {
    const onPopState = () => setTab(tabFromSearch(window.location.search, platformTabs(platform, audienceAvailable)));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [audienceAvailable, platform]);

  useEffect(() => {
    document.title = platform === "instagram" && tab === "stories"
      ? "Instagram Stories · SocialMedia"
      : `${PLATFORM_LABELS[platform]} Dashboard · SocialMedia`;
  }, [platform, tab]);

  const selectTab = (nextTab: DashboardTab["id"]) => {
    setTab(nextTab);
    const params = new URLSearchParams(location.search);
    if (nextTab === "cover") params.delete("tab");
    else params.set("tab", nextTab);
    const search = params.toString();
    navigate({ pathname: location.pathname, search: search ? `?${search}` : "" });
  };

  if (query.isPending) return <DashboardLoading title={PLATFORM_LABELS[platform]} />;
  if (query.isError || !query.data) return <DashboardError retry={() => void query.refetch()} />;
  const data = query.data;
  const storyView = platform === "instagram" && tab === "stories";
  const storyFreshness = data.meta.freshness === "fresh" ? "Live tracking" : data.meta.freshness.replaceAll("_", " ");
  return (
    <main className={`page-shell dashboard-page platform-dashboard-page platform-${platform}`}>
      <header className="platform-dashboard-header">
        <div>
          <h1>{storyView ? "Instagram Stories" : `${PLATFORM_LABELS[platform]} Dashboard`}</h1>
          {storyView ? (
            <div className="platform-story-intro">
              <p>Track story performance, audience behaviour, and story history.</p>
              <span className={`platform-story-freshness status-${data.meta.freshness}`}><i />{storyFreshness}</span>
            </div>
          ) : <p>{PLATFORM_DESCRIPTIONS[platform]}</p>}
        </div>
        <div className="platform-dashboard-toolbar">
          <div aria-label="Dashboard sections" className="platform-toolbar-tabs" role="tablist">
            {tabs.map((item) => (
              <button
                aria-selected={tab === item.id}
                className={tab === item.id ? "active" : ""}
                key={item.id}
                onClick={() => selectTab(item.id)}
                role="tab"
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
          <DatePeriodControl
            ariaLabel={storyView ? "Date range" : "Date period"}
            controlClassName="platform-range-control"
            label={storyView ? "Date Range" : "Date Period"}
            onChange={setPeriod}
            period={period}
            resolvedEndDate={data.meta.date_range.end_on}
            resolvedStartDate={data.meta.date_range.start_on}
          />
          <ReportExport
            accountId={data.meta.resolved_account_ids.length === 1 ? data.meta.resolved_account_ids[0] : undefined}
            brandId={selectedBrandId}
            endDate={data.meta.date_range.end_on}
            metrics={data.metrics}
            rollup={rollup}
            startDate={data.meta.date_range.start_on}
            subtitle={`${selectedBrand?.name ?? "Selected Brand"} · ${data.meta.date_range.start_on} to ${data.meta.date_range.end_on}`}
            surface={platform}
            tab={tab}
            title={storyView ? "Instagram Stories" : `${PLATFORM_LABELS[platform]} Dashboard`}
          />
        </div>
      </header>
      <div aria-live="polite" role="tabpanel">
        <TabContent data={data} platform={platform} tab={tab} />
      </div>
    </main>
  );
}
