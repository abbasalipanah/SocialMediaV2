import { ArrowDown, ArrowUp, ChevronsUpDown, Eye, MoreHorizontal, Play, Search } from "lucide-react";
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
  totalCount,
  statusFilter,
  statusOptions,
  onStatusFilter,
  secondaryFilter,
  secondaryOptions,
  secondaryLabel,
  onSecondaryFilter,
  navigation,
  children,
}: {
  search: string;
  onSearch: (value: string) => void;
  count: number;
  totalCount: number;
  statusFilter: string;
  statusOptions: string[];
  onStatusFilter: (value: string) => void;
  secondaryFilter: string;
  secondaryOptions: Array<{ label: string; value: string }>;
  secondaryLabel: string;
  onSecondaryFilter: (value: string) => void;
  navigation: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="settings-table-card">
      <div className="table-toolbar performance-table-toolbar">
        <div aria-label="Settings views" className="settings-tabs" role="tablist">{navigation}</div>
        <div className="settings-table-controls">
          <span className="result-count">Showing <strong>{count}</strong> of {totalCount}</span>
          <label className="settings-search"><Search size={16} /><span className="sr-only">Search</span><input onChange={(event) => onSearch(event.target.value)} placeholder="Search by name or ID" value={search} /></label>
          <label className="settings-filter"><span className="sr-only">Status filter</span><select onChange={(event) => onStatusFilter(event.target.value)} value={statusFilter}>{statusOptions.map((option) => <option key={option} value={option}>{option === "All" ? "Status: All" : humanize(option)}</option>)}</select></label>
          <label className="settings-filter"><span className="sr-only">{secondaryLabel} filter</span><select onChange={(event) => onSecondaryFilter(event.target.value)} value={secondaryFilter}>{secondaryOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
        </div>
      </div>
      <div className="table-scroll">{children}</div>
    </section>
  );
}

const PLATFORM_FILTER_OPTIONS: Array<{ label: string; value: string }> = [
  { label: "Platform: All", value: "all" },
  { label: "Facebook", value: "facebook" },
  { label: "Instagram", value: "instagram" },
  { label: "TikTok", value: "tiktok" },
];

function brandStatus(item: SettingsBrand): string {
  if (item.linked_account_count === 0) return "Missing Accounts";
  return item.last_sync_at ? "Ready" : "Pending Setup";
}

function EmptyRow({ columns }: { columns: number }) {
  return <tr><td className="table-empty" colSpan={columns}>No matching records.</td></tr>;
}

