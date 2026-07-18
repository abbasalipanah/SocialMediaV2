import { ArrowRight, Cable, Layers3 } from "lucide-react";
import type { ReactNode } from "react";

import type { Platform } from "../../api";
import { useBrandScope } from "../../app/BrandScopeProvider";

export function PhaseShellPage({
  title,
  description,
  platform,
  children,
}: {
  title: string;
  description: string;
  platform?: Platform;
  children?: ReactNode;
}) {
  const { capabilities, rollup, selectedBrand } = useBrandScope();
  const platformState = platform
    ? capabilities?.platforms.find((item) => item.platform === platform)
    : null;
  const available = platformState?.navigation_available ?? false;

  return (
    <main className="page-shell">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Social Media</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <span className={`availability-pill${available ? " available" : ""}`}>
          <Cable size={15} />
          {platform ? (available ? "Available" : "Connection required") : "Workspace ready"}
        </span>
      </header>
      <section className="phase-panel">
        <div className="phase-panel-icon"><Layers3 size={24} /></div>
        <div>
          <p className="eyebrow">Shell scope</p>
          <h2>{rollup ? "All accessible child brands" : selectedBrand?.name ?? "Selected brand"}</h2>
          <p>
            Navigation and selection are live. Dashboard data, tables, charts and detailed empty states
            are delivered in Phase 8.
          </p>
        </div>
        <ArrowRight aria-hidden="true" size={20} />
      </section>
      {children}
    </main>
  );
}
