import {
  ArrowLeft,
  BarChart3,
  Facebook,
  HelpCircle,
  Instagram,
  LockKeyhole,
  LogOut,
  Settings,
  X,
} from "lucide-react";
import type { ComponentType } from "react";
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
          <div aria-hidden="true" className="brand-symbol">A</div>
          <div>
            <strong>ACCUMULATE</strong>
            <span>Social Media</span>
          </div>
          <button aria-label="Close navigation" className="sidebar-close" onClick={onClose} type="button">
            <X size={20} />
          </button>
        </div>

        <nav className="sidebar-nav">
          <p className="sidebar-section-label">Workspace</p>
          <NavigationLink icon={BarChart3} label="Overview" onClick={onClose} path="/overview" />
          <p className="sidebar-section-label channel-label">Channels</p>
          {platformNavigation.map(({ icon: Icon, label, path, platform }) => {
            const available = platformAvailable(platform, capabilities);
            return available ? (
              <NavigationLink icon={Icon} key={platform} label={label} onClick={onClose} path={path} />
            ) : (
              <div
                aria-disabled="true"
                className="sidebar-link locked"
                data-loading={isLoading || undefined}
                key={platform}
                title={isLoading ? "Checking availability" : "Connect this channel in Settings"}
              >
                <Icon size={20} />
                <span>{label}</span>
                <LockKeyhole className="link-lock" size={14} />
              </div>
            );
          })}
        </nav>

        <nav aria-label="Account navigation" className="sidebar-footer">
          {settingsVisible && (
            <NavigationLink icon={Settings} label="Settings" onClick={onClose} path="/settings" />
          )}
          <a className="sidebar-link" href="mailto:support@theaccumulate.com">
            <HelpCircle size={20} />
            <span>Support</span>
          </a>
          <a className="sidebar-link" href="https://app.theaccumulate.com">
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
