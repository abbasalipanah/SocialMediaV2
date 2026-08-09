import { Building2, Check, LogOut, Menu, UserRound } from "lucide-react";
import { useLocation } from "../routing";

import type { Platform } from "../api";
import { useBrandScope } from "../app/BrandScopeProvider";
import { usePlatformAccounts } from "../app/usePlatformAccounts";
import { useAuth } from "../auth";
import { Popover, ScopePicker } from "../ui";

function routePlatform(pathname: string): Platform | null {
  if (pathname.startsWith("/facebook")) return "facebook";
  if (pathname.startsWith("/instagram")) return "instagram";
  if (pathname.startsWith("/tiktok")) return "tiktok";
  return null;
}

function brandLabel(name: string | null, brandId: string): string {
  return name?.trim() || `Brand ${brandId}`;
}

function accountLabel(platform: Platform): string {
  if (platform === "facebook") return "Facebook Page";
  if (platform === "instagram") return "Instagram Profile";
  return "TikTok Account";
}

function accountDetail(
  platform: Platform,
  externalId: string,
  healthStatus: string,
  lastSyncedAt: string | null,
): string {
  const idLabel = platform === "facebook" ? "Page ID" : platform === "instagram" ? "Profile ID" : "Account ID";
  const syncLabel = lastSyncedAt
    ? `Last sync ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(lastSyncedAt))}`
    : "Not synced yet";
  return `${idLabel} ${externalId} · ${healthStatus.replaceAll("_", " ")} · ${syncLabel}`;
}

export function Topbar({
  onOpenNavigation,
  onLogout,
  loggingOut,
}: {
  onOpenNavigation: () => void;
  onLogout: () => void;
  loggingOut: boolean;
}) {
  const location = useLocation();
  const platform = routePlatform(location.pathname);
  const { user } = useAuth();
  const {
    parentBrands,
    parentBrand,
    childBrands,
    selectedBrand,
    selectedBrandId,
    rollup,
    selectParent,
    selectChild,
    accountSelections,
    selectAccount,
  } = useBrandScope();
  const accountState = usePlatformAccounts(platform);

  if (!user) return null;

  return (
    <header className="app-topbar">
      <button
        aria-label="Open navigation"
        className="mobile-menu-button"
        onClick={onOpenNavigation}
        type="button"
      >
        <Menu size={22} />
      </button>

      <div className="topbar-selectors">
        <Popover
          className="brand-selector"
          label="Brand family"
          value={parentBrand ? brandLabel(parentBrand.name, parentBrand.brand_id) : "Loading…"}
        >
          {(close) => (
            <ScopePicker
              onSelect={(id) => {
                selectParent(id);
                close();
              }}
              options={parentBrands.map((brand) => ({
                id: brand.brand_id,
                label: brandLabel(brand.name, brand.brand_id),
                detail: brand.visibility === "hidden_parent" ? "Parent workspace" : undefined,
              }))}
              selectedId={parentBrand?.brand_id ?? ""}
            />
          )}
        </Popover>

        {childBrands.length > 0 && (
          <Popover
            className="child-selector"
            label="Account group"
            value={rollup ? "All child brands" : brandLabel(selectedBrand?.name ?? null, selectedBrandId)}
          >
            {(close) => (
              <ScopePicker
                onSelect={(id) => {
                  selectChild(id);
                  close();
                }}
                options={[
                  { id: "all", label: "All child brands", detail: "Backend rollup" },
                  ...childBrands.map((brand) => ({
                    id: brand.brand_id,
                    label: brandLabel(brand.name, brand.brand_id),
                  })),
                ]}
                selectedId={rollup ? "all" : selectedBrandId}
              />
            )}
          </Popover>
        )}

        {platform && (
          <Popover
            className="account-selector"
            label={accountLabel(platform)}
            value={
              accountState.isLoading
                ? "Loading…"
                : accountState.selectedAccountId === "all"
                  ? "All accounts"
                  : accountState.accounts.find(
                        (account) => account.account_id === accountState.selectedAccountId,
                      )?.display_name ?? "All accounts"
            }
          >
            {(close) => (
              <ScopePicker
                emptyLabel="No linked accounts"
                onSelect={(id) => {
                  selectAccount(platform, id === "all" ? "all" : Number(id));
                  close();
                }}
                options={[
                  { id: "all", label: "All accounts" },
                  ...accountState.accounts.map((account) => ({
                    id: String(account.account_id),
                    label: account.display_name,
                    detail: accountDetail(
                      platform,
                      account.external_id,
                      account.health_status,
                      account.last_synced_at,
                    ),
                  })),
                ]}
                selectedId={String(accountSelections[platform] ?? "all")}
              />
            )}
          </Popover>
        )}
      </div>

      <Popover className="profile-popover" label="Profile" value={user.email ?? `User ${user.user_id}`}>
        {(close) => (
          <div className="profile-card">
            <div className="profile-avatar"><UserRound size={20} /></div>
            <div>
              <strong>User {user.user_id}</strong>
              <span>{user.email ?? "Email unavailable"}</span>
            </div>
            <p><UserRound size={15} /> Role: {user.role.replaceAll("_", " ")}</p>
            <p><Check size={15} /> Signed in with Accumulate</p>
            <p><Building2 size={15} /> {brandLabel(selectedBrand?.name ?? null, selectedBrandId)}</p>
            <button
              className="profile-logout"
              disabled={loggingOut}
              onClick={() => {
                close();
                onLogout();
              }}
              type="button"
            >
              <LogOut size={16} /> {loggingOut ? "Signing out…" : "Sign out"}
            </button>
          </div>
        )}
      </Popover>
    </header>
  );
}
