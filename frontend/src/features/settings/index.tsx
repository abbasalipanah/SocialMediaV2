import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ClipboardCheck, Layers3, LockKeyhole, Settings2, Share2, ShieldCheck, UsersRound, X } from "lucide-react";
import { useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";

import { apiQuery, auditSchema, queryString, tiktokActivationReadinessSchema } from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";
import { AccountsTable, BrandsTable, LinksTable, SettingsTableError, SettingsTableLoading, SyncTable, type SettingsView } from "./SettingsTables";
import { SetupDrawer } from "./SetupDrawer";
import { useSettingsData } from "./useSettingsData";

const VIEWS: Array<{ id: SettingsView; label: string; icon: typeof Layers3 }> = [
  { id: "brands", label: "Brands", icon: Layers3 },
  { id: "accounts", label: "Social Accounts", icon: UsersRound },
  { id: "links", label: "Brand Links", icon: Share2 },
  { id: "sync", label: "Sync & Backfill", icon: ClipboardCheck },
];

export default function SettingsPage() {
  const location = useLocation();
  const nested = location.pathname !== "/settings";
  const [view, setView] = useState<SettingsView>("brands");
  const [setupOpen, setSetupOpen] = useState(false);
  const { capabilities, selectedBrand } = useBrandScope();
  const data = useSettingsData();
  const mutationAvailable = capabilities?.permissions.operation_mutation_available ?? false;

  const selectedQuery = view === "brands" ? data.brands : view === "accounts" ? data.accounts : view === "links" ? data.links : data.jobs;
  const table = selectedQuery.isPending
    ? <SettingsTableLoading />
    : selectedQuery.isError || !selectedQuery.data
      ? <SettingsTableError retry={() => void selectedQuery.refetch()} />
      : view === "brands"
        ? <BrandsTable items={data.brands.data?.items ?? []} />
        : view === "accounts"
          ? <AccountsTable items={data.accounts.data?.items ?? []} mutationAvailable={mutationAvailable} />
          : view === "links"
            ? <LinksTable items={data.links.data?.items ?? []} />
            : <SyncTable items={data.jobs.data?.items ?? []} mutationAvailable={mutationAvailable} />;

  return (
    <main className="page-shell settings-page">
      <header className="settings-header"><div><p className="eyebrow">Social Media</p><h1>Settings</h1><p>Manage reporting visibility for {selectedBrand?.name ?? "the selected Brand"}.</p></div><button className="primary-button compact-button" onClick={() => setSetupOpen(true)} type="button"><Settings2 size={17} /> Brand Setup</button></header>
      {data.completionMessage && <div className="settings-toast" role="status"><CheckCircle2 size={18} /><span>{data.completionMessage}</span><button aria-label="Dismiss" onClick={data.dismissCompletion} type="button"><X size={16} /></button></div>}
      <div aria-label="Settings views" className="settings-tabs" role="tablist">{VIEWS.map(({ id, label, icon: Icon }) => <button aria-selected={view === id} className={view === id ? "active" : ""} key={id} onClick={() => setView(id)} role="tab" type="button"><Icon size={17} />{label}</button>)}</div>
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
      {query.isPending ? <div aria-label="Checking secure launch" className="dashboard-skeleton secure-skeleton" /> : query.isError || !query.data ? <div className="secure-denied" role="alert"><LockKeyhole size={22} /><div><strong>Fresh owner launch required</strong><p>Return to Accumulate and open the signed TikTok owner activation link for this exact Brand.</p></div><a className="secondary-button" href="https://app.theaccumulate.com">Back to Accumulate</a></div> : <div className="handoff-summary"><div className="handoff-ready"><CheckCircle2 size={19} /><span>Signed handoff verified</span></div><dl><div><dt>Brand</dt><dd>{query.data.brand_id}</dd></div><div><dt>Connection</dt><dd>{query.data.connection_state.replaceAll("_", " ")}</dd></div><div><dt>Fresh until</dt><dd>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(query.data.fresh_until))}</dd></div><div><dt>Runtime</dt><dd>{query.data.runtime_mode.replaceAll("_", " ")}</dd></div></dl><button className="primary-button compact-button" disabled={!query.data.oauth_start_available} title="Provider authorization remains unavailable before cutover" type="button">Connect TikTok</button><p className="operation-note">Provider authorization is unavailable before cutover. No state, credential or external request was created.</p></div>}
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
