import { CalendarDays } from "lucide-react";
import { useEffect, useState } from "react";

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
import { ExportPng } from "./ExportPng";
import { PLATFORM_LABELS, RANGE_OPTIONS, platformTabs, type DashboardTab, type RangeKey } from "./catalog";
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
  return <TikTokPulseDashboard data={data} tab={tab as "overview" | "videos" | "audience"} />;
}

export function PlatformPage({ platform, description }: { platform: Platform; description: string }) {
  const { capabilities, selectedBrand } = useBrandScope();
  const audienceAvailable = capabilities?.platforms
    .find((item) => item.platform === platform)
    ?.capabilities.some((item) => item.capability === "audience" && ["available", "partial"].includes(item.status)) ?? false;
  const tabs = platformTabs(platform, audienceAvailable);
  const [tab, setTab] = useState<DashboardTab["id"]>(tabs[0]?.id ?? "overview");
  const [range, setRange] = useState<RangeKey>("last_30_days");
  const query = useChannelDashboard(platform, range, tab);

  useEffect(() => {
    if (!tabs.some((item) => item.id === tab)) setTab(tabs[0]?.id ?? "overview");
  }, [tab, tabs]);

  if (query.isPending) return <DashboardLoading title={PLATFORM_LABELS[platform]} />;
  if (query.isError || !query.data) return <DashboardError retry={() => void query.refetch()} />;
  const data = query.data;
  return (
    <main className={`page-shell dashboard-page platform-dashboard-page platform-${platform}`}>
      <header className="platform-dashboard-header">
        <div>
          <h1>{PLATFORM_LABELS[platform]} Dashboard</h1>
          <p>{description}</p>
        </div>
        <div className="platform-dashboard-toolbar">
          <div aria-label="Dashboard sections" className="platform-toolbar-tabs" role="tablist">
            {tabs.map((item) => (
              <button
                aria-selected={tab === item.id}
                className={tab === item.id ? "active" : ""}
                key={item.id}
                onClick={() => setTab(item.id)}
                role="tab"
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
          <label className="platform-range-control">
            <span><CalendarDays size={18} /></span>
            <span><small>Date Period</small><select aria-label="Date period" onChange={(event) => setRange(event.target.value as RangeKey)} value={range}>{RANGE_OPTIONS.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></span>
          </label>
          <ExportPng
            metrics={data.metrics}
            subtitle={`${selectedBrand?.name ?? "Selected Brand"} · ${data.meta.date_range.start_on} to ${data.meta.date_range.end_on}`}
            title={`${PLATFORM_LABELS[platform]} Dashboard`}
          />
        </div>
      </header>
      <CoverageNotice status={data.meta.data_status} warnings={data.meta.warnings} />
      <div aria-live="polite" role="tabpanel">
        <TabContent data={data} platform={platform} tab={tab} />
      </div>
    </main>
  );
}
