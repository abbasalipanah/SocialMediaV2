import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { useBrandScope } from "../app/BrandScopeProvider";
import { useAuth } from "../auth";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell() {
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const location = useLocation();
  const { logout } = useAuth();
  const { error } = useBrandScope();

  useEffect(() => setNavigationOpen(false), [location.pathname]);

  const handleLogout = async () => {
    setLoggingOut(true);
    setLogoutError("");
    try {
      await logout();
    } catch {
      setLogoutError("Sign out could not be completed. Please try again.");
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <div className="app-frame">
      <Sidebar
        loggingOut={loggingOut}
        onClose={() => setNavigationOpen(false)}
        onLogout={() => void handleLogout()}
        open={navigationOpen}
      />
      <div className="app-workspace">
        <Topbar
          loggingOut={loggingOut}
          onLogout={() => void handleLogout()}
          onOpenNavigation={() => setNavigationOpen(true)}
        />
        {(logoutError || error) && (
          <div className="shell-alert" role="alert">
            {logoutError || "Workspace data could not be loaded. Refresh to try again."}
          </div>
        )}
        <div className="route-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
