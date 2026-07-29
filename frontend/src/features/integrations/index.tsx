import {
  Activity,
  AlertTriangle,
  Check,
  ChevronRight,
  CircleOff,
  Clock3,
  Facebook,
  Instagram,
  Link2,
  PlugZap,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import type {
  OperationsReadiness,
  Platform,
  ReportingAccount,
  ReportingConnection,
  ReportingSyncJob,
  WorkspaceCapabilities,
} from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";
import { humanize } from "../dashboard/format";
import { useSettingsData } from "../settings/useSettingsData";
import { TikTokConnectionModal } from "./TikTokConnectionModal";
import { MetaConnectionModal } from "./MetaConnectionModal";

type IntegrationStatus = "connected" | "action_required" | "not_connected";
type StatusFilter = "all" | IntegrationStatus;

type SocialIntegrationPlatform = {
  platform: Platform;
  label: string;
  description: string;
  connectionMode: string;
  status: IntegrationStatus;
  accounts: ReportingAccount[];
  connection: ReportingConnection | null;
  jobs: ReportingSyncJob[];
  capabilities: Array<{ capability: string; status: string; reason: string }>;
  lastSyncAt: string | null;
  pendingJobs: number;
  failedJobs: number;
};

const PLATFORMS: Platform[] = ["facebook", "instagram", "tiktok"];

const PLATFORM_META: Record<Platform, { label: string; description: string; connectionMode: string }> = {
  facebook: {
    label: "Facebook",
    description: "Facebook Pages, audience, content and community reporting projected from the approved Meta connector.",
    connectionMode: "Managed through the Accumulate Meta connection",
  },
  instagram: {
    label: "Instagram",
    description: "Instagram Business profiles, posts, reels, stories and audience reporting linked to the selected Brand.",
    connectionMode: "Managed through the Accumulate Meta connection",
  },
  tiktok: {
    label: "TikTok",
    description: "TikTok Business account, video performance and audience capabilities with Brand-scoped self-service connection.",
    connectionMode: "Brand-scoped TikTok self-service",
  },
};

const STATUS_META: Record<IntegrationStatus, { label: string; className: string }> = {
  connected: { label: "Connected", className: "status-connected" },
  action_required: { label: "Action required", className: "status-action" },
  not_connected: { label: "Not connected", className: "status-disconnected" },
};

function latestTimestamp(values: Array<string | null | undefined>): string | null {
  return values.reduce<string | null>((latest, value) => {
    if (!value || Number.isNaN(new Date(value).getTime())) return latest;
    if (!latest || new Date(value).getTime() > new Date(latest).getTime()) return value;
    return latest;
  }, null);
}

export function buildSocialIntegrations({
  accounts,
  connections,
  jobs,
  readiness,
  capabilities,
}: {
  accounts: ReportingAccount[];
  connections: ReportingConnection[];
  jobs: ReportingSyncJob[];
  readiness: OperationsReadiness | undefined;
  capabilities: WorkspaceCapabilities | null;
}): SocialIntegrationPlatform[] {
  return PLATFORMS.map((platform) => {
    const platformAccounts = accounts.filter((account) => account.platform === platform);
    const connection = connections.find((item) => item.platform === platform) ?? null;
    const platformJobs = jobs.filter((job) => job.platform === platform);
    const capabilityRows = capabilities?.platforms.find((item) => item.platform === platform)?.capabilities ?? [];
    const readinessRow = readiness?.platforms.find((item) => item.platform === platform);
    const pendingJobs = platformJobs.filter((job) => ["pending", "running"].includes(job.status)).length;
    const failedJobs = platformJobs.filter((job) => job.status === "failed").length;
    const connectedAccounts = platformAccounts.filter((account) => account.connection_state === "connected");
    const accountIssue = platformAccounts.some(
      (account) => account.connection_state !== "connected" || account.health_status !== "healthy",
    );
    const capabilityIssue = capabilityRows.some((item) =>
      ["blocked_configuration", "not_approved", "unsupported", "partial"].includes(item.status),
    );
    const connectionIssue = Boolean(connection && connection.state !== "connected");
    const status: IntegrationStatus = platformAccounts.length === 0
      ? "not_connected"
      : connectedAccounts.length === platformAccounts.length
        && !accountIssue
        && !capabilityIssue
        && !connectionIssue
        && failedJobs === 0
        ? "connected"
        : "action_required";

    return {
      platform,
      ...PLATFORM_META[platform],
      status,
      accounts: platformAccounts,
      connection,
      jobs: platformJobs,
      capabilities: capabilityRows,
      lastSyncAt: latestTimestamp([
        readinessRow?.last_sync_at,
        ...platformAccounts.map((account) => account.last_synced_at),
      ]),
      pendingJobs: Math.max(pendingJobs, readinessRow?.pending_job_count ?? 0),
      failedJobs,
    };
  });
}

export default function IntegrationsPage() {
  const { capabilities, isLoading: scopeLoading, rollup, selectedBrand, selectedBrandId } = useBrandScope();
  const data = useSettingsData();
  const [selectedPlatformId, setSelectedPlatformId] = useState<Platform | "">("facebook");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [tiktokConnectOpen, setTikTokConnectOpen] = useState(false);
  const [metaConnectPlatform, setMetaConnectPlatform] = useState<"facebook" | "instagram" | null>(null);

  const platforms = useMemo(
    () => buildSocialIntegrations({
      accounts: data.accounts.data?.items ?? [],
      connections: data.connections.data?.items ?? [],
      jobs: data.jobs.data?.items ?? [],
      readiness: data.readiness.data,
      capabilities,
    }),
    [capabilities, data.accounts.data?.items, data.connections.data?.items, data.jobs.data?.items, data.readiness.data],
  );
  const filteredPlatforms = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return platforms.filter((platform) => {
      if (statusFilter !== "all" && platform.status !== statusFilter) return false;
      if (!normalizedQuery) return true;
      return platform.label.toLowerCase().includes(normalizedQuery)
        || platform.accounts.some((account) =>
          account.display_name.toLowerCase().includes(normalizedQuery)
          || account.external_id.toLowerCase().includes(normalizedQuery),
        );
    });
  }, [platforms, query, statusFilter]);

  useEffect(() => {
    if (filteredPlatforms.some((platform) => platform.platform === selectedPlatformId)) return;
    setSelectedPlatformId(filteredPlatforms[0]?.platform ?? "");
  }, [filteredPlatforms, selectedPlatformId]);

  const selectedPlatform = selectedPlatformId
    ? platforms.find((platform) => platform.platform === selectedPlatformId) ?? null
    : null;
  const loading = scopeLoading
    || data.accounts.isPending
    || data.connections.isPending
    || data.jobs.isPending
    || data.readiness.isPending;
  const refreshing = data.accounts.isFetching
    || data.connections.isFetching
    || data.jobs.isFetching
    || data.readiness.isFetching;
  const hasError = data.accounts.isError
    || data.connections.isError
    || data.jobs.isError
    || data.readiness.isError;
  const canManage = capabilities?.permissions.settings_visible === true;
  const canManageTikTok = capabilities?.permissions.tiktok_connection_manage === true && !rollup;
  const canManageMeta = capabilities?.permissions.meta_connection_manage === true && !rollup;
  const mutationAvailable = capabilities?.permissions.operation_mutation_available === true;
  const brandName = selectedBrand?.name ?? (rollup ? "Selected Brand family" : "Selected Brand");

  const refresh = async () => {
    await Promise.all([
      data.accounts.refetch(),
      data.connections.refetch(),
      data.jobs.refetch(),
      data.readiness.refetch(),
    ]);
  };

  return (
    <main className="page-shell integrations-page">
      <header className="integrations-header">
        <div>
          <p className="eyebrow integrations-eyebrow"><PlugZap size={15} />{brandName}</p>
          <h1>Integrations</h1>
          <p>Connect social accounts and monitor their reporting, capability and sync status in one place.</p>
        </div>
        <button className="settings-action-button" disabled={refreshing} onClick={() => void refresh()} type="button">
          <RefreshCw className={refreshing ? "spin" : ""} size={16} />
          {refreshing ? "Refreshing status" : "Refresh status"}
        </button>
      </header>

      {hasError && (
        <div className="integrations-alert" role="alert">
          <AlertTriangle size={17} />
          <span>Some integration status could not be loaded. No connection decision was inferred from missing data.</span>
        </div>
      )}

      <section aria-label="Integration summary" className="integrations-summary-grid">
        <SummaryCard icon={<PlugZap size={21} />} label="Platforms" tone="indigo" value={3} />
        <SummaryCard icon={<Check size={21} />} label="Connected" tone="emerald" value={platforms.filter((item) => item.status === "connected").length} />
        <SummaryCard icon={<AlertTriangle size={21} />} label="Action required" tone="amber" value={platforms.filter((item) => item.status === "action_required").length} />
      </section>

      <section className="integrations-layout">
        <div className="integrations-catalog">
          <div className="integrations-controls">
            <label className="integrations-search">
              <Search aria-hidden="true" size={16} />
              <span className="sr-only">Search platforms or accounts</span>
              <input onChange={(event) => setQuery(event.target.value)} placeholder="Search platforms or accounts" value={query} />
            </label>
            <label className="integrations-filter">
              <span className="sr-only">Filter integration status</span>
              <select onChange={(event) => setStatusFilter(event.target.value as StatusFilter)} value={statusFilter}>
                <option value="all">All statuses</option>
                <option value="connected">Connected</option>
                <option value="action_required">Action required</option>
                <option value="not_connected">Not connected</option>
              </select>
            </label>
          </div>

          {loading ? (
            <div aria-label="Loading integrations" className="integrations-loading"><RefreshCw className="spin" size={25} /></div>
          ) : filteredPlatforms.length ? (
            <div className="integrations-card-grid">
              {filteredPlatforms.map((platform) => (
                <IntegrationCard
                  canManage={canManage}
                  canManageTikTok={canManageTikTok}
                  canManageMeta={canManageMeta}
                  isSelected={selectedPlatformId === platform.platform}
                  key={platform.platform}
                  onConnectTikTok={() => setTikTokConnectOpen(true)}
                  onConnectMeta={() => {
                    if (platform.platform === "facebook" || platform.platform === "instagram") {
                      setMetaConnectPlatform(platform.platform);
                    }
                  }}
                  onSelect={() => setSelectedPlatformId(platform.platform)}
                  platform={platform}
                />
              ))}
            </div>
          ) : (
            <div className="integrations-empty"><Search size={22} /><strong>No matching integrations</strong><span>Try another platform, account or status.</span></div>
          )}
        </div>

        <IntegrationDetailPanel
          canManage={canManage}
          canManageTikTok={canManageTikTok}
          canManageMeta={canManageMeta}
          mutationAvailable={mutationAvailable}
          onConnectTikTok={() => setTikTokConnectOpen(true)}
          onConnectMeta={(platform) => setMetaConnectPlatform(platform)}
          onClose={() => setSelectedPlatformId("")}
          platform={selectedPlatform}
        />
      </section>
      {tiktokConnectOpen && <TikTokConnectionModal brandId={selectedBrandId} brandName={brandName} onClose={() => setTikTokConnectOpen(false)} onConnected={() => void refresh()} />}
      {metaConnectPlatform && (
        <MetaConnectionModal
          brandId={selectedBrandId}
          brandName={brandName}
          focusPlatform={metaConnectPlatform}
          onClose={() => setMetaConnectPlatform(null)}
          onConnected={() => void refresh()}
        />
      )}
    </main>
  );
}

