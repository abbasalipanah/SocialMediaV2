import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Link2, ListChecks, LockKeyhole, RefreshCw, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";

import { apiQuery, auditSchema, queryString, tiktokActivationReadinessSchema } from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";
import { AccountsTable, BrandsTable, LinksTable, SettingsTableError, SettingsTableLoading, SyncTable, type SettingsView } from "./SettingsTables";
import { SetupDrawer } from "./SetupDrawer";
import { useSettingsData } from "./useSettingsData";

const VIEWS: Array<{ id: SettingsView; label: string; hint: string }> = [
  { id: "brands", label: "Brands", hint: "SSO-authorized Brands and social setup readiness" },
  { id: "accounts", label: "Platform Accounts", hint: "Accounts stored by Social Media" },
  { id: "links", label: "Mappings", hint: "Active Brand-to-account links" },
  { id: "sync", label: "Sync & Backfill", hint: "Sync history and backfill readiness" },
];

export default function SettingsPage() {
  const location = useLocation();
  const nested = location.pathname !== "/settings";
  const [view, setView] = useState<SettingsView>("brands");
  const [setupOpen, setSetupOpen] = useState(false);
  const { capabilities } = useBrandScope();
  const data = useSettingsData();
  const mutationAvailable = capabilities?.permissions.operation_mutation_available ?? false;
  const brands = data.brands.data?.items ?? [];
  const accounts = data.accounts.data?.items ?? [];
  const links = data.links.data?.items ?? [];
  const jobs = data.jobs.data?.items ?? [];
  const currentAccess = brands.filter((item) => item.access_mode !== null).length;
  const ready = brands.filter((item) => item.linked_account_count > 0 && item.last_sync_at !== null).length;
  const pendingSetup = brands.filter((item) => item.linked_account_count > 0 && item.last_sync_at === null).length;
  const missingAccounts = brands.filter((item) => item.linked_account_count === 0).length;
  const connected = accounts.filter((item) => item.connection_state === "connected").length;
  const needsAttention = accounts.filter((item) => item.health_status !== "healthy" || item.connection_state !== "connected").length
    + jobs.filter((item) => item.status === "failed").length;
  const summary = [
    { label: "Current Access", value: currentAccess, tone: "indigo" },
    { label: "Ready", value: ready, tone: "emerald" },
    { label: "Pending Setup", value: pendingSetup, tone: "amber" },
    { label: "Missing Accounts", value: missingAccounts, tone: "rose" },
    { label: "Connected", value: connected, tone: "sky" },
    { label: "Needs Attention", value: needsAttention, tone: needsAttention > 0 ? "rose" : "slate" },
  ];
  const refreshing = data.brands.isFetching || data.accounts.isFetching || data.links.isFetching || data.jobs.isFetching;

  const navigation = VIEWS.map(({ id, label, hint }) => (
    <button
      aria-label={`${label}: ${hint}`}
      aria-selected={view === id}
      className={view === id ? "active" : ""}
      key={id}
      onClick={() => setView(id)}
      role="tab"
      title={hint}
      type="button"
    >
      {label}
    </button>
  ));

  const refreshPlatform = async () => {
    await Promise.all([data.accounts.refetch(), data.links.refetch(), data.jobs.refetch(), data.brands.refetch()]);
  };

  const selectedQuery = view === "brands" ? data.brands : view === "accounts" ? data.accounts : view === "links" ? data.links : data.jobs;
  const table = selectedQuery.isPending
    ? <SettingsTableLoading />
    : selectedQuery.isError || !selectedQuery.data
      ? <SettingsTableError retry={() => void selectedQuery.refetch()} />
      : view === "brands"
        ? <BrandsTable items={brands} navigation={navigation} onSetup={() => setSetupOpen(true)} />
        : view === "accounts"
          ? <AccountsTable items={accounts} mutationAvailable={mutationAvailable} navigation={navigation} />
          : view === "links"
            ? <LinksTable items={links} navigation={navigation} />
            : <SyncTable items={jobs} mutationAvailable={mutationAvailable} navigation={navigation} />;

  return (
    <main className="page-shell settings-page">
      <header className="settings-header performance-settings-header">
        <div>
          <p className="eyebrow">Settings</p>
          <h1>Brand Setup and Account Mapping</h1>
          <p>Manage social Brands, platform accounts and sync readiness from one table-first workspace.</p>
        </div>
        <div className="settings-header-actions">
          <button className="settings-action-button" onClick={() => setView("links")} type="button"><Link2 size={16} />Linked brands</button>
          <button className="settings-action-button emphasized" onClick={() => setView("sync")} type="button"><ListChecks size={16} />Manual sync</button>
          <button className="settings-action-button" disabled={refreshing} onClick={() => void refreshPlatform()} type="button"><RefreshCw className={refreshing ? "spin" : ""} size={16} />{refreshing ? "Refreshing" : "Refresh Platform"}</button>
        </div>
      </header>
      {data.completionMessage && <div className="settings-toast" role="status"><CheckCircle2 size={18} /><span>{data.completionMessage}</span><button aria-label="Dismiss" onClick={data.dismissCompletion} type="button"><X size={16} /></button></div>}
      <section aria-label="Settings summary" className="settings-summary-grid">{summary.map((item) => <article className={`tone-${item.tone}`} key={item.label}><span>{item.label}</span><strong>{item.value}</strong></article>)}</section>
      <div role="tabpanel">{table}</div>
      {nested && <Outlet />}
      <SetupDrawer
        accounts={data.accounts.data?.items ?? []}
        brands={data.brands.data?.items ?? []}
        connections={data.connections.data?.items ?? []}
        jobs={data.jobs.data?.items ?? []}
        mutationAvailable={mutationAvailable}
        onClose={() => setSetupOpen(false)}
        open={setupOpen}
        readiness={data.readiness.data}
      />
    </main>
  );
}

