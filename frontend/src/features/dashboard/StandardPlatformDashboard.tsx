import type { Platform, PlatformDashboard } from "../../api";
import {
  AudienceSection,
  CommunitySection,
  ContentSection,
  HonestEmpty,
  MetricBand,
  TrendSection,
} from "./DashboardCards";
import type { DashboardTab } from "./catalog";

export function StandardPlatformDashboard({
  data,
  platform,
  tab,
}: {
  data: PlatformDashboard;
  platform: Platform;
  tab: DashboardTab["id"];
}) {
  if (["account", "page", "profile"].includes(tab)) {
    return (
      <>
        <MetricBand data={data} scope={platform} />
        <TrendSection data={data} />
      </>
    );
  }
  if (tab === "content" || tab === "videos") {
    return (
      <>
        <ContentSection content={data.content} />
        <CommunitySection data={data} />
      </>
    );
  }
  if (tab === "audience") {
    return <AudienceSection breakdowns={data.breakdowns} />;
  }
  if (tab !== "cover") {
    return (
      <HonestEmpty
        copy="This section is not available for the selected platform."
        title="Section unavailable"
      />
    );
  }
  return (
    <>
      <MetricBand data={data} scope={platform} />
      <TrendSection data={data} />
      <ContentSection content={data.content} />
      <CommunitySection data={data} />
    </>
  );
}