function SummaryCard({ icon, value, label, tone }: { icon: ReactNode; value: number; label: string; tone: "indigo" | "emerald" | "amber" }) {
  return <article><span className={`integration-summary-icon tone-${tone}`}>{icon}</span><div><strong>{value}</strong><small>{label}</small></div></article>;
}

function PlatformIcon({ platform }: { platform: Platform }) {
  if (platform === "facebook") return <Facebook size={24} />;
  if (platform === "instagram") return <Instagram size={24} />;
  return <span aria-hidden="true" className="integration-tiktok-mark">♪</span>;
}

function IntegrationCard({ platform, isSelected, canManage, canManageTikTok, canManageMeta, onSelect, onConnectTikTok, onConnectMeta }: {
  platform: SocialIntegrationPlatform;
  isSelected: boolean;
  canManage: boolean;
  canManageTikTok: boolean;
  canManageMeta: boolean;
  onSelect: () => void;
  onConnectTikTok: () => void;
  onConnectMeta: () => void;
}) {
  const status = STATUS_META[platform.status];
  const metaPlatform = platform.platform === "facebook" || platform.platform === "instagram";
  const actionLabel = platform.status === "connected"
    ? "View"
    : platform.platform === "tiktok" && canManageTikTok
      ? "Connect TikTok"
      : metaPlatform && canManageMeta
        ? "Connect Meta"
        : canManage
          ? "Manage in Settings"
          : "View status";
  return (
    <article className={`integration-card${isSelected ? " selected" : ""}`}>
      <button className="integration-card-main" onClick={onSelect} type="button">
        <span className="integration-card-heading">
          <span className={`integration-platform-icon platform-${platform.platform}`}><PlatformIcon platform={platform.platform} /></span>
          <span><strong>{platform.label}</strong><small>{platform.accounts.length ? `${platform.accounts.length} account${platform.accounts.length === 1 ? "" : "s"} linked` : "No account linked"}</small></span>
          <span className={`integration-status ${status.className}`}>{status.label}</span>
        </span>
        <span className="integration-description">{platform.description}</span>
        <span className="integration-sync"><ShieldCheck size={14} />{platform.lastSyncAt ? `Last sync ${formatDateTime(platform.lastSyncAt)}` : "No sync completed yet"}</span>
      </button>
      {platform.platform === "tiktok" && canManageTikTok && platform.status !== "connected" ? (
        <button className="integration-card-action" onClick={onConnectTikTok} type="button">{actionLabel}<ChevronRight size={14} /></button>
      ) : metaPlatform && canManageMeta && platform.status !== "connected" ? (
        <button className="integration-card-action" onClick={onConnectMeta} type="button">{actionLabel}<ChevronRight size={14} /></button>
      ) : canManage && platform.status !== "connected" ? (
        <Link className="integration-card-action" to="/settings">{actionLabel}<ChevronRight size={14} /></Link>
      ) : (
        <button className="integration-card-action" onClick={onSelect} type="button">{actionLabel}<ChevronRight size={14} /></button>
      )}
    </article>
  );
}

