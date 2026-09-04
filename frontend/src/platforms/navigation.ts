import type { Platform } from "../api";
import { PLATFORM_IDS } from "./catalog";

type NavigationCapabilities = {
  platforms: ReadonlyArray<{
    platform: Platform;
    navigation_available: boolean;
  }>;
};

export function previewPlatformsFromEnv(value: string | undefined): ReadonlySet<Platform> {
  const configured = (value ?? "")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter((item): item is Platform => PLATFORM_IDS.includes(item as Platform));
  return new Set(configured);
}

const LOCAL_PREVIEW_PLATFORMS = import.meta.env.DEV
  ? previewPlatformsFromEnv(import.meta.env.VITE_LOCAL_PREVIEW_PLATFORMS)
  : new Set<Platform>();

export function platformNavigationAvailable(
  platform: Platform,
  capabilities: NavigationCapabilities | null,
  previewPlatforms: ReadonlySet<Platform> = LOCAL_PREVIEW_PLATFORMS,
): boolean {
  const connected = capabilities?.platforms.find(
    (item) => item.platform === platform,
  )?.navigation_available ?? false;
  return connected || previewPlatforms.has(platform);
}
