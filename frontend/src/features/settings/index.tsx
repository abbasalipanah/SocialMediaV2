import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Link2,
  ListChecks,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import { useState } from "react";
import { Link, Outlet, useLocation } from "../../routing";

import type { SettingsBrand } from "../../api";
import { apiQuery, auditSchema, queryString, tiktokActivationReadinessSchema } from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";
import { SetupDrawer } from "./SetupDrawer";
import {
  AccountsTable,
  BrandsTable,
  LinksTable,
  SettingsTableError,
  SettingsTableLoading,
  SyncTable,
  type SettingsView,
} from "./SettingsTables";
import { useSettingsData } from "./useSettingsData";

export default function SettingsPage() {
  const location = useLocation();
  const nested = location.pathname !== "/settings";
  // The Brand whose row was clicked. Opening setup from a row and then
  // showing the session's Brand meant every row opened the same one.
  const [setupBrand, setSetupBrand] = useState<SettingsBrand | null>(null);
  const [view, setView] = useState<SettingsView>("brands");
  const { capabilities } = useBrandScope();
  const data = useSettingsData();
  const mutationAvailable = capabilities?.permissions.operation_mutation_available ?? false;
  const brands = data.brands.data?.items ?? [];
  const accounts = data.accounts.data?.items ?? [];
  const links = data.links.data?.items ?? [];
  const jobs = data.jobs.data?.items ?? [];
  const readyBrands = brands.filter((item) => item.linked_account_count > 0 && item.last_sync_at).length;
  const pendingBrands = brands.filter((item) => item.linked_account_count > 0 && !item.last_sync_at).length;
  const missingAccounts = brands.filter((item) => item.linked_account_count === 0).length;
  const connectedAccounts = accounts.filter((item) => item.connection_state === "connected").length;
  const activeJobs = jobs.filter((item) => ["pending", "running"].includes(item.status)).length;
  const failedJobs = jobs.filter((item) => item.status === "failed").length;
  const refreshing = [
    data.brands,
    data.accounts,
    data.links,
    data.connections,
    data.jobs,
    data.readiness,
  ].some((query) => query.isFetching);

  const tabs = (
    <>
      {([
        ["brands", "Brands"],
        ["accounts", "Platform Accounts"],
        ["links", "Mappings"],
        ["sync", "Sync & Backfill"],
      ] as Array<[SettingsView, string]>).map(([id, label]) => (
        <button
          aria-selected={view === id}
          className={view === id ? "active" : ""}
          key={id}
          onClick={() => setView(id)}
          role="tab"
          type="button"
        >
          {label}
        </button>
      ))}
    </>
  );

  const viewLoading = view === "brands"
    ? data.brands.isPending
    : view === "accounts"
      ? data.accounts.isPending
      : view === "links"
        ? data.links.isPending
        : data.jobs.isPending;
  const viewError = view === "brands"
    ? data.brands.isError
    : view === "accounts"
      ? data.accounts.isError
      : view === "links"
        ? data.links.isError
        : data.jobs.isError;
  const retryView = () => {
    if (view === "brands") void data.brands.refetch();
    else if (view === "accounts") void data.accounts.refetch();
    else if (view === "links") void data.links.refetch();
    else void data.jobs.refetch();
  };
  const refreshPlatform = async () => {
    await Promise.all([
      data.brands.refetch(),
      data.accounts.refetch(),
      data.links.refetch(),
      data.connections.refetch(),
      data.jobs.refetch(),
      data.readiness.refetch(),
    ]);
  };

  return (
    <main className="page-shell settings-page">
      <header className="performance-settings-header">
        <div>
          <p className="eyebrow">Settings</p>
          <h1>Brand Setup and Account Mapping</h1>
          <p>Manage Brand readiness, social accounts, mappings and collection status in one table-first workspace.</p>
        </div>
        <div className="settings-header-actions">
          <button className="settings-action-button" onClick={() => setView("links")} type="button"><Link2 size={16} />Linked brands</button>
          <button className="settings-action-button" onClick={() => setView("sync")} type="button"><ListChecks size={16} />Manual sync</button>
          <button className="settings-action-button emphasized" disabled={refreshing} onClick={() => void refreshPlatform()} type="button"><RefreshCw className={refreshing ? "spin" : ""} size={16} />{refreshing ? "Refreshing" : "Refresh Platform"}</button>
        </div>
      </header>

      {data.completionMessage && <div className="success-strip" role="status"><CheckCircle2 size={18} /><span>{data.completionMessage}</span><button aria-label="Dismiss" onClick={data.dismissCompletion} type="button"><X size={16} /></button></div>}

      <section aria-label="Settings summary" className="settings-summary-grid">
        <article className="tone-indigo"><span>Current Brands</span><strong>{brands.length}</strong></article>
        <article className="tone-emerald"><span>Ready</span><strong>{readyBrands}</strong></article>
        <article className="tone-amber"><span>Pending Setup</span><strong>{pendingBrands}</strong></article>
        <article className="tone-rose"><span>Missing Accounts</span><strong>{missingAccounts}</strong></article>
        <article className="tone-sky"><span>Connected Accounts</span><strong>{connectedAccounts}</strong></article>
        <article><span>{failedJobs ? "Failed Jobs" : "Active Jobs"}</span><strong>{failedJobs || activeJobs}</strong></article>
      </section>

      {viewLoading ? <SettingsTableLoading /> : viewError ? <SettingsTableError retry={retryView} /> : view === "brands" ? <BrandsTable items={brands} navigation={tabs} onSetup={setSetupBrand} /> : view === "accounts" ? <AccountsTable items={accounts} mutationAvailable={mutationAvailable} navigation={tabs} /> : view === "links" ? <LinksTable items={links} navigation={tabs} /> : <SyncTable items={jobs} mutationAvailable={mutationAvailable} navigation={tabs} />}
      {nested && <Outlet />}
      <SetupDrawer
        accounts={data.accounts.data?.items ?? []}
        brand={setupBrand}
        connections={data.connections.data?.items ?? []}
        jobs={data.jobs.data?.items ?? []}
        mutationAvailable={mutationAvailable}
        onClose={() => setSetupBrand(null)}
        open={setupBrand !== null}
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
      {query.isPending ? <div aria-label="Checking secure launch" className="dashboard-skeleton secure-skeleton" /> : query.isError || !query.data ? <div className="secure-denied" role="alert"><LockKeyhole size={22} /><div><strong>Fresh owner launch required</strong><p>Return to Accumulate and open the signed TikTok owner activation link for this exact Brand.</p></div><a className="secondary-button" href="https://app.theaccumulate.com">Back to Accumulate AI</a></div> : <div className="handoff-summary"><div className="handoff-ready"><CheckCircle2 size={19} /><span>Signed handoff verified</span></div><dl><div><dt>Brand</dt><dd>{query.data.brand_id}</dd></div><div><dt>Connection</dt><dd>{query.data.connection_state.replaceAll("_", " ")}</dd></div><div><dt>Fresh until</dt><dd>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(query.data.fresh_until))}</dd></div><div><dt>Runtime</dt><dd>{query.data.runtime_mode.replaceAll("_", " ")}</dd></div></dl><form action="/api/settings/tiktok/oauth/account/start" method="post"><button className="primary-button compact-button" disabled={!query.data.oauth_start_available} title={query.data.oauth_start_available ? "Continue to TikTok authorization" : "Provider authorization is disabled by the runtime policy"} type="submit">Connect TikTok</button></form><p className="operation-note">{query.data.oauth_start_available ? "Authorization begins only after this explicit action." : "Provider authorization is disabled by the runtime policy. No state, credential or external request was created."}</p></div>}
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
