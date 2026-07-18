import { Check, Circle, Facebook, Instagram, Radio, Settings2 } from "lucide-react";
import { useState } from "react";

import type {
  OperationsReadiness,
  Platform,
  ReportingAccount,
  ReportingConnection,
  ReportingSyncJob,
  SettingsBrand,
} from "../../api";
import { Dialog } from "../../ui";
import { PLATFORM_LABELS } from "../dashboard/catalog";
import { formatDate, humanize } from "../dashboard/format";

const STEPS = ["Brand Information", "Social Accounts", "Sync Settings", "Readiness Summary"] as const;
type SetupStep = (typeof STEPS)[number];
const PLATFORMS: Platform[] = ["facebook", "instagram", "tiktok"];

function PlatformSymbol({ platform }: { platform: Platform }) {
  if (platform === "facebook") return <Facebook size={19} />;
  if (platform === "instagram") return <Instagram size={19} />;
  return <span className="drawer-tiktok">♪</span>;
}

function BrandInformation({ brands }: { brands: SettingsBrand[] }) {
  return <div className="setup-step"><p className="setup-intro">Review the Brands visible to this signed-in workspace. Authority remains managed by Accumulate.</p><div className="setup-brand-list">{brands.map((brand) => <article key={brand.brand_id}><div><strong>{brand.name ?? `Brand ${brand.brand_id}`}</strong><span>{brand.parent_brand_id ? "Child Brand" : "Parent Brand"}</span></div><dl><div><dt>Linked accounts</dt><dd>{brand.linked_account_count}</dd></div><div><dt>Last sync</dt><dd>{formatDate(brand.last_sync_at)}</dd></div></dl></article>)}</div></div>;
}

function SocialAccountStep({ accounts, connections }: { accounts: ReportingAccount[]; connections: ReportingConnection[] }) {
  return <div className="setup-step"><p className="setup-intro">Only the three approved social platforms are shown.</p><div className="setup-platform-list">{PLATFORMS.map((platform) => {
    const platformAccounts = accounts.filter((item) => item.platform === platform);
    const connection = connections.find((item) => item.platform === platform);
    return <article key={platform}><div className={`setup-platform-icon setup-${platform}`}><PlatformSymbol platform={platform} /></div><div><strong>{PLATFORM_LABELS[platform]}</strong><span>{platformAccounts.length} linked account{platformAccounts.length === 1 ? "" : "s"}</span></div><span className="setup-state">{humanize(connection?.state ?? "not connected")}</span></article>;
  })}</div></div>;
}

function SyncSettingsStep({ accounts, jobs, mutationAvailable }: { accounts: ReportingAccount[]; jobs: ReportingSyncJob[]; mutationAvailable: boolean }) {
  const active = jobs.filter((item) => ["pending", "running"].includes(item.status)).length;
  return <div className="setup-step"><p className="setup-intro">Collection state is reported by the backend. This drawer never starts a job when opened.</p><div className="setup-summary-grid"><article><Radio size={20} /><span>Nightly enabled</span><strong>{accounts.filter((item) => item.nightly_enabled).length}</strong></article><article><Settings2 size={20} /><span>Pending or running</span><strong>{active}</strong></article></div><label className="readonly-toggle"><input checked={mutationAvailable} disabled readOnly type="checkbox" /><span><strong>Manual operations</strong><small>{mutationAvailable ? "Available for this scope" : "Disabled by backend capability"}</small></span></label></div>;
}

function ReadinessStep({ readiness, accounts, jobs }: { readiness: OperationsReadiness | undefined; accounts: ReportingAccount[]; jobs: ReportingSyncJob[] }) {
  const failed = jobs.filter((item) => item.status === "failed").length;
  const checks = [
    ["Backend readiness", readiness?.status === "ready", readiness?.status ?? "Unavailable"],
    ["Reporting database", readiness?.database_configured === true, readiness?.database_configured ? "Configured" : "Not configured"],
    ["Linked social accounts", accounts.length > 0, `${accounts.length} linked`],
    ["Failed sync jobs", failed === 0, failed === 0 ? "None" : `${failed} require attention`],
  ] as const;
  return <div className="setup-step"><p className="setup-intro">This summary is read-only and scoped to the selected Brand.</p><div className="readiness-list">{checks.map(([label, ready, detail]) => <article key={label}><span className={ready ? "ready" : "attention"}>{ready ? <Check size={17} /> : <Circle size={17} />}</span><div><strong>{label}</strong><small>{detail}</small></div></article>)}</div></div>;
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
  const [step, setStep] = useState<SetupStep>(STEPS[0]);
  const index = STEPS.indexOf(step);
  return (
    <Dialog description="Review social reporting setup and readiness." drawer onClose={onClose} open={open} title="Brand Setup">
      <div className="setup-layout">
        <nav aria-label="Setup steps" className="setup-navigation">{STEPS.map((item, itemIndex) => <button aria-current={step === item ? "step" : undefined} className={step === item ? "active" : ""} key={item} onClick={() => setStep(item)} type="button"><span>{itemIndex + 1}</span>{item}</button>)}</nav>
        <div className="setup-content">
          <div className="setup-progress"><span>Step {index + 1} of {STEPS.length}</span><strong>{step}</strong></div>
          {step === "Brand Information" && <BrandInformation brands={brands} />}
          {step === "Social Accounts" && <SocialAccountStep accounts={accounts} connections={connections} />}
          {step === "Sync Settings" && <SyncSettingsStep accounts={accounts} jobs={jobs} mutationAvailable={mutationAvailable} />}
          {step === "Readiness Summary" && <ReadinessStep accounts={accounts} jobs={jobs} readiness={readiness} />}
          <div className="setup-actions"><button className="secondary-button" disabled={index === 0} onClick={() => setStep(STEPS[index - 1] ?? STEPS[0])} type="button">Back</button>{index < STEPS.length - 1 ? <button className="primary-button compact-button" onClick={() => setStep(STEPS[index + 1] ?? STEPS.at(-1)!)} type="button">Continue</button> : <button className="primary-button compact-button" onClick={onClose} type="button">Done</button>}</div>
        </div>
      </div>
    </Dialog>
  );
}
