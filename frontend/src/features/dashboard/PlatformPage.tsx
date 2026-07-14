import { Facebook, Instagram, Radio, UserRound } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import type { Platform } from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";
import { usePlatformAccounts } from "../../app/usePlatformAccounts";
import {
  AudienceSection,
  CommunitySection,
  ContentSection,
  HonestEmpty,
  MetricBand,
  TrendSection,
} from "./DashboardCards";
import {
  CoverageNotice,
  DashboardError,
  DashboardHeader,
  DashboardLoading,
  DashboardTabs,
} from "./DashboardFrame";
import { PLATFORM_LABELS, platformTabs, type DashboardTab, type RangeKey } from "./catalog";
import { formatDate, humanize } from "./format";
import { useChannelDashboard } from "./useDashboard";

function PlatformIcon({ platform }: { platform: Platform }) {
  if (platform === "facebook") return <Facebook size={25} />;
  if (platform === "instagram") return <Instagram size={25} />;
  return <span aria-hidden="true" className="profile-tiktok">♪</span>;
}

function ProfileHeader({ platform }: { platform: Platform }) {
  const accounts = usePlatformAccounts(platform);
  const selected = accounts.selectedAccountId === "all"
    ? null
    : accounts.accounts.find((account) => account.account_id === accounts.selectedAccountId);
  return (
    <section className={`platform-profile platform-${platform}`}>
      <div className="platform-profile-icon"><PlatformIcon platform={platform} /></div>
      <div>
        <p>{selected ? humanize(selected.connection_state) : `${accounts.accounts.length} linked account${accounts.accounts.length === 1 ? "" : "s"}`}</p>
        <h2>{selected?.display_name ?? `All ${PLATFORM_LABELS[platform]} accounts`}</h2>
        <span>{selected ? `${selected.external_id} · Last sync ${formatDate(selected.last_synced_at)}` : "Aggregated within the authorized Brand scope"}</span>
      </div>
      {selected && <span className={`account-health health-${selected.health_status}`}>{humanize(selected.health_status)}</span>}
    </section>
  );
}

function TabContent({ platform, tab, data }: {
  platform: Platform;
  tab: DashboardTab["id"];
  data: NonNullable<ReturnType<typeof useChannelDashboard>["data"]>;
}) {
  if (tab === "cover") {
    return <HonestEmpty title="Cover media is unavailable" copy="The reporting contract does not currently return a cover asset. No placeholder image is presented as live data." />;
  }
  if (tab === "content" || tab === "videos") return <ContentSection content={data.content} />;
  if (tab === "stories") return <ContentSection content={data.content} storyOnly />;
  if (tab === "audience") return <AudienceSection breakdowns={data.breakdowns} />;
  return (
    <>
      <MetricBand data={data} scope={platform} />
      <TrendSection data={data} />
      <CommunitySection data={data} />
    </>
  );
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
    <main className="page-shell dashboard-page">
      <DashboardHeader
        description={description}
        exportSubtitle={`${selectedBrand?.name ?? "Selected Brand"} · ${data.meta.date_range.start_on} to ${data.meta.date_range.end_on}`}
        freshness={data.meta.freshness}
        lastSync={data.meta.last_sync_at}
        metrics={data.metrics}
        onRange={setRange}
        range={range}
        status={data.meta.data_status}
        title={PLATFORM_LABELS[platform]}
      />
      <ProfileHeader platform={platform} />
      <CoverageNotice status={data.meta.data_status} warnings={data.meta.warnings} />
      <DashboardTabs
        active={tab}
        onSelect={(id) => setTab(id as DashboardTab["id"])}
        tabs={tabs}
      >
        <TabContent data={data} platform={platform} tab={tab} />
      </DashboardTabs>
    </main>
  );
}
