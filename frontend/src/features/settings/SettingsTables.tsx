import { ArrowDown, ArrowUp, ChevronsUpDown, Eye, Play, Search } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import type {
  BrandLink,
  Platform,
  ReportingAccount,
  ReportingSyncJob,
  SettingsBrand,
} from "../../api";
import { Dialog } from "../../ui";
import { PLATFORM_LABELS } from "../dashboard/catalog";
import { formatDate, humanize } from "../dashboard/format";

export type SettingsView = "accounts" | "brands" | "links" | "sync";
type SortDirection = "asc" | "desc";

function StatusPill({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const tone = ["active", "available", "complete", "completed", "connected", "healthy", "ready"].includes(normalized)
    ? "success"
    : ["error", "failed", "revoked"].includes(normalized)
      ? "danger"
      : ["pending", "running", "partial"].includes(normalized)
        ? "warning"
        : "neutral";
  return <span className={`settings-pill pill-${tone}`}>{humanize(value)}</span>;
}

function SortButton({ label, active, direction, onClick }: { label: string; active: boolean; direction: SortDirection; onClick: () => void }) {
  return <button className="table-sort" onClick={onClick} type="button">{label}{active ? (direction === "asc" ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ChevronsUpDown size={13} />}</button>;
}

function TableFrame({
  search,
  onSearch,
  count,
  filter,
  onFilter,
  children,
}: {
  search: string;
  onSearch: (value: string) => void;
  count: number;
  filter?: Platform | "all";
  onFilter?: (value: Platform | "all") => void;
  children: ReactNode;
}) {
  return (
    <section className="settings-table-card">
      <div className="table-toolbar">
        <label className="settings-search"><Search size={16} /><span className="sr-only">Search</span><input onChange={(event) => onSearch(event.target.value)} placeholder="Search this view" value={search} /></label>
        {filter && onFilter && (
          <label className="settings-filter"><span className="sr-only">Platform filter</span><select onChange={(event) => onFilter(event.target.value as Platform | "all")} value={filter}><option value="all">All platforms</option><option value="facebook">Facebook</option><option value="instagram">Instagram</option><option value="tiktok">TikTok</option></select></label>
        )}
        <span className="result-count">{count} result{count === 1 ? "" : "s"}</span>
      </div>
      <div className="table-scroll">{children}</div>
    </section>
  );
}

function EmptyRow({ columns }: { columns: number }) {
  return <tr><td className="table-empty" colSpan={columns}>No matching records.</td></tr>;
}

export function BrandsTable({ items }: { items: SettingsBrand[] }) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"accounts" | "name">("name");
  const [direction, setDirection] = useState<SortDirection>("asc");
  const rows = useMemo(() => items
    .filter((item) => `${item.name ?? ""} ${item.brand_id}`.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      const compared = sort === "accounts"
        ? a.linked_account_count - b.linked_account_count
        : (a.name ?? a.brand_id).localeCompare(b.name ?? b.brand_id);
      return direction === "asc" ? compared : -compared;
    }), [direction, items, search, sort]);
  const chooseSort = (next: typeof sort) => {
    if (sort === next) setDirection((current) => current === "asc" ? "desc" : "asc");
    else { setSort(next); setDirection("asc"); }
  };
  return (
    <TableFrame count={rows.length} onSearch={setSearch} search={search}>
      <table className="settings-table"><thead><tr><th><SortButton active={sort === "name"} direction={direction} label="Brand" onClick={() => chooseSort("name")} /></th><th>Hierarchy</th><th>Access</th><th><SortButton active={sort === "accounts"} direction={direction} label="Linked accounts" onClick={() => chooseSort("accounts")} /></th><th>Last sync</th></tr></thead><tbody>
        {rows.length === 0 ? <EmptyRow columns={5} /> : rows.map((item) => <tr key={item.brand_id}><td><div className={item.parent_brand_id ? "hierarchy-name child" : "hierarchy-name"}><strong>{item.name ?? `Brand ${item.brand_id}`}</strong><small>{item.brand_id}</small></div></td><td><StatusPill value={item.parent_brand_id ? "Child Brand" : "Parent Brand"} /></td><td>{item.access_mode ? <StatusPill value={item.access_mode} /> : <span className="muted-cell">Inherited</span>}</td><td>{item.linked_account_count}</td><td>{formatDate(item.last_sync_at)}</td></tr>)}
      </tbody></table>
    </TableFrame>
  );
}

