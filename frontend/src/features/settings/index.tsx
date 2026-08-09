import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, LockKeyhole, ShieldCheck, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, Outlet, useLocation } from "../../routing";

import { apiQuery, auditSchema, queryString, tiktokActivationReadinessSchema } from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";
import { SetupDrawer } from "./SetupDrawer";
import { useSettingsData } from "./useSettingsData";

function displayDate(value: string | null): string {
  if (!value) return "-";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export default function SettingsPage() {
  const location = useLocation();
  const nested = location.pathname !== "/settings";
  const [setupOpen, setSetupOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [pendingBrandId, setPendingBrandId] = useState("");
  const { capabilities } = useBrandScope();
  const data = useSettingsData();
  const mutationAvailable = capabilities?.permissions.operation_mutation_available ?? false;
  const brands = data.brands.data?.items ?? [];
  const accounts = data.accounts.data?.items ?? [];
  const links = data.links.data?.items ?? [];
  const jobs = data.jobs.data?.items ?? [];
  const tiktokVisible = capabilities?.platforms.find((item) => item.platform === "tiktok")?.navigation_available === true;
  const auditVisible = capabilities?.permissions.internal_audit_visible === true;
  const brandStatus = (brand: (typeof brands)[number]) => brand.linked_account_count === 0
    ? "Attention"
    : brand.last_sync_at ? "Ready" : "Preparing";
  const visibleBrands = useMemo(() => brands.filter((brand) => {
    const matchesSearch = `${brand.name ?? ""} ${brand.brand_id}`.toLowerCase().includes(search.trim().toLowerCase());
    return matchesSearch && (filter === "all" || brandStatus(brand).toLowerCase() === filter);
  }), [brands, filter, search]);
  const loading = data.brands.isPending || data.accounts.isPending || data.jobs.isPending;
  const failed = data.brands.isError || data.accounts.isError || data.jobs.isError;

  return (
    <main className="canonical-settings shell">
      <section className="hero-panel">
        <div className="hero-copy">
          <div className="eyebrow">Settings</div>
          <h1>Social media setup</h1>
          <p>Brands, linked accounts, backfill and nightly sync in one table.</p>
        </div>
        <div className="top-nav">
          {tiktokVisible && <Link to="/tiktok">TikTok</Link>}
          <Link to="/facebook">Facebook</Link>
          <Link to="/instagram">Instagram</Link>
          {auditVisible && <Link className="action-button" to="/settings/audit">Audit</Link>}
        </div>
      </section>

      {failed && <div className="error-strip" role="alert">Settings records could not be loaded.</div>}
      {data.completionMessage && <div className="success-strip" role="status"><CheckCircle2 size={18} /><span>{data.completionMessage}</span><button aria-label="Dismiss" onClick={data.dismissCompletion} type="button"><X size={16} /></button></div>}

      <section className="surface settings-toolbar">
        <input className="search-input" onChange={(event) => setSearch(event.target.value)} placeholder="Search brands" value={search} />
        <select aria-label="Brand status" className="toolbar-select" onChange={(event) => setFilter(event.target.value)} value={filter}>
          <option value="all">All</option><option value="ready">Ready</option><option value="preparing">Preparing</option><option value="attention">Attention</option>
        </select>
        <select aria-label="Select brand" className="toolbar-select" onChange={(event) => setPendingBrandId(event.target.value)} value={pendingBrandId}>
          <option value="">Select brand</option>
          {brands.map((brand) => <option key={brand.brand_id} value={brand.brand_id}>{brand.name ?? `Brand ${brand.brand_id}`}</option>)}
        </select>
        <button className="action-button" disabled={!pendingBrandId || !mutationAvailable} title={mutationAvailable ? "Add selected Brand" : "Brand authority is managed by Accumulate"} type="button">Add brand</button>
      </section>

      <section className="surface table-surface">
        <div className="settings-table-scroll"><table className="settings-table"><thead><tr><th>Brand</th><th>Meta Access</th><th>Discovery</th><th>Accounts</th><th>Data</th><th>Backfill</th><th>Collector</th><th>Last Sync</th><th>Nightly</th><th>Action</th></tr></thead><tbody>
          {visibleBrands.map((brand) => {
            const brandAccounts = accounts.filter((account) => account.brand_id === brand.brand_id);
            const backfills = brandAccounts.map((account) => account.backfill_status);
            const backfill = backfills.length === 0 ? "Not started" : backfills.every((status) => status === "complete") ? "Complete" : backfills.some((status) => status === "failed") ? "Attention" : "Preparing";
            const nightly = brandAccounts.some((account) => account.nightly_enabled);
            const metaAccess = brandAccounts.some((account) => account.platform === "facebook" || account.platform === "instagram") ? "Connected" : "Not connected";
            const status = brandStatus(brand);
            return <tr key={brand.brand_id}><td><div className="table-primary">{brand.name ?? `Brand ${brand.brand_id}`}</div><div className="table-secondary">{brand.parent_brand_id ? "Child Brand" : "Parent Brand"}</div></td><td>{metaAccess}</td><td>{brandAccounts.length > 0 ? "Complete" : "Pending"}</td><td>{brand.linked_account_count}</td><td><span className={`pill ${status === "Ready" ? "pill-live" : status === "Attention" ? "pill-alert" : "pill-ink"}`}>{status}</span></td><td>{backfill}</td><td>{nightly ? "Active" : "Dormant"}</td><td>{displayDate(brand.last_sync_at)}</td><td>{nightly ? "On" : "Off"}</td><td><button className="action-button action-button-small" onClick={() => setSetupOpen(true)} type="button">Setup</button></td></tr>;
          })}
          {loading && <tr><td className="table-empty" colSpan={10}>Loading brands</td></tr>}
          {!loading && visibleBrands.length === 0 && <tr><td className="table-empty" colSpan={10}>No brands in this view</td></tr>}
        </tbody></table></div>
      </section>
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
      {query.isPending ? <div aria-label="Checking secure launch" className="dashboard-skeleton secure-skeleton" /> : query.isError || !query.data ? <div className="secure-denied" role="alert"><LockKeyhole size={22} /><div><strong>Fresh owner launch required</strong><p>Return to Accumulate and open the signed TikTok owner activation link for this exact Brand.</p></div><a className="secondary-button" href="https://app.theaccumulate.com">Back to Accumulate</a></div> : <div className="handoff-summary"><div className="handoff-ready"><CheckCircle2 size={19} /><span>Signed handoff verified</span></div><dl><div><dt>Brand</dt><dd>{query.data.brand_id}</dd></div><div><dt>Connection</dt><dd>{query.data.connection_state.replaceAll("_", " ")}</dd></div><div><dt>Fresh until</dt><dd>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(query.data.fresh_until))}</dd></div><div><dt>Runtime</dt><dd>{query.data.runtime_mode.replaceAll("_", " ")}</dd></div></dl><form action="/api/settings/tiktok/oauth/account/start" method="post"><button className="primary-button compact-button" disabled={!query.data.oauth_start_available} title={query.data.oauth_start_available ? "Continue to TikTok authorization" : "Provider authorization is disabled by the runtime policy"} type="submit">Connect TikTok</button></form><p className="operation-note">{query.data.oauth_start_available ? "Authorization begins only after this explicit action." : "Provider authorization is disabled by the runtime policy. No state, credential or external request was created."}</p></div>}
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