function IntegrationDetailPanel({ platform, canManage, canManageTikTok, canManageMeta, mutationAvailable, onClose, onConnectTikTok, onConnectMeta }: {
  platform: SocialIntegrationPlatform | null;
  canManage: boolean;
  canManageTikTok: boolean;
  canManageMeta: boolean;
  mutationAvailable: boolean;
  onClose: () => void;
  onConnectTikTok: () => void;
  onConnectMeta: (platform: "facebook" | "instagram") => void;
}) {
  if (!platform) return <aside className="integration-detail-placeholder" />;
  const status = STATUS_META[platform.status];
  return (
    <aside className="integration-detail">
      <div className="integration-detail-heading">
        <div className={`integration-platform-icon platform-${platform.platform}`}><PlatformIcon platform={platform.platform} /></div>
        <div><h2>{platform.label}</h2><span className={`integration-status ${status.className}`}>{status.label}</span></div>
        <button aria-label="Close integration details" onClick={onClose} type="button"><X size={16} /></button>
      </div>
      <div className="integration-detail-content">
        <section>
          <h3>Connected accounts ({platform.accounts.length})</h3>
          <div className="integration-account-list">
            {platform.accounts.length ? platform.accounts.map((account) => (
              <article key={account.account_id}>
                <div><strong>{account.display_name}</strong><small>{account.external_id}</small></div>
                <span className={account.connection_state === "connected" ? "account-active" : "account-attention"}>{humanize(account.connection_state)}</span>
                <dl><div><dt>Health</dt><dd>{humanize(account.health_status)}</dd></div><div><dt>Backfill</dt><dd>{humanize(account.backfill_status)}</dd></div><div><dt>Last sync</dt><dd>{formatDateTime(account.last_synced_at)}</dd></div></dl>
              </article>
            )) : <div className="integration-no-accounts">No account is linked to this Brand.</div>}
          </div>
        </section>

        <section>
          <h3>Reporting capabilities</h3>
          <div className="integration-capability-list">
            {platform.capabilities.length ? platform.capabilities.map((capability) => {
              const available = capability.status === "available";
              return <div key={capability.capability}><span className={available ? "available" : "unavailable"}>{available ? <Check size={14} /> : <CircleOff size={14} />}</span><div><strong>{humanize(capability.capability)}</strong><small>{humanize(capability.status)} · {humanize(capability.reason)}</small></div></div>;
            }) : <div className="integration-no-capabilities">Capability status is unavailable.</div>}
          </div>
        </section>

        <section className="integration-operations">
          <h3>Operations</h3>
          <div><Activity size={15} /><span><strong>{platform.pendingJobs}</strong> pending or running</span></div>
          <div><AlertTriangle size={15} /><span><strong>{platform.failedJobs}</strong> failed jobs</span></div>
          <div><Clock3 size={15} /><span>{platform.lastSyncAt ? formatDateTime(platform.lastSyncAt) : "Never synced"}</span></div>
        </section>

        <div className="integration-mode-note"><ShieldCheck size={16} /><div><strong>{platform.connectionMode}</strong><span>{platform.platform === "tiktok" && canManageTikTok ? "TikTok authorization starts only after an explicit Connect action and a successful backend readiness check." : (platform.platform === "facebook" || platform.platform === "instagram") && canManageMeta ? "Meta authorization starts only after an explicit Connect action. Account selection remains Brand-scoped." : mutationAvailable ? "Operational changes require an explicit confirmed action." : "Direct connect, disconnect and sync mutations are disabled by the backend runtime."}</span></div></div>

        {platform.platform === "tiktok" && canManageTikTok ? <button className="integration-manage-button" onClick={onConnectTikTok} type="button"><Link2 size={15} />{platform.accounts.length ? "Connect another TikTok account" : "Connect TikTok"}</button> : (platform.platform === "facebook" || platform.platform === "instagram") && canManageMeta ? <button className="integration-manage-button" onClick={() => onConnectMeta(platform.platform as "facebook" | "instagram")} type="button"><Link2 size={15} />{platform.accounts.length ? "Connect another Meta account" : "Connect Meta"}</button> : canManage ? <Link className="integration-manage-button" to="/settings"><Link2 size={15} />Manage in Settings</Link> : <div className="integration-readonly-note"><CircleOff size={15} />You can review status, but connection management is not available for this session.</div>}
      </div>
    </aside>
  );
}

function formatDateTime(value: string | null): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}