export function AccountsTable({ items, mutationAvailable }: { items: ReportingAccount[]; mutationAvailable: boolean }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Platform | "all">("all");
  const [selected, setSelected] = useState<ReportingAccount | null>(null);
  const rows = useMemo(() => items.filter((item) => (filter === "all" || item.platform === filter) && `${item.display_name} ${item.external_id} ${item.brand_id}`.toLowerCase().includes(search.toLowerCase())).sort((a, b) => a.display_name.localeCompare(b.display_name)), [filter, items, search]);
  return (
    <>
      <TableFrame count={rows.length} filter={filter} onFilter={setFilter} onSearch={setSearch} search={search}>
        <table className="settings-table"><thead><tr><th>Social account</th><th>Platform</th><th>Connection</th><th>Health</th><th>Backfill</th><th>Last sync</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>
          {rows.length === 0 ? <EmptyRow columns={7} /> : rows.map((item) => <tr key={item.account_id}><td><strong>{item.display_name}</strong><small className="cell-subtitle">{item.external_id}</small></td><td>{PLATFORM_LABELS[item.platform]}</td><td><StatusPill value={item.connection_state} /></td><td><StatusPill value={item.health_status} /></td><td><StatusPill value={item.backfill_status} /></td><td>{formatDate(item.last_synced_at)}</td><td><button aria-label={`Review ${item.display_name}`} className="icon-button" onClick={() => setSelected(item)} type="button"><Eye size={16} /></button></td></tr>)}
        </tbody></table>
      </TableFrame>
      <Dialog description="Review account state and manual operation availability." onClose={() => setSelected(null)} open={selected !== null} title={selected?.display_name ?? "Social account"}>
        {selected && <div className="dialog-body account-review"><dl><div><dt>Platform</dt><dd>{PLATFORM_LABELS[selected.platform]}</dd></div><div><dt>External ID</dt><dd>{selected.external_id}</dd></div><div><dt>Connection</dt><dd><StatusPill value={selected.connection_state} /></dd></div><div><dt>Nightly sync</dt><dd>{selected.nightly_enabled ? "Enabled" : "Disabled"}</dd></div></dl><div className="dialog-actions"><button className="secondary-button" onClick={() => setSelected(null)} type="button">Close</button><button className="primary-button compact-button" disabled={!mutationAvailable} title={mutationAvailable ? "Queue manual sync" : "Writes are unavailable in this runtime"} type="button"><Play size={16} /> Sync now</button></div>{!mutationAvailable && <p className="operation-note">Manual sync is unavailable while the backend write capability is disabled.</p>}</div>}
      </Dialog>
    </>
  );
}

export function LinksTable({ items }: { items: BrandLink[] }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Platform | "all">("all");
  const [selected, setSelected] = useState<BrandLink | null>(null);
  const rows = useMemo(() => items.filter((item) => (filter === "all" || item.platform === filter) && `${item.display_name} ${item.external_id} ${item.brand_id}`.toLowerCase().includes(search.toLowerCase())).sort((a, b) => a.brand_id.localeCompare(b.brand_id)), [filter, items, search]);
  return <><TableFrame count={rows.length} filter={filter} onFilter={setFilter} onSearch={setSearch} search={search}><table className="settings-table"><thead><tr><th>Brand</th><th>Social account</th><th>Platform</th><th>External ID</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{rows.length === 0 ? <EmptyRow columns={6} /> : rows.map((item) => <tr key={`${item.brand_id}-${item.account_id}`}><td><strong>{item.brand_id}</strong></td><td>{item.display_name}</td><td>{PLATFORM_LABELS[item.platform]}</td><td>{item.external_id}</td><td><StatusPill value={item.link_status} /></td><td><button aria-label={`Review link for ${item.display_name}`} className="icon-button" onClick={() => setSelected(item)} type="button"><Eye size={16} /></button></td></tr>)}</tbody></table></TableFrame><Dialog description="Review the projected Brand-to-account mapping." onClose={() => setSelected(null)} open={selected !== null} title="Brand link"><div className="dialog-body account-review"><dl><div><dt>Brand</dt><dd>{selected?.brand_id}</dd></div><div><dt>Social account</dt><dd>{selected?.display_name}</dd></div><div><dt>Platform</dt><dd>{selected ? PLATFORM_LABELS[selected.platform] : ""}</dd></div><div><dt>External ID</dt><dd>{selected?.external_id}</dd></div><div><dt>Status</dt><dd>{selected && <StatusPill value={selected.link_status} />}</dd></div></dl><div className="dialog-actions"><button className="secondary-button" onClick={() => setSelected(null)} type="button">Close</button></div></div></Dialog></>;
}

export function SyncTable({ items, mutationAvailable }: { items: ReportingSyncJob[]; mutationAvailable: boolean }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Platform | "all">("all");
  const rows = useMemo(() => items.filter((item) => (filter === "all" || item.platform === filter) && `${item.job_id} ${item.stage} ${item.status} ${item.brand_id}`.toLowerCase().includes(search.toLowerCase())).sort((a, b) => b.scheduled_for.localeCompare(a.scheduled_for)), [filter, items, search]);
  return <TableFrame count={rows.length} filter={filter} onFilter={setFilter} onSearch={setSearch} search={search}><table className="settings-table"><thead><tr><th>Job</th><th>Platform</th><th>Stage</th><th>Status</th><th>Scheduled</th><th>Finished</th><th>Failure</th></tr></thead><tbody>{rows.length === 0 ? <EmptyRow columns={7} /> : rows.map((item) => <tr key={item.job_id}><td><strong>#{item.job_id}</strong><small className="cell-subtitle">Brand {item.brand_id}</small></td><td>{PLATFORM_LABELS[item.platform]}</td><td>{humanize(item.stage)}</td><td><StatusPill value={item.status} /></td><td>{formatDate(item.scheduled_for)}</td><td>{item.finished_at ? formatDate(item.finished_at) : "—"}</td><td>{item.error_code ? humanize(item.error_code) : "—"}</td></tr>)}</tbody></table>{!mutationAvailable && <p className="table-footnote">Sync and backfill commands remain unavailable while backend writes are disabled. Existing jobs are read-only.</p>}</TableFrame>;
}

export function SettingsTableLoading() {
  return <div aria-label="Loading settings records" className="settings-table-card table-loading"><div className="dashboard-skeleton" /><div className="dashboard-skeleton" /><div className="dashboard-skeleton" /></div>;
}

export function SettingsTableError({ retry }: { retry: () => void }) {
  return <section className="settings-inline-error" role="alert"><p>Settings records could not be loaded.</p><button className="secondary-button" onClick={retry} type="button">Retry</button></section>;
}
