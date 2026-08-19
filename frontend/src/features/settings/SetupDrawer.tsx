import { Check, Circle, Facebook, Instagram, Radio, Settings2, Store } from "lucide-react";

import type {
  OperationsReadiness,
  Platform,
  ReportingAccount,
  ReportingConnection,
  ReportingSyncJob,
  SettingsBrand,
} from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";
import { Dialog } from "../../ui";
import { PLATFORM_LABELS } from "../dashboard/catalog";
import { formatDate, humanize } from "../dashboard/format";

const PLATFORMS: Platform[] = ["facebook", "instagram", "tiktok"];

function PlatformSymbol({ platform }: { platform: Platform }) {
  if (platform === "facebook") return <Facebook size={19} />;
  if (platform === "instagram") return <Instagram size={19} />;
  return <span className="drawer-tiktok">♪</span>;
}

function Section({
  index,
  title,
  hint,
  children,
}: {
  index: number;
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="setup-section">
      <header>
        <h4>
          {index}. {title}
        </h4>
        {hint && <p>{hint}</p>}
      </header>
      {children}
    </section>
  );
}

function BrandInformation({ brand }: { brand: SettingsBrand | null }) {
  if (!brand) {
    return <p className="setup-empty">This Brand is not in the current workspace scope.</p>;
  }
  const fields: [string, string][] = [
    ["Brand name", brand.name ?? `Brand ${brand.brand_id}`],
    ["Hierarchy", brand.parent_brand_id ? "Child Brand" : "Parent Brand"],
    ["Access", humanize(brand.access_mode ?? "read")],
    ["Last sync", formatDate(brand.last_sync_at)],
  ];
  return (
    <dl className="setup-field-grid">
      {fields.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function SocialAccounts({
  accounts,
  connections,
}: {
  accounts: ReportingAccount[];
  connections: ReportingConnection[];
}) {
  return (
    <div className="setup-platform-list">
      {PLATFORMS.map((platform) => {
        const linked = accounts.filter((item) => item.platform === platform);
        const connection = connections.find((item) => item.platform === platform);
        return (
          <article key={platform}>
            <div className={`setup-platform-icon setup-${platform}`}>
              <PlatformSymbol platform={platform} />
            </div>
            <div className="setup-platform-detail">
              <strong>{PLATFORM_LABELS[platform]}</strong>
              <span>
                {linked.length} linked
                {linked.length > 0 && ` · ${linked.map((item) => item.display_name).join(" · ")}`}
              </span>
            </div>
            <span className={linked.length > 0 ? "setup-state" : "setup-state muted"}>
              {humanize(connection?.state ?? "not connected")}
            </span>
          </article>
        );
      })}
    </div>
  );
}

function SyncSettings({
  accounts,
  jobs,
  mutationAvailable,
}: {
  accounts: ReportingAccount[];
  jobs: ReportingSyncJob[];
  mutationAvailable: boolean;
}) {
  const active = jobs.filter((item) => ["pending", "running"].includes(item.status)).length;
  return (
    <>
      <div className="setup-summary-grid">
        <article>
          <Radio size={20} />
          <span>Nightly enabled</span>
          <strong>{accounts.filter((item) => item.nightly_enabled).length}</strong>
        </article>
        <article>
          <Settings2 size={20} />
          <span>Pending or running</span>
          <strong>{active}</strong>
        </article>
      </div>
      <label className="readonly-toggle">
        <input checked={mutationAvailable} disabled readOnly type="checkbox" />
        <span>
          <strong>Manual operations</strong>
          <small>
            {mutationAvailable ? "Available for this scope" : "Disabled by backend capability"}
          </small>
        </span>
      </label>
    </>
  );
}

function Readiness({
  readiness,
  accounts,
  jobs,
}: {
  readiness: OperationsReadiness | undefined;
  accounts: ReportingAccount[];
  jobs: ReportingSyncJob[];
}) {
  const failed = jobs.filter((item) => item.status === "failed").length;
  const checks = [
    ["Backend readiness", readiness?.status === "ready", readiness?.status ?? "Unavailable"],
    [
      "Reporting database",
      readiness?.database_configured === true,
      readiness?.database_configured ? "Configured" : "Not configured",
    ],
    ["Linked social accounts", accounts.length > 0, `${accounts.length} linked`],
    ["Failed sync jobs", failed === 0, failed === 0 ? "None" : `${failed} require attention`],
  ] as const;
  return (
    <div className="readiness-list">
      {checks.map(([label, ready, detail]) => (
        <article key={label}>
          <span className={ready ? "ready" : "attention"}>
            {ready ? <Check size={17} /> : <Circle size={17} />}
          </span>
          <div>
            <strong>{label}</strong>
            <small>{detail}</small>
          </div>
        </article>
      ))}
    </div>
  );
}

export function SetupDrawer({
  open,
  onClose,
  brands,
  accounts,
  connections,
  jobs,
  readiness,
  mutationAvailable,
}: {
  open: boolean;
  onClose: () => void;
  brands: SettingsBrand[];
  accounts: ReportingAccount[];
  connections: ReportingConnection[];
  jobs: ReportingSyncJob[];
  readiness: OperationsReadiness | undefined;
  mutationAvailable: boolean;
}) {
  const { selectedBrandId } = useBrandScope();
  // The Brand this workspace is on, not the whole catalogue. The drawer used to
  // list every Brand in scope on its first step, so opening setup for one Brand
  // showed forty seven of them and said nothing about the one asked for.
  const brand = brands.find((item) => item.brand_id === selectedBrandId) ?? null;

  return (
    <Dialog
      description="Review Brand details, linked social accounts and collection readiness."
      drawer
      onClose={onClose}
      open={open}
      title="Brand Setup"
    >
      <div className="setup-page">
        <div className="setup-identity">
          <span className="setup-identity-icon">
            <Store size={21} />
          </span>
          <div>
            <strong>{brand?.name ?? "Brand Setup"}</strong>
            <span>
              Linking is managed by Accumulate and the platform connections; this view reports what
              they resolved to.
            </span>
          </div>
        </div>

        <Section index={1} title="Brand Information">
          <BrandInformation brand={brand} />
        </Section>

        <Section
          index={2}
          title="Social Accounts"
          hint="Only the three approved platforms are shown. A platform with no linked account cannot be opened for this Brand."
        >
          <SocialAccounts accounts={accounts} connections={connections} />
        </Section>

        <Section
          index={3}
          title="Sync Settings"
          hint="Collection state is reported by the backend. Opening this view never starts a job."
        >
          <SyncSettings accounts={accounts} jobs={jobs} mutationAvailable={mutationAvailable} />
        </Section>

        <Section index={4} title="Readiness">
          <Readiness accounts={accounts} jobs={jobs} readiness={readiness} />
        </Section>

        <div className="setup-actions">
          <button className="primary-button compact-button" onClick={onClose} type="button">
            Close
          </button>
        </div>
      </div>
    </Dialog>
  );
}