export function TikTokConnectPage() {
  const { selectedBrandId } = useBrandScope();
  const query = useQuery({
    queryKey: ["settings", "tiktok", "activation-readiness", selectedBrandId],
    queryFn: ({ signal }) => apiQuery(
      `/api/settings/tiktok/activation-readiness${queryString({ brand_id: selectedBrandId })}`,
      tiktokActivationReadinessSchema,
      signal,
    ),
    retry: false,
  });
  return (
    <section className="nested-secure-surface">
      <div className="secure-surface-heading"><div className="secure-icon"><ShieldCheck size={22} /></div><div><p className="eyebrow">Owner activation</p><h2>TikTok connection handoff</h2><p>Opening this page never creates an intent or contacts TikTok.</p></div></div>
      {query.isPending ? <div aria-label="Checking secure launch" className="dashboard-skeleton secure-skeleton" /> : query.isError || !query.data ? <div className="secure-denied" role="alert"><LockKeyhole size={22} /><div><strong>Fresh owner launch required</strong><p>Return to Accumulate and open the signed TikTok owner activation link for this exact Brand.</p></div><a className="secondary-button" href="https://app.theaccumulate.com">Back to Accumulate</a></div> : <div className="handoff-summary"><div className="handoff-ready"><CheckCircle2 size={19} /><span>Signed handoff verified</span></div><dl><div><dt>Brand</dt><dd>{query.data.brand_id}</dd></div><div><dt>Connection</dt><dd>{query.data.connection_state.replaceAll("_", " ")}</dd></div><div><dt>Fresh until</dt><dd>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(query.data.fresh_until))}</dd></div><div><dt>Runtime</dt><dd>{query.data.runtime_mode.replaceAll("_", " ")}</dd></div></dl><form action="/api/settings/tiktok/oauth/account/start" method="post"><button className="primary-button compact-button" disabled={!query.data.oauth_start_available} title={query.data.oauth_start_available ? "Continue to TikTok authorization" : "Provider authorization remains unavailable before cutover"} type="submit">Connect TikTok</button></form><p className="operation-note">{query.data.oauth_start_available ? "Authorization begins only after this explicit action." : "Provider authorization is unavailable before cutover. No state, credential or external request was created."}</p></div>}
      <Link className="nested-back-link" to="/settings">Return to Settings</Link>
    </section>
  );
}

export function AuditPage() {
  const { selectedBrandId, rollup, capabilities } = useBrandScope();
  const query = useQuery({
    queryKey: ["settings", "audit", selectedBrandId, rollup],
    queryFn: ({ signal }) => apiQuery(
      `/api/settings/audit${queryString({ brand_id: selectedBrandId, rollup })}`,
      auditSchema,
      signal,
    ),
  });
  const mutationAvailable = capabilities?.permissions.operation_mutation_available ?? false;
  return (
    <section className="nested-secure-surface">
      <div className="secure-surface-heading"><div className="secure-icon"><ShieldCheck size={22} /></div><div><p className="eyebrow">Internal</p><h2>Audit and manual repair</h2><p>This surface is visible only through the backend internal-audit capability.</p></div></div>
      {query.isPending ? <div aria-label="Loading audit" className="dashboard-skeleton secure-skeleton" /> : query.isError || !query.data ? <div className="secure-denied" role="alert"><AlertTriangle size={22} /><div><strong>Audit could not be loaded</strong><p>No operational action is available.</p></div></div> : <div className="audit-summary"><dl><div><dt>Status</dt><dd>{query.data.status.replaceAll("_", " ")}</dd></div><div><dt>Reason</dt><dd>{query.data.reason.replaceAll("_", " ")}</dd></div><div><dt>Records</dt><dd>{query.data.items.length}</dd></div></dl><button className="secondary-button" disabled={!mutationAvailable} title="Manual repair is unavailable in this runtime" type="button">Manual repair</button>{!mutationAvailable && <p className="operation-note">Manual repair is unavailable while backend writes are disabled.</p>}</div>}
      <Link className="nested-back-link" to="/settings">Return to Settings</Link>
    </section>
  );
}
