export const PLATFORM_IDS = [
  "facebook",
  "instagram",
  "tiktok",
  "x",
  "linkedin",
  "youtube",
] as const;

export type PlatformId = (typeof PLATFORM_IDS)[number];
export type ConnectionProviderId = "meta" | "tiktok" | "x" | "linkedin" | "youtube";

export type PlatformDefinition = {
  id: PlatformId;
  label: string;
  route: string;
  description: string;
  connectionProvider: ConnectionProviderId;
};

export const PLATFORM_CATALOG = [
  {
    id: "facebook",
    label: "Facebook",
    route: "facebook",
    description: "Unified Facebook performance monitor.",
    connectionProvider: "meta",
  },
  {
    id: "instagram",
    label: "Instagram",
    route: "instagram",
    description: "Unified Instagram performance monitor.",
    connectionProvider: "meta",
  },
  {
    id: "tiktok",
    label: "TikTok",
    route: "tiktok",
    description: "Organic account, video and audience performance in one view.",
    connectionProvider: "tiktok",
  },
  {
    id: "x",
    label: "X",
    route: "x",
    description: "Organic profile and owned-post performance in one view.",
    connectionProvider: "x",
  },
  {
    id: "linkedin",
    label: "LinkedIn",
    route: "linkedin",
    description: "Organization, content and follower performance in one view.",
    connectionProvider: "linkedin",
  },
  {
    id: "youtube",
    label: "YouTube",
    route: "youtube",
    description: "Channel, video and audience performance in one view.",
    connectionProvider: "youtube",
  },
] as const satisfies ReadonlyArray<PlatformDefinition>;

export const PLATFORM_LABELS = Object.fromEntries(
  PLATFORM_CATALOG.map((platform) => [platform.id, platform.label]),
) as Record<PlatformId, string>;

export const PLATFORM_DESCRIPTIONS = Object.fromEntries(
  PLATFORM_CATALOG.map((platform) => [platform.id, platform.description]),
) as Record<PlatformId, string>;

export function platformDefinition(platform: PlatformId): PlatformDefinition {
  const definition = PLATFORM_CATALOG.find((item) => item.id === platform);
  if (!definition) throw new Error("platform_definition_not_found");
  return definition;
}
