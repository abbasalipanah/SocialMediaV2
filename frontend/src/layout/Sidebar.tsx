import {
  Facebook,
  Lock,
  Home,
  Instagram,
  Linkedin,
  PieChart,
  PlugZap,
  Settings,
  X,
  Youtube,
} from "lucide-react";
import type { ComponentType } from "react";
import { NavLink } from "../routing";

import type { Platform } from "../api";
import { accumulateUrl } from "../app/accumulateLink";
import { useBrandScope } from "../app/BrandScopeProvider";
import { PLATFORM_CATALOG } from "../platforms/catalog";
import { platformNavigationAvailable } from "../platforms/navigation";

type SidebarProps = {
  open: boolean;
  onClose: () => void;
  onLogout: () => void;
  loggingOut: boolean;
};

const TiktokMark = ({ size = 20 }: { size?: number }) => (
  <span aria-hidden="true" className="tiktok-mark" style={{ fontSize: size }}>♪</span>
);

const platformIcons = {
  facebook: Facebook,
  instagram: Instagram,
  tiktok: TiktokMark,
  x: X,
  linkedin: Linkedin,
  youtube: Youtube,
} satisfies Record<Platform, ComponentType<{ size?: number }>>;

const platformNavigation = PLATFORM_CATALOG.map((platform) => ({
  label: platform.label,
  path: `/${platform.route}`,
  platform: platform.id,
  icon: platformIcons[platform.id],
}));

export const SOCIAL_NAVIGATION_LABELS = [
  "Home",
  "Analytics",
  "Social Media",
  ...platformNavigation.map((item) => item.label),
  "Settings",
  "Integrations",
] as const;

function NavigationLink({
  path,
  label,
  icon: Icon,
  onClick,
  locked = false,
}: {
  path: string;
  label: string;
  icon: ComponentType<{ size?: number }>;
  onClick: () => void;
  locked?: boolean;
}) {
  if (locked) {
    // A channel the Brand has not connected keeps its place rather than
    // disappearing, so the navigation reads the same for every Brand and the
    // absence is stated instead of hidden.
    return (
      <span
        aria-disabled="true"
        className="sidebar-link locked"
        title={`${label} is not connected for this Brand`}
      >
        <Icon size={20} />
        <span>{label}</span>
        <Lock aria-hidden="true" className="sidebar-link-lock" size={14} />
      </span>
    );
  }
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

export function Sidebar({ open, onClose }: SidebarProps) {
  const { capabilities } = useBrandScope();
  const settingsVisible = capabilities?.permissions.settings_visible === true;
  const integrationsVisible = capabilities?.permissions.integrations_visible === true;
  const homePath = "/";

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
          <NavLink aria-label="Accumulate Social Media" onClick={onClose} to={homePath}>
            <img alt="" className="accumulate-sidebar-logo" src="/accumulate-logo.svg" />
          </NavLink>
          <button aria-label="Close navigation" className="sidebar-close" onClick={onClose} type="button">
            <X size={20} />
          </button>
        </div>

        <nav className="sidebar-nav">
          <NavigationLink icon={Home} label="Home" onClick={onClose} path={homePath} />
          <div className="sidebar-link analytics-toggle active-parent">
            <PieChart size={18} />
            <span>Analytics</span>
            <span className="link-chevron">⌄</span>
          </div>
          <div className="sidebar-channel-tree">
            <div className="sidebar-channel-title">Social Media</div>
            {platformNavigation.map(({ icon: Icon, label, path, platform }) => (
              <div className="sidebar-channel-row" key={platform}>
                <span aria-hidden="true" className="channel-connector" />
                <NavigationLink
                  icon={Icon}
                  label={label}
                  locked={!platformNavigationAvailable(platform, capabilities)}
                  onClick={onClose}
                  path={path}
                />
              </div>
            ))}
          </div>
        </nav>

        <nav aria-label="Account navigation" className="sidebar-footer">
          {settingsVisible && (
            <NavigationLink icon={Settings} label="Settings" onClick={onClose} path="/settings" />
          )}
          {integrationsVisible && (
            <NavigationLink icon={PlugZap} label="Integrations" onClick={onClose} path="/integrations" />
          )}
          <a className="sidebar-return-link" href={accumulateUrl}>
            <img alt="" className="sidebar-return-mark" src="/favicon.png" />
            <span>Back to Accumulate AI</span>
          </a>
        </nav>
      </aside>
    </>
  );
}
