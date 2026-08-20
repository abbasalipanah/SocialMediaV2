import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Circle, Facebook, Instagram, Radio, Settings2, Store } from "lucide-react";
import { useState } from "react";

import type {
  OperationsReadiness,
  Platform,
  ReportingAccount,
  ReportingConnection,
  ReportingSyncJob,
  SettingsBrand,
} from "../../api";
import {
  apiQuery,
  connectionsSchema,
  queryString,
  socialAccountsSchema,
  syncJobsSchema,
} from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";
import { Dialog } from "../../ui";
import { MetaConnectionModal } from "../integrations/MetaConnectionModal";
import { TikTokConnectionModal } from "../integrations/TikTokConnectionModal";
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

function BrandInformation({ brand }: { brand: SettingsBrand }) {
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
  canManage,
  loading,
  onConnect,
}: {
  accounts: ReportingAccount[];
  connections: ReportingConnection[];
  canManage: boolean;
  loading: boolean;
  onConnect: (platform: Platform) => void;
}) {
  return (
    <div className="setup-platform-list">
      {PLATFORMS.map((platform) => {
        const linked = accounts.filter((item) => item.platform === platform);
        // The account's own connection state, not the connection list's. A Meta
        // connection is stored once under `facebook` and serves Instagram too,
        // so looking it up per platform reported a linked Instagram profile as
        // "Not Connected".
        const state =
          linked[0]?.connection_state ??
          connections.find((item) => item.platform === platform)?.state ??
          "not connected";
        return (
          <article key={platform}>
            <div className={`setup-platform-icon setup-${platform}`}>
              <PlatformSymbol platform={platform} />
            </div>
            <div className="setup-platform-detail">
              <strong>{PLATFORM_LABELS[platform]}</strong>
              <span>
                {loading
                  ? "Checking…"
                  : linked.length > 0
                    ? linked
                        .map((item) => item.display_name || item.external_id)
                        .join(" · ")
                    : "No account linked to this Brand"}
              </span>
            </div>
            <span className={linked.length > 0 ? "setup-state" : "setup-state muted"}>
              {humanize(state)}
            </span>
            <button
              className="settings-row-action"
              disabled={!canManage}
              onClick={() => onConnect(platform)}
              title={
                canManage ? undefined : "Needs an agency admin or super admin, on a single Brand"
              }
              type="button"
            >
              {linked.length > 0 ? "Edit" : "Connect"}
            </button>
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
  const awaiting = accounts.filter(
    (item) => !["complete", "completed"].includes(item.backfill_status.toLowerCase()),
  ).length;
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
      <p className="setup-note">
        {awaiting === 0
          ? "Every linked account has finished its backfill. The scheduled collection keeps them current."
          : `${awaiting} account${awaiting === 1 ? "" : "s"} still to backfill. A newly linked account is backfilled by the scheduled collection; it is not started from this view.`}
      </p>
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
  brand,
  accounts,
  connections,
  jobs,
  readiness,
  mutationAvailable,
}: {
  open: boolean;
  onClose: () => void;
  brand: SettingsBrand | null;
  accounts: ReportingAccount[];
  connections: ReportingConnection[];
  jobs: ReportingSyncJob[];
  readiness: OperationsReadiness | undefined;
  mutationAvailable: boolean;
}) {
  const queryClient = useQueryClient();
  const { capabilities, rollup } = useBrandScope();
  const [connecting, setConnecting] = useState<Platform | null>(null);

  if (!brand) return null;

  // Fetched for the Brand whose row was clicked, not filtered out of the page's
  // lists: those are scoped to the Brand the workspace is currently on, so any
  // other row found nothing in them and reported a Brand with linked accounts
  // as having none, with every platform offering "Connect".
  const scope = queryString({ brand_id: brand.brand_id, rollup: false });
  const accountsQuery = useQuery({
    enabled: open,
    queryKey: ["settings", "setup", "accounts", brand.brand_id],
    queryFn: ({ signal }) =>
      apiQuery(`/api/settings/social-accounts${scope}`, socialAccountsSchema, signal),
  });
  const connectionsQuery = useQuery({
    enabled: open,
    queryKey: ["settings", "setup", "connections", brand.brand_id],
    queryFn: ({ signal }) =>
      apiQuery(`/api/settings/connections${scope}`, connectionsSchema, signal),
  });
  const jobsQuery = useQuery({
    enabled: open,
    queryKey: ["settings", "setup", "jobs", brand.brand_id],
    queryFn: ({ signal }) =>
      apiQuery(`/api/settings/sync-jobs${scope}`, syncJobsSchema, signal),
  });

  const brandAccounts = accountsQuery.data?.items ?? [];
  const brandConnections = connectionsQuery.data?.items ?? [];
  const brandJobs = jobsQuery.data?.items ?? [];
  const loadingAccounts = accountsQuery.isPending;
  const brandName = brand.name ?? `Brand ${brand.brand_id}`;

  // Settings authority may set up any Brand its signed scope grants, which is
  // what opening setup from a row means. The backend re-checks write access on
  // this Brand before any exchange, so this only decides whether to offer it.
  const canManage =
    !rollup &&
    capabilities?.permissions.meta_connection_manage === true &&
    capabilities?.permissions.tiktok_connection_manage === true;

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["settings"] });
    setConnecting(null);
  };

  return (
    <>
      <Dialog
        description="Review Brand details, link social accounts and check collection readiness."
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
              <strong>{brandName}</strong>
              <span>
                Brand #{brand.brand_id} ·{" "}
                {loadingAccounts
                  ? "checking linked accounts…"
                  : `${brandAccounts.length} linked account${
                      brandAccounts.length === 1 ? "" : "s"
                    }`}
              </span>
            </div>
          </div>

          <Section index={1} title="Brand Information">
            <BrandInformation brand={brand} />
          </Section>

          <Section
            index={2}
            title="Social Accounts"
            hint="Connect Facebook, Instagram or TikTok for this Brand, or edit what is already linked."
          >
            <SocialAccounts
              accounts={brandAccounts}
              canManage={canManage}
              connections={brandConnections}
              loading={loadingAccounts}
              onConnect={setConnecting}
            />
            {!canManage && (
              <p className="setup-note">
                Linking accounts needs an agency admin or super admin on a single
                Brand. Leave the roll-up view to set up {brandName}.
              </p>
            )}
          </Section>

          <Section index={3} title="Sync Settings">
            <SyncSettings
              accounts={brandAccounts}
              jobs={brandJobs}
              mutationAvailable={mutationAvailable}
            />
          </Section>

          <Section index={4} title="Readiness">
            <Readiness accounts={brandAccounts} jobs={brandJobs} readiness={readiness} />
          </Section>

          <div className="setup-actions">
            <button className="primary-button compact-button" onClick={onClose} type="button">
              Close
            </button>
          </div>
        </div>
      </Dialog>

      {(connecting === "facebook" || connecting === "instagram") && (
        <MetaConnectionModal
          brandId={brand.brand_id}
          brandName={brandName}
          focusPlatform={connecting}
          onClose={() => setConnecting(null)}
          onConnected={refresh}
        />
      )}
      {connecting === "tiktok" && (
        <TikTokConnectionModal
          brandId={brand.brand_id}
          brandName={brandName}
          onClose={() => setConnecting(null)}
          onConnected={refresh}
        />
      )}
    </>
  );
}
