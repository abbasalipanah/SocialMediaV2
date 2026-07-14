import { Outlet, useLocation } from "react-router-dom";

import { PhaseShellPage } from "../shared/PhaseShellPage";

export default function SettingsPage() {
  const location = useLocation();
  const nested = location.pathname !== "/settings";
  return (
    <PhaseShellPage
      description="Connections, account links and workspace visibility are controlled by backend capabilities."
      title="Settings"
    >
      {nested && <Outlet />}
    </PhaseShellPage>
  );
}

export function TikTokConnectPage() {
  return (
    <section className="nested-placeholder">
      <p className="eyebrow">Owner activation</p>
      <h2>TikTok connection</h2>
      <p>This shell route is inert. Provider authorization is not started by opening this page.</p>
    </section>
  );
}

export function AuditPage() {
  return (
    <section className="nested-placeholder">
      <p className="eyebrow">Internal</p>
      <h2>Audit</h2>
      <p>The audit surface is available only when the backend grants internal visibility.</p>
    </section>
  );
}
