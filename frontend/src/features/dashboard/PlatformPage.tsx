import { CalendarDays, Download } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "../../routing";

import type { Platform } from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";
import { FacebookPulseDashboard } from "../facebook/FacebookPulseDashboard";
import { InstagramPulseDashboard } from "../instagram/InstagramPulseDashboard";
import { TikTokPulseDashboard } from "../tiktok/TikTokPulseDashboard";
import {
  CoverageNotice,
  DashboardError,
  DashboardLoading,
} from "./DashboardFrame";
import { PLATFORM_DESCRIPTIONS, PLATFORM_LABELS, RANGE_OPTIONS, platformTabs, type DashboardTab, type RangeKey } from "./catalog";
import { useChannelDashboard } from "./useDashboard";

function TabContent({ platform, tab, data }: {
  platform: Platform;
  tab: DashboardTab["id"];
  data: NonNullable<ReturnType<typeof useChannelDashboard>["data"]>;
}) {
  if (platform === "facebook") {
    return <FacebookPulseDashboard data={data} tab={tab as "cover" | "page" | "content" | "audience"} />;
  }
  if (platform === "instagram") {
    return <InstagramPulseDashboard data={data} tab={tab as "cover" | "page" | "content" | "stories" | "audience"} />;
  }
  return <TikTokPulseDashboard data={data} tab={tab as "account" | "cover" | "content" | "audience"} />;
}

function tabFromSearch(search: string, tabs: DashboardTab[]): DashboardTab["id"] {
  const candidate = new URLSearchParams(search).get("tab")?.toLowerCase();
  return tabs.some((item) => item.id === candidate) ? candidate as DashboardTab["id"] : "cover";
}

export function PlatformPage({ platform }: { platform: Platform }) {
  const { capabilities, selectedBrand } = useBrandScope();
  const location = useLocation();
  const navigate = useNavigate();
  const audienceAvailable = capabilities?.platforms
    .find((item) => item.platform === platform)
    ?.capabilities.some((item) => item.capability === "audience" && ["available", "partial"].includes(item.status)) ?? false;
  const tabs = platformTabs(platform, audienceAvailable);
  const [tab, setTab] = useState<DashboardTab["id"]>(() => tabFromSearch(location.search, tabs));
  const [range, setRange] = useState<RangeKey>("last_30_days");
  const query = useChannelDashboard(platform, range, tab);

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

  const downloadDashboard = () => {
    if (!query.data) return;
    const blob = new Blob([JSON.stringify(query.data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${platform}-dashboard-${query.data.meta.date_range.end_on}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
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
          <label className="platform-range-control">
            <span><CalendarDays size={18} /></span>
            <span><small>{storyView ? "Date Range" : "Date Period"}</small><select aria-label={storyView ? "Date range" : "Date period"} onChange={(event) => setRange(event.target.value as RangeKey)} value={range}>{RANGE_OPTIONS.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></span>
          </label>
          <button
            aria-label="Download dashboard data"
            className="dashboard-download-button"
            onClick={downloadDashboard}
            title={`${selectedBrand?.name ?? "Selected Brand"} · ${data.meta.date_range.start_on} to ${data.meta.date_range.end_on}`}
            type="button"
          >
            <Download size={19} />
          </button>
        </div>
      </header>
      <CoverageNotice status={data.meta.data_status} warnings={data.meta.warnings} />
      <div aria-live="polite" role="tabpanel">
        <TabContent data={data} platform={platform} tab={tab} />
      </div>
    </main>
  );
}
