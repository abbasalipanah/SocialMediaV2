import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import { BrandScopeProvider, useBrandScope } from "../app/BrandScopeProvider";
import { useAuth } from "../auth";
import { AppShell } from "../layout";
import { ScreenState } from "../ui";
import { LoginPage } from "./LoginPage";
import { SsoConsumePage } from "./SsoConsumePage";

const OverviewPage = lazy(() => import("../features/overview"));
const FacebookPage = lazy(() => import("../features/facebook"));
const InstagramPage = lazy(() => import("../features/instagram"));
const TikTokPage = lazy(() => import("../features/tiktok"));
const IntegrationsPage = lazy(() => import("../features/integrations"));
const SettingsPage = lazy(() => import("../features/settings"));
const TikTokConnectPage = lazy(() =>
  import("../features/settings").then((module) => ({ default: module.TikTokConnectPage })),
);
const AuditPage = lazy(() =>
  import("../features/settings").then((module) => ({ default: module.AuditPage })),
);

function RouteLoading() {
  return (
    <div aria-live="polite" className="route-loading">
      <span className="loading-spinner" /> Loading view…
    </div>
  );
}

function AuthenticatedWorkspace() {
  const auth = useAuth();
  const location = useLocation();
  if (auth.status === "checking") {
    return (
      <ScreenState eyebrow="ACCUMULATE" title="Loading your workspace…">
        <p>Checking session and Brand access.</p>
      </ScreenState>
    );
  }
  if (auth.status === "error") {
    return (
      <ScreenState eyebrow="Connection error" title="We could not verify your session">
        <p>No access decision was made. Retry the secure session check.</p>
        <button className="primary-button" onClick={auth.retry} type="button">Try again</button>
      </ScreenState>
    );
  }
  if (!auth.user) return <Navigate replace state={{ from: location.pathname }} to="/login" />;
  return (
    <BrandScopeProvider>
      <Outlet />
    </BrandScopeProvider>
  );
}

function SettingsGuard({ audit = false, children }: { audit?: boolean; children: ReactNode }) {
  const { capabilities, isLoading } = useBrandScope();
  if (isLoading) return <RouteLoading />;
  const allowed = audit
    ? capabilities?.permissions.internal_audit_visible
    : capabilities?.permissions.settings_visible;
  return allowed ? children : <Navigate replace to="/overview" />;
}

export function AppRoutes() {
  return (
    <Suspense fallback={<RouteLoading />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/sso/consume" element={<SsoConsumePage />} />
        <Route element={<AuthenticatedWorkspace />}>
          <Route element={<AppShell />}>
            <Route index element={<Navigate replace to="/overview" />} />
            <Route path="overview" element={<OverviewPage />} />
            <Route path="facebook" element={<FacebookPage />} />
            <Route path="instagram" element={<InstagramPage />} />
            <Route path="tiktok" element={<TikTokPage />} />
            <Route path="integrations" element={<IntegrationsPage />} />
            <Route
              path="settings"
              element={<SettingsGuard><SettingsPage /></SettingsGuard>}
            >
              <Route
                path="tiktok/connect"
                element={<SettingsGuard><TikTokConnectPage /></SettingsGuard>}
              />
              <Route
                path="audit"
                element={<SettingsGuard audit><AuditPage /></SettingsGuard>}
              />
            </Route>
          </Route>
        </Route>
        <Route path="*" element={<Navigate replace to="/overview" />} />
      </Routes>
    </Suspense>
  );
}
