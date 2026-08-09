import {
  Facebook,
  Home,
  Instagram,
  PieChart,
  PlugZap,
  Settings,
  X,
} from "lucide-react";
import type { ComponentType } from "react";
import { NavLink } from "../routing";

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
  "Home",
  "Analytics",
  "Social Media",
  ...platformNavigation.map((item) => item.label),
  "Settings",
  "Integrations",
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

export function Sidebar({ open, onClose }: SidebarProps) {
  const { capabilities } = useBrandScope();
  const settingsVisible = capabilities?.permissions.settings_visible === true;
  const integrationsVisible = capabilities?.permissions.integrations_visible === true;
  const tiktokVisible = platformAvailable("tiktok", capabilities);
  const homePath = tiktokVisible ? "/tiktok" : "/facebook";
  const visiblePlatforms = platformNavigation.filter(
    (item) => item.platform !== "tiktok" || tiktokVisible,
  );

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
            {visiblePlatforms.map(({ icon: Icon, label, path, platform }) => (
              <div className="sidebar-channel-row" key={platform}>
                <span aria-hidden="true" className="channel-connector" />
                <NavigationLink icon={Icon} label={label} onClick={onClose} path={path} />
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
          <div className="sidebar-product-note"><span />SocialMedia standalone</div>
        </nav>
      </aside>
    </>
  );
}