export function BrandsTable({ items, navigation, onSetup }: { items: SettingsBrand[]; navigation: ReactNode; onSetup: () => void }) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [hierarchyFilter, setHierarchyFilter] = useState("all");
  const [sort, setSort] = useState<"accounts" | "name">("name");
  const [direction, setDirection] = useState<SortDirection>("asc");
  const rows = useMemo(() => items
    .filter((item) => statusFilter === "All" || brandStatus(item) === statusFilter)
    .filter((item) => hierarchyFilter === "all" || (hierarchyFilter === "parent" ? !item.parent_brand_id : Boolean(item.parent_brand_id)))
    .filter((item) => `${item.name ?? ""} ${item.brand_id}`.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      const compared = sort === "accounts"
        ? a.linked_account_count - b.linked_account_count
        : (a.name ?? a.brand_id).localeCompare(b.name ?? b.brand_id);
      return direction === "asc" ? compared : -compared;
    }), [direction, hierarchyFilter, items, search, sort, statusFilter]);
  const statusOptions = ["All", ...Array.from(new Set(items.map(brandStatus)))];
  const chooseSort = (next: typeof sort) => {
    if (sort === next) setDirection((current) => current === "asc" ? "desc" : "asc");
    else { setSort(next); setDirection("asc"); }
  };
  return (
    <TableFrame count={rows.length} navigation={navigation} onSearch={setSearch} onSecondaryFilter={setHierarchyFilter} onStatusFilter={setStatusFilter} search={search} secondaryFilter={hierarchyFilter} secondaryLabel="Hierarchy" secondaryOptions={[{ label: "Hierarchy: All", value: "all" }, { label: "Parent Brands", value: "parent" }, { label: "Child Brands", value: "child" }]} statusFilter={statusFilter} statusOptions={statusOptions} totalCount={items.length}>
      <table className="settings-table performance-settings-table"><thead><tr><th>#</th><th>ID</th><th><SortButton active={sort === "name"} direction={direction} label="Brand" onClick={() => chooseSort("name")} /></th><th>Status</th><th>Access</th><th><SortButton active={sort === "accounts"} direction={direction} label="Linked" onClick={() => chooseSort("accounts")} /></th><th>Last sync</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>
        {rows.length === 0 ? <EmptyRow columns={8} /> : rows.map((item, index) => <tr key={item.brand_id}><td>{index + 1}</td><td><span className="muted-cell">{item.brand_id}</span></td><td><div className={item.parent_brand_id ? "hierarchy-name child" : "hierarchy-name"}><strong>{item.name ?? `Brand ${item.brand_id}`}</strong><small>{item.parent_brand_id ? "Child Brand" : "Parent Brand"}</small></div></td><td><StatusPill value={brandStatus(item)} /></td><td>{item.access_mode ? <StatusPill value={item.access_mode} /> : <span className="muted-cell">Inherited</span>}</td><td><strong>{item.linked_account_count}</strong> linked</td><td>{formatDate(item.last_sync_at)}</td><td><button className="settings-row-action" onClick={onSetup} type="button">{item.linked_account_count > 0 ? "Edit" : "Setup"}<MoreHorizontal size={15} /></button></td></tr>)}
      </tbody></table>
    </TableFrame>
  );
}

