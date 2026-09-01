import {
  lazy,
  Suspense,
  type ComponentType,
  type LazyExoticComponent,
  type ReactNode,
} from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "../routing";

import type { Platform } from "../api";

import { BrandScopeProvider, useBrandScope } from "../app/BrandScopeProvider";
import { useAuth } from "../auth";
import { AppShell } from "../layout";
import { PLATFORM_CATALOG } from "../platforms/catalog";
import { ScreenState } from "../ui";
import { LoginPage } from "./LoginPage";
import { SsoConsumePage } from "./SsoConsumePage";

const FacebookPage = lazy(() => import("../features/facebook"));
const InstagramPage = lazy(() => import("../features/instagram"));
const TikTokPage = lazy(() => import("../features/tiktok"));
const platformPages = {
  facebook: FacebookPage,
  instagram: InstagramPage,
  tiktok: TikTokPage,
} satisfies Record<Platform, LazyExoticComponent<ComponentType>>;
const OverviewPage = lazy(() => import("../features/overview"));
const SettingsPage = lazy(() => import("../features/settings"));
const IntegrationsPage = lazy(() => import("../features/integrations"));
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

function PlatformGuard({ platform, children }: { platform: Platform; children: ReactNode }) {
  const { capabilities, isLoading } = useBrandScope();
  if (isLoading) return <RouteLoading />;
  // The sidebar shows a platform this Brand has no account for as locked. The
  // route has to agree: without this the page still opened from a bookmark, a
  // back button, or a Brand switch that left the URL where it was, and it
  // rendered an empty dashboard headed "No Accounts".
  const available = capabilities?.platforms.find(
    (item) => item.platform === platform,
  )?.navigation_available;
  return available ? children : <Navigate replace to="/overview" />;
}

function SettingsGuard({ audit = false, children }: { audit?: boolean; children: ReactNode }) {
  const { capabilities, isLoading } = useBrandScope();
  if (isLoading) return <RouteLoading />;
  const allowed = audit
    ? capabilities?.permissions.internal_audit_visible
    : capabilities?.permissions.settings_visible;
  return allowed ? children : <Navigate replace to="/overview" />;
}

function IntegrationsGuard({ children }: { children: ReactNode }) {
  const { capabilities, isLoading } = useBrandScope();
  if (isLoading) return <RouteLoading />;
  return capabilities?.permissions.integrations_visible
    ? children
    : <Navigate replace to="/overview" />;
}

export function AppRoutes() {
  return (
    <Suspense fallback={<RouteLoading />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/sso/consume" element={<SsoConsumePage />} />
        <Route path="/sso/consume" element={<SsoConsumePage />} />
        <Route element={<AuthenticatedWorkspace />}>
          <Route element={<AppShell />}>
            <Route path="overview" element={<OverviewPage />} />
            {PLATFORM_CATALOG.map((platform) => {
              const PlatformPage = platformPages[platform.id];
              return (
                <Route
                  key={platform.id}
                  path={platform.route}
                  element={
                    <PlatformGuard platform={platform.id}>
                      <PlatformPage />
                    </PlatformGuard>
                  }
                />
              );
            })}
            <Route path="integrations" element={<IntegrationsGuard><IntegrationsPage /></IntegrationsGuard>} />
            <Route path="settings" element={<SettingsGuard><SettingsPage /></SettingsGuard>}>
              <Route
                path="tiktok/connect"
                element={<TikTokConnectPage />}
              />
              <Route
                path="audit"
                element={<SettingsGuard audit><AuditPage /></SettingsGuard>}
              />
            </Route>
            <Route index element={<OverviewPage />} />
            <Route path="*" element={<Navigate replace to="/overview" />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}
