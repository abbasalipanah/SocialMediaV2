import {
  AlertTriangle,
  Check,
  Link2,
  Linkedin,
  PlugZap,
  RefreshCw,
  ShieldCheck,
  Youtube,
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import type { ReportingConnection } from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";
import { OAuthConnectionModal, type OAuthProvider } from "./OAuthConnectionModal";
import { useIntegrationsData } from "./useIntegrationsData";

type AuthorizationStatus = "authorized" | "pending" | "action_required" | "not_authorized";

export type AuthorizationProvider = {
  provider: OAuthProvider;
  label: string;
  description: string;
  status: AuthorizationStatus;
  connection: ReportingConnection | null;
};

const PROVIDER_COPY: Record<OAuthProvider, { label: string; description: string }> = {
  meta: {
    label: "Meta",
    description: "Authorize Facebook and Instagram access through Meta OAuth. Account selection and mapping stay in Settings.",
  },
  tiktok: {
    label: "TikTok",
    description: "Authorize TikTok Business access through OAuth. Account details and maintenance stay in Settings.",
  },
  x: {
    label: "X",
    description: "Authorize read-only X profile and post access. Account selection and mapping stay in Settings.",
  },
  linkedin: {
    label: "LinkedIn",
    description: "Authorize read-only Company Page, post and follower analytics. Page selection and mapping stay in Settings.",
  },
  youtube: {
    label: "YouTube",
    description: "Authorize read-only YouTube channel and analytics access. Channel selection and mapping stay in Settings.",
  },
};

const STATUS_COPY: Record<AuthorizationStatus, { label: string; className: string }> = {
  authorized: { label: "Authorized", className: "status-connected" },
  pending: { label: "Authorized · verification pending", className: "status-action" },
  action_required: { label: "Reconnect required", className: "status-action" },
  not_authorized: { label: "Not authorized", className: "status-disconnected" },
};

function latestConnection(rows: ReportingConnection[]): ReportingConnection | null {
  return rows.reduce<ReportingConnection | null>(
    (latest, item) => (!latest || item.connection_id > latest.connection_id ? item : latest),
    null,
  );
}

function authorizationStatus(connection: ReportingConnection | null): AuthorizationStatus {
  if (!connection) return "not_authorized";
  if (connection.state === "connected") return "authorized";
  if (connection.state === "pending_verification") return "pending";
  return "action_required";
}

export function buildAuthorizationProviders(connections: ReportingConnection[]): AuthorizationProvider[] {
  const metaConnection = latestConnection(
    connections.filter((item) => item.platform === "facebook" || item.platform === "instagram"),
  );
  const tiktokConnection = latestConnection(
    connections.filter((item) => item.platform === "tiktok"),
  );
  const youtubeConnection = latestConnection(
    connections.filter((item) => item.platform === "youtube"),
  );
  const xConnection = latestConnection(
    connections.filter((item) => item.platform === "x"),
  );
  const linkedinConnection = latestConnection(
    connections.filter((item) => item.platform === "linkedin"),
  );

  return ([
    ["meta", metaConnection],
    ["tiktok", tiktokConnection],
    ["x", xConnection],
    ["linkedin", linkedinConnection],
    ["youtube", youtubeConnection],
  ] as const).map(([provider, connection]) => ({
    provider,
    ...PROVIDER_COPY[provider],
    status: authorizationStatus(connection),
    connection,
  }));
}

export default function IntegrationsPage() {
  const { capabilities, isLoading: scopeLoading, rollup, selectedBrand, selectedBrandId } = useBrandScope();
  const data = useIntegrationsData();
  const [activeProvider, setActiveProvider] = useState<OAuthProvider | null>(null);
  const providers = useMemo(
    () => buildAuthorizationProviders(data.connections.data?.items ?? []),
    [data.connections.data?.items],
  );
  const loading = scopeLoading || (!rollup && data.connections.isPending);
  const refreshing = data.connections.isFetching;
  const canAuthorizeMeta = capabilities?.permissions.meta_connection_manage === true && !rollup;
  const canAuthorizeTikTok = capabilities?.permissions.tiktok_connection_manage === true && !rollup;
  const canAuthorizeOAuthChannel = capabilities?.permissions.integrations_visible === true && !rollup;
  const brandName = selectedBrand?.name ?? "Selected Brand";
  const authorizedCount = providers.filter((item) => item.status === "authorized" || item.status === "pending").length;
  const attentionCount = providers.filter((item) => item.status === "action_required").length;

  const refresh = async () => {
    await data.connections.refetch();
  };

  return (
    <main className="page-shell integrations-page oauth-integrations-page">
      <header className="integrations-header">
        <div>
          <p className="eyebrow integrations-eyebrow"><PlugZap size={15} />{brandName}</p>
          <h1>Integrations</h1>
          <p>Authorize social providers for this Brand. Account discovery, selection and mapping are managed separately in Settings.</p>
        </div>
        <button className="settings-action-button" disabled={refreshing || rollup} onClick={() => void refresh()} type="button">
          <RefreshCw className={refreshing ? "spin" : ""} size={16} />
          {refreshing ? "Refreshing status" : "Refresh status"}
        </button>
      </header>

      {rollup && (
        <div className="integrations-alert oauth-integrations-scope-note" role="status">
          <ShieldCheck size={17} />
          <span>Select one individual Brand before starting OAuth. Provider authorization is never applied to an “All child brands” roll-up.</span>
        </div>
      )}
      {data.connections.isError && !rollup && (
        <div className="integrations-alert" role="alert">
          <AlertTriangle size={17} />
          <span>Authorization status could not be loaded. No provider state was inferred from missing data.</span>
        </div>
      )}

      <section aria-label="Authorization summary" className="integrations-summary-grid">
        <SummaryCard icon={<PlugZap size={21} />} label="OAuth providers" tone="indigo" value={5} />
        <SummaryCard icon={<Check size={21} />} label="Authorized" tone="emerald" value={authorizedCount} />
        <SummaryCard icon={<AlertTriangle size={21} />} label="Reconnect required" tone="amber" value={attentionCount} />
      </section>

      <section aria-label="OAuth providers" className="oauth-provider-grid">
        {loading ? (
          <div aria-label="Loading integrations" className="integrations-loading"><RefreshCw className="spin" size={25} /></div>
        ) : providers.map((provider) => (
          <AuthorizationCard
            canAuthorize={provider.provider === "meta"
              ? canAuthorizeMeta
              : provider.provider === "tiktok"
                ? canAuthorizeTikTok
                : canAuthorizeOAuthChannel}
            key={provider.provider}
            onAuthorize={() => setActiveProvider(provider.provider)}
            provider={provider}
            rollup={rollup}
          />
        ))}
      </section>

      <aside className="oauth-integrations-boundary">
        <ShieldCheck size={19} />
        <div>
          <strong>OAuth-only workspace</strong>
          <span>This page never lists provider accounts, external account IDs, sync jobs or account health. Those account-level controls remain in Settings for agency admins and super admins.</span>
        </div>
      </aside>

      {activeProvider && (
        <OAuthConnectionModal
          brandId={selectedBrandId}
          brandName={brandName}
          onAuthorized={() => void refresh()}
          onClose={() => setActiveProvider(null)}
          provider={activeProvider}
        />
      )}
    </main>
  );
}

function SummaryCard({ icon, value, label, tone }: { icon: ReactNode; value: number; label: string; tone: "indigo" | "emerald" | "amber" }) {
  return <article><span className={`integration-summary-icon tone-${tone}`}>{icon}</span><div><strong>{value}</strong><small>{label}</small></div></article>;
}

function ProviderIcon({ provider }: { provider: OAuthProvider }) {
  if (provider === "meta") return <span aria-hidden="true" className="oauth-meta-mark">∞</span>;
  if (provider === "tiktok") return <span aria-hidden="true" className="integration-tiktok-mark">♪</span>;
  if (provider === "youtube") return <Youtube aria-hidden="true" size={22} />;
  if (provider === "linkedin") return <Linkedin aria-hidden="true" size={22} />;
  return <span aria-hidden="true" className="social-x-mark">𝕏</span>;
}

function AuthorizationCard({ provider, canAuthorize, rollup, onAuthorize }: {
  provider: AuthorizationProvider;
  canAuthorize: boolean;
  rollup: boolean;
  onAuthorize: () => void;
}) {
  const status = STATUS_COPY[provider.status];
  const actionLabel = provider.status === "authorized" || provider.status === "pending"
    ? `Reauthorize ${provider.label}`
    : `Authorize ${provider.label}`;
  return (
    <article className="integration-card oauth-provider-card">
      <div className="integration-card-main">
        <div className="integration-card-heading">
          <span className={`integration-platform-icon platform-${provider.provider}`}><ProviderIcon provider={provider.provider} /></span>
          <span><strong>{provider.label}</strong><small>OAuth authorization only</small></span>
          <span className={`integration-status ${status.className}`}>{status.label}</span>
        </div>
        <span className="integration-description">{provider.description}</span>
        <span className="integration-sync"><ShieldCheck size={14} />No connected account details are exposed on this page.</span>
      </div>
      <button className="integration-card-action" disabled={!canAuthorize} onClick={onAuthorize} type="button">
        <Link2 size={14} />
        {rollup ? "Select one Brand to authorize" : actionLabel}
      </button>
    </article>
  );
}