export function AccountsTable({ items, mutationAvailable, navigation }: { items: ReportingAccount[]; mutationAvailable: boolean; navigation: ReactNode }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Platform | "all">("all");
  const [statusFilter, setStatusFilter] = useState("All");
  const [selected, setSelected] = useState<ReportingAccount | null>(null);
  const rows = useMemo(() => items.filter((item) => (statusFilter === "All" || item.connection_state === statusFilter) && (filter === "all" || item.platform === filter) && `${item.display_name} ${item.external_id} ${item.brand_id}`.toLowerCase().includes(search.toLowerCase())).sort((a, b) => a.display_name.localeCompare(b.display_name)), [filter, items, search, statusFilter]);
  const statusOptions = ["All", ...Array.from(new Set(items.map((item) => item.connection_state)))];
  return (
    <>
      <TableFrame count={rows.length} navigation={navigation} onSearch={setSearch} onSecondaryFilter={(value) => setFilter(value as Platform | "all")} onStatusFilter={setStatusFilter} search={search} secondaryFilter={filter} secondaryLabel="Platform" secondaryOptions={PLATFORM_FILTER_OPTIONS} statusFilter={statusFilter} statusOptions={statusOptions} totalCount={items.length}>
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

export function LinksTable({ items, navigation }: { items: BrandLink[]; navigation: ReactNode }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Platform | "all">("all");
  const [statusFilter, setStatusFilter] = useState("All");
  const [selected, setSelected] = useState<BrandLink | null>(null);
  const rows = useMemo(() => items.filter((item) => (statusFilter === "All" || item.link_status === statusFilter) && (filter === "all" || item.platform === filter) && `${item.display_name} ${item.external_id} ${item.brand_id}`.toLowerCase().includes(search.toLowerCase())).sort((a, b) => a.brand_id.localeCompare(b.brand_id)), [filter, items, search, statusFilter]);
  const statusOptions = ["All", ...Array.from(new Set(items.map((item) => item.link_status)))];
  return <><TableFrame count={rows.length} navigation={navigation} onSearch={setSearch} onSecondaryFilter={(value) => setFilter(value as Platform | "all")} onStatusFilter={setStatusFilter} search={search} secondaryFilter={filter} secondaryLabel="Platform" secondaryOptions={PLATFORM_FILTER_OPTIONS} statusFilter={statusFilter} statusOptions={statusOptions} totalCount={items.length}><table className="settings-table"><thead><tr><th>Brand</th><th>Social account</th><th>Platform</th><th>External ID</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{rows.length === 0 ? <EmptyRow columns={6} /> : rows.map((item) => <tr key={`${item.brand_id}-${item.account_id}`}><td><strong>{item.brand_id}</strong></td><td>{item.display_name}</td><td>{PLATFORM_LABELS[item.platform]}</td><td>{item.external_id}</td><td><StatusPill value={item.link_status} /></td><td><button aria-label={`Review link for ${item.display_name}`} className="icon-button" onClick={() => setSelected(item)} type="button"><Eye size={16} /></button></td></tr>)}</tbody></table></TableFrame><Dialog description="Review the projected Brand-to-account mapping." onClose={() => setSelected(null)} open={selected !== null} title="Brand link"><div className="dialog-body account-review"><dl><div><dt>Brand</dt><dd>{selected?.brand_id}</dd></div><div><dt>Social account</dt><dd>{selected?.display_name}</dd></div><div><dt>Platform</dt><dd>{selected ? PLATFORM_LABELS[selected.platform] : ""}</dd></div><div><dt>External ID</dt><dd>{selected?.external_id}</dd></div><div><dt>Status</dt><dd>{selected && <StatusPill value={selected.link_status} />}</dd></div></dl><div className="dialog-actions"><button className="secondary-button" onClick={() => setSelected(null)} type="button">Close</button></div></div></Dialog></>;
}

export function SyncTable({ items, mutationAvailable, navigation }: { items: ReportingSyncJob[]; mutationAvailable: boolean; navigation: ReactNode }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Platform | "all">("all");
  const [statusFilter, setStatusFilter] = useState("All");
  const rows = useMemo(() => items.filter((item) => (statusFilter === "All" || item.status === statusFilter) && (filter === "all" || item.platform === filter) && `${item.job_id} ${item.stage} ${item.status} ${item.brand_id}`.toLowerCase().includes(search.toLowerCase())).sort((a, b) => b.scheduled_for.localeCompare(a.scheduled_for)), [filter, items, search, statusFilter]);
  const statusOptions = ["All", ...Array.from(new Set(items.map((item) => item.status)))];
  return <TableFrame count={rows.length} navigation={navigation} onSearch={setSearch} onSecondaryFilter={(value) => setFilter(value as Platform | "all")} onStatusFilter={setStatusFilter} search={search} secondaryFilter={filter} secondaryLabel="Platform" secondaryOptions={PLATFORM_FILTER_OPTIONS} statusFilter={statusFilter} statusOptions={statusOptions} totalCount={items.length}><table className="settings-table"><thead><tr><th>Job</th><th>Platform</th><th>Stage</th><th>Status</th><th>Scheduled</th><th>Finished</th><th>Failure</th></tr></thead><tbody>{rows.length === 0 ? <EmptyRow columns={7} /> : rows.map((item) => <tr key={item.job_id}><td><strong>#{item.job_id}</strong><small className="cell-subtitle">Brand {item.brand_id}</small></td><td>{PLATFORM_LABELS[item.platform]}</td><td>{humanize(item.stage)}</td><td><StatusPill value={item.status} /></td><td>{formatDate(item.scheduled_for)}</td><td>{item.finished_at ? formatDate(item.finished_at) : "—"}</td><td>{item.error_code ? humanize(item.error_code) : "—"}</td></tr>)}</tbody></table>{!mutationAvailable && <p className="table-footnote">Sync and backfill commands remain unavailable while backend writes are disabled. Existing jobs are read-only.</p>}</TableFrame>;
}

export function SettingsTableLoading() {
  return <div aria-label="Loading settings records" className="settings-table-card table-loading"><div className="dashboard-skeleton" /><div className="dashboard-skeleton" /><div className="dashboard-skeleton" /></div>;
}

export function SettingsTableError({ retry }: { retry: () => void }) {
  return <section className="settings-inline-error" role="alert"><p>Settings records could not be loaded.</p><button className="secondary-button" onClick={retry} type="button">Retry</button></section>;
}
