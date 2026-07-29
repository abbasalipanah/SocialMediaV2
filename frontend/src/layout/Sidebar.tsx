import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  Facebook,
  HelpCircle,
  Home,
  Instagram,
  LockKeyhole,
  LogOut,
  PieChart,
  PlugZap,
  Settings,
  X,
} from "lucide-react";
import { useState, type ComponentType } from "react";
import { NavLink } from "react-router-dom";

import type { Platform } from "../api";
import { useBrandScope } from "../app/BrandScopeProvider";

type SidebarProps = {
  open: boolean;
  onClose: () => void;
  onLogout: () => void;
  loggingOut: boolean;
};

const TiktokMark = ({ size = 20 }: { size?: number }) => (
  <span aria-hidden="true" className="tiktok-mark" style={{ fontSize: size }}>♪</span>
);

const platformNavigation: Array<{
  label: string;
  path: string;
  platform: Platform;
  icon: ComponentType<{ size?: number }>;
}> = [
  { label: "Facebook", path: "/facebook", platform: "facebook", icon: Facebook },
  { label: "Instagram", path: "/instagram", platform: "instagram", icon: Instagram },
  { label: "TikTok", path: "/tiktok", platform: "tiktok", icon: TiktokMark },
];

export const SOCIAL_NAVIGATION_LABELS = [
  "Overview",
  ...platformNavigation.map((item) => item.label),
] as const;

function platformAvailable(platform: Platform, capabilities: ReturnType<typeof useBrandScope>["capabilities"]) {
  return (
    capabilities?.platforms.find((item) => item.platform === platform)?.navigation_available ??
    false
  );
}

function NavigationLink({
  path,
  label,
  icon: Icon,
  onClick,
}: {
  path: string;
  label: string;
  icon: ComponentType<{ size?: number }>;
  onClick: () => void;
}) {
  return (
    <NavLink
      className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
      onClick={onClick}
      to={path}
    >
      <Icon size={20} />
      <span>{label}</span>
    </NavLink>
  );
}

export function Sidebar({ open, onClose, onLogout, loggingOut }: SidebarProps) {
  const [analyticsExpanded, setAnalyticsExpanded] = useState(true);
  const { capabilities, isLoading } = useBrandScope();
  const settingsVisible = capabilities?.permissions.settings_visible === true;

  return (
    <>
      <button
        aria-label="Close navigation"
        className={`sidebar-backdrop${open ? " visible" : ""}`}
        onClick={onClose}
        tabIndex={open ? 0 : -1}
        type="button"
      />
      <aside aria-label="Primary navigation" className={`app-sidebar${open ? " open" : ""}`}>
        <div className="sidebar-brand">
          <NavLink aria-label="Social Media overview" onClick={onClose} to="/overview">
            <img alt="" className="accumulate-sidebar-logo" src="/accumulate-logo.svg" />
          </NavLink>
          <button aria-label="Close navigation" className="sidebar-close" onClick={onClose} type="button">
            <X size={20} />
          </button>
        </div>

        <nav className="sidebar-nav">
          <NavigationLink icon={Home} label="Overview" onClick={onClose} path="/overview" />
          <button
            aria-expanded={analyticsExpanded}
            className="sidebar-link analytics-toggle"
            onClick={() => setAnalyticsExpanded((current) => !current)}
            type="button"
          >
            <PieChart size={18} />
            <span>Analytics</span>
            {analyticsExpanded ? <ChevronDown className="link-chevron" size={14} /> : <ChevronRight className="link-chevron" size={14} />}
          </button>
          {analyticsExpanded && (
            <div className="sidebar-channel-tree">
              {platformNavigation.map(({ icon: Icon, label, path, platform }) => {
                const available = platformAvailable(platform, capabilities);
                return (
                  <div className="sidebar-channel-row" key={platform}>
                    <span aria-hidden="true" className="channel-connector" />
                    {available ? (
                      <NavigationLink icon={Icon} label={label} onClick={onClose} path={path} />
                    ) : (
                      <div
                        aria-disabled="true"
                        className="sidebar-link locked"
                        data-loading={isLoading || undefined}
                        title={isLoading ? "Checking availability" : `Connect ${label} in Settings`}
                      >
                        <Icon size={17} />
                        <span>{label}</span>
                        <LockKeyhole className="link-lock" size={13} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </nav>

        <nav aria-label="Account navigation" className="sidebar-footer">
          {settingsVisible && (
            <NavigationLink icon={Settings} label="Settings" onClick={onClose} path="/settings" />
          )}
          <NavigationLink icon={PlugZap} label="Integrations" onClick={onClose} path="/integrations" />
          <a className="sidebar-link" href="mailto:support@theaccumulate.com">
            <HelpCircle size={20} />
            <span>Support</span>
          </a>
          <a className="sidebar-return-link" href="https://app.theaccumulate.com">
            <ArrowLeft size={20} />
            <span>Back to Accumulate</span>
          </a>
          <button className="sidebar-link sidebar-action" disabled={loggingOut} onClick={onLogout} type="button">
            <LogOut size={20} />
            <span>{loggingOut ? "Signing out…" : "Sign out"}</span>
          </button>
        </nav>
      </aside>
    </>
  );
}
