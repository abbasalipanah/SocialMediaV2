import { z } from "zod";

import type { components } from "./openapi.generated";

export const platformSchema = z.enum(["facebook", "instagram", "tiktok"]);
export type Platform = z.infer<typeof platformSchema>;

export const authUserSchema = z.object({
  authenticated: z.literal(true),
  user_id: z.string(),
  email: z.string().email().nullable(),
  source_system: z.literal("accumulate").nullable(),
  brand_id: z.string(),
  role: z.string(),
  app_role: z.string().nullable(),
  access_mode: z.enum(["read", "write"]),
  settings_visible: z.boolean(),
  integrations_visible: z.boolean(),
  is_internal_staff: z.boolean(),
  expires_at: z.string(),
  revoked: z.literal(false),
});
export type AuthUser = z.infer<typeof authUserSchema> & components["schemas"]["AuthMeResponse"];

export const brandScopeSchema = z.object({
  requested_brand_id: z.string(),
  rollup: z.boolean(),
  resolved_brand_ids: z.array(z.string()),
});

export const workspaceBrandSchema = z.object({
  brand_id: z.string(),
  name: z.string().nullable(),
  parent_brand_id: z.string().nullable(),
  visibility: z.enum(["active", "hidden_parent"]),
  access_mode: z.enum(["read", "write"]).nullable(),
  role: z.string().nullable(),
});
export type WorkspaceBrand = z.infer<typeof workspaceBrandSchema>;

export const brandWorkspaceSchema = z.object({
  default_brand_id: z.string(),
  brands: z.array(workspaceBrandSchema),
  families: z.array(
    z.object({
      root_brand_id: z.string(),
      brand_ids: z.array(z.string()),
    }),
  ),
  scope: brandScopeSchema,
});
export type BrandWorkspace = z.infer<typeof brandWorkspaceSchema> &
  components["schemas"]["BrandWorkspace"];

export const capabilityStatusSchema = z.enum([
  "unsupported",
  "not_approved",
  "not_configured",
  "blocked_configuration",
  "manual_activation_required",
  "partial",
  "available",
]);
export const capabilitySchema = z.enum(["profile", "content", "comments", "audience"]);

export const workspaceCapabilitiesSchema = z.object({
  scope: brandScopeSchema,
  platforms: z.array(
    z.object({
      platform: platformSchema,
      capabilities: z.array(
        z.object({
          platform: platformSchema,
          capability: capabilitySchema,
          status: capabilityStatusSchema,
          reason: z.string(),
        }),
      ),
      linked_account_count: z.number().int().nonnegative(),
      navigation_available: z.boolean(),
    }),
  ),
  permissions: z.object({
    settings_visible: z.boolean(),
    integrations_visible: z.boolean(),
    internal_audit_visible: z.boolean(),
    rollup_available: z.boolean(),
    operation_mutation_available: z.boolean(),
    tiktok_connection_manage: z.boolean(),
    meta_connection_manage: z.boolean(),
  }),
  runtime: z.object({
    mode: z.enum([
      "development",
      "dormant",
      "staging",
      "standalone_ready",
      "active",
    ]),
    writes_enabled: z.boolean(),
    automated_schedule_available: z.boolean(),
  }),
});
export type WorkspaceCapabilities = z.infer<typeof workspaceCapabilitiesSchema> &
  components["schemas"]["WorkspaceCapabilitiesResponse"];

export const reportingAccountSchema = z.object({
  account_id: z.number().int(),
  brand_id: z.string(),
  platform: platformSchema,
  external_id: z.string(),
  display_name: z.string(),
  status: z.string(),
  connection_state: z.string(),
  health_status: z.string(),
  backfill_status: z.string(),
  link_status: z.string(),
  nightly_enabled: z.boolean(),
  last_synced_at: z.string().nullable(),
});
export type ReportingAccount = z.infer<typeof reportingAccountSchema> &
  components["schemas"]["ReportingAccount"];

export const platformAccountsSchema = z.object({
  meta: brandScopeSchema,
  platform: platformSchema,
  accounts: z.array(reportingAccountSchema),
});

export const metricIdSchema = z.enum([
  "followers",
  "following",
  "new_followers",
  "follows",
  "unfollows",
  "followers_net",
  "reach",
  "reach_paid",
  "reach_organic",
  "views",
  "views_paid",
  "views_organic",
  "interactions",
  "engagement_rate",
  "page_views",
  "profile_views",
  "website_clicks",
  "total_actions",
  "reactions",
  "media_count",
  "video_views_total",
  "video_views_change",
  "video_likes_total",
  "video_comments_total",
  "video_shares_total",
  "video_engagements_total",
  "video_engagement_rate",
]);
export type MetricId = z.infer<typeof metricIdSchema>;

export const dataStatusSchema = z.enum(["available", "partial", "unavailable"]);
export type DataStatus = z.infer<typeof dataStatusSchema>;

export const availabilityStatusSchema = z.enum([
  "available",
  "partial",
  "pending",
  "provider_unavailable",
  "unavailable",
]);

const dashboardMetaSchema = z.object({
  dashboard_id: z.string(),
  platform: platformSchema.nullable(),
  requested_brand_id: z.string(),
  rollup: z.boolean(),
  resolved_brand_ids: z.array(z.string()),
  resolved_account_ids: z.array(z.number().int()),
  date_range: z.object({
    start_on: z.string(),
    end_on: z.string(),
    key: z.string(),
  }),
  generated_at: z.string(),
  last_sync_at: z.string().nullable(),
  freshness: z.enum(["fresh", "stale", "outdated", "never_synced"]),
  observed_days: z.number().int().nonnegative(),
  expected_days: z.number().int().positive(),
  data_status: dataStatusSchema,
  warnings: z.array(z.string()),
});

export const dashboardMetricSchema = z.object({
  metric_id: metricIdSchema,
  value: z.number().nullable(),
  previous_value: z.number().nullable(),
  delta_pct: z.number().nullable(),
  semantic_type: z.enum(["snapshot", "flow", "cumulative", "ratio"]),
  unit: z.enum(["count", "ratio"]),
  data_status: dataStatusSchema,
  methodology: z.string().min(1),
  availability_reason: z.string().nullable(),
});
export type DashboardMetric = z.infer<typeof dashboardMetricSchema>;

const dashboardSeriesSchema = z.object({
  metric_id: metricIdSchema,
  semantic_type: z.enum(["snapshot", "flow", "cumulative", "ratio"]),
  points: z.array(z.object({ observed_on: z.string(), value: z.number() })),
  methodology: z.string().min(1),
});
export type DashboardSeries = z.infer<typeof dashboardSeriesSchema>;

const dashboardBreakdownSchema = z.object({
  metric_id: metricIdSchema,
  dimension: z.string(),
  items: z.array(
    z.object({
      key: z.string(),
      value: z.number(),
      percentage: z.number().nullable(),
    }),
  ),
});
export type DashboardBreakdown = z.infer<typeof dashboardBreakdownSchema>;

export const dashboardContentSchema = z.object({
  account_id: z.number().int(),
  external_content_id: z.string(),
  content_type: z.string(),
  permalink: z.string(),
  message: z.string(),
  media_url: z.string(),
  published_at: z.string().nullable(),
  likes_count: z.number().int(),
  comments_count: z.number().int(),
  shares_count: z.number().int(),
  interactions: z.number().int(),
  views: z.number().nullable(),
  reach: z.number().nullable(),
  cover_url: z.string().nullable(),
  thumbnail_url: z.string().nullable(),
  cover_candidates: z.array(z.string()),
  thumbnail_candidates: z.array(z.string()),
  media_url_candidates: z.array(z.string()),
  full_video_watched_rate: z.number().nullable(),
  total_time_watched: z.number().nullable(),
  average_time_watched: z.number().nullable(),
  data_status: dataStatusSchema,
});
export type DashboardContent = z.infer<typeof dashboardContentSchema>;

const communitySchema = z.object({
  total_comments: z.number().int().nonnegative(),
  answered_comments: z.number().int().nonnegative(),
  unanswered_comments: z.number().int().nonnegative(),
  comment_likes: z.number().int().nonnegative(),
  data_status: dataStatusSchema,
  top_commenters: z.array(z.object({
    name: z.string(),
    comments: z.number().int().nonnegative(),
    likes: z.number().int().nonnegative(),
  })),
  top_liked_comments: z.array(z.object({
    name: z.string(),
    comment: z.string(),
    likes: z.number().int().nonnegative(),
    replies: z.number().int().nonnegative(),
  })),
});

const dashboardNamedValueSchema = z.object({
  name: z.string(),
  value: z.number(),
});

export const dashboardContentSummarySchema = z.object({
  total: z.number().int().nonnegative(),
  by_type: z.array(dashboardNamedValueSchema),
  reach_by_type: z.array(dashboardNamedValueSchema),
  views_by_type: z.array(dashboardNamedValueSchema),
  data_status: dataStatusSchema,
});

const dashboardSourceValuesSchema = z.object({
  organic: z.number().nullable(),
  paid: z.number().nullable(),
  data_status: dataStatusSchema,
});

export const dashboardSourceBreakdownSchema = z.object({
  organic_only: z.boolean(),
  paid_available: z.boolean(),
  views: dashboardSourceValuesSchema.nullable(),
  reach: dashboardSourceValuesSchema.nullable(),
  data_status: dataStatusSchema,
}).nullable();

export const dashboardMetricMethodologySchema = z.object({
  follower_flow: z.string().min(1),
  engagement_rate: z.string().min(1),
  reach: z.string().min(1),
});

export const dashboardAudienceCapabilitiesSchema = z.object({
  source: z.string().nullable(),
  geo: availabilityStatusSchema,
  age_gender: availabilityStatusSchema,
  activity: availabilityStatusSchema,
});

const dashboardStorySummarySchema = z.object({
  count: z.number().int().nonnegative(),
  views: z.number().nullable(),
  reach: z.number().nullable(),
  interactions: z.number().nullable(),
  replies: z.number().nullable(),
  completion_rate: z.number().nullable(),
  data_status: dataStatusSchema,
});

const dashboardStoryTrendSchema = z.object({
  labels: z.array(z.string()),
  views: z.array(z.number().nullable()),
  reach: z.array(z.number().nullable()),
  data_status: dataStatusSchema,
});

const dashboardStoryNavigationSchema = z.object({
  taps_forward: z.number().nullable(),
  taps_back: z.number().nullable(),
  swipe_forward: z.number().nullable(),
  exits: z.number().nullable(),
  data_status: dataStatusSchema,
});

const dashboardStoryActionsSchema = z.object({
  replies: z.number().nullable(),
  shares: z.number().nullable(),
  profile_visits: z.number().nullable(),
  follows: z.number().nullable(),
  sticker_taps: z.number().nullable(),
  saves: z.number().nullable(),
  data_status: dataStatusSchema,
});

export const dashboardStoryItemSchema = z.object({
  content_id: z.string(),
  title: z.string(),
  cover_url: z.string(),
  permalink: z.string(),
  created_time: z.string().nullable(),
  views: z.number().nullable(),
  reach: z.number().nullable(),
  interactions: z.number().nullable(),
  replies: z.number().nullable(),
  shares: z.number().nullable(),
  profile_visits: z.number().nullable(),
  follows: z.number().nullable(),
  sticker_taps: z.number().nullable(),
  saves: z.number().nullable(),
  taps_forward: z.number().nullable(),
  taps_back: z.number().nullable(),
  swipe_forward: z.number().nullable(),
  exits: z.number().nullable(),
  navigation: z.number().nullable(),
  completion_rate: z.number().nullable(),
  data_status: dataStatusSchema,
});
export type DashboardStoryItem = z.infer<typeof dashboardStoryItemSchema>;

export const dashboardStoriesSchema = z.object({
  summary: dashboardStorySummarySchema,
  previous_summary: dashboardStorySummarySchema,
  trend: dashboardStoryTrendSchema,
  navigation: dashboardStoryNavigationSchema,
  actions: dashboardStoryActionsSchema,
  items: z.array(dashboardStoryItemSchema),
  data_status: dataStatusSchema,
}).nullable();
export type DashboardStories = Exclude<z.infer<typeof dashboardStoriesSchema>, null>;

export const platformDashboardSchema = z.object({
  meta: dashboardMetaSchema,
  metrics: z.array(dashboardMetricSchema),
  series: z.array(dashboardSeriesSchema),
  breakdowns: z.array(dashboardBreakdownSchema),
  content: z.array(dashboardContentSchema),
  community: communitySchema,
  top_hashtags: z.array(z.object({
    name: z.string(),
    count: z.number().int().nonnegative(),
  })),
  content_summary: dashboardContentSummarySchema,
  source_breakdown: dashboardSourceBreakdownSchema,
  metric_methodology: dashboardMetricMethodologySchema,
  audience_capabilities: dashboardAudienceCapabilitiesSchema,
  stories: dashboardStoriesSchema,
});
export type PlatformDashboard = z.infer<typeof platformDashboardSchema> &
  components["schemas"]["PlatformDashboard"];

export const overviewDashboardSchema = z.object({
  meta: dashboardMetaSchema,
  metrics: z.array(dashboardMetricSchema),
  platforms: z.array(platformDashboardSchema),
  content: z.array(dashboardContentSchema),
  community: communitySchema,
});
export type OverviewDashboard = z.infer<typeof overviewDashboardSchema> &
  components["schemas"]["OverviewDashboard"];

const settingsBrandSchema = z.object({
  brand_id: z.string(),
  name: z.string().nullable(),
  parent_brand_id: z.string().nullable(),
  visibility: z.string(),
  access_mode: z.string().nullable(),
  role: z.string().nullable(),
  linked_account_count: z.number().int().nonnegative(),
  last_sync_at: z.string().nullable(),
});
export type SettingsBrand = z.infer<typeof settingsBrandSchema>;

export const settingsBrandsSchema = z.object({
  meta: brandScopeSchema,
  items: z.array(settingsBrandSchema),
});
export type SettingsBrands = z.infer<typeof settingsBrandsSchema>;

export const socialAccountsSchema = z.object({
  meta: brandScopeSchema,
  items: z.array(reportingAccountSchema),
});
export type SocialAccounts = z.infer<typeof socialAccountsSchema>;

const brandLinkSchema = z.object({
  brand_id: z.string(),
  platform: platformSchema,
  account_id: z.number().int(),
  external_id: z.string(),
  display_name: z.string(),
  link_status: z.string(),
});
export type BrandLink = z.infer<typeof brandLinkSchema>;

export const brandLinksSchema = z.object({
  meta: brandScopeSchema,
  items: z.array(brandLinkSchema),
});
export type BrandLinks = z.infer<typeof brandLinksSchema>;

const connectionSchema = z.object({
  connection_id: z.number().int(),
  brand_id: z.string(),
  platform: platformSchema,
  state: z.string(),
  expires_at: z.string().nullable(),
  projected_at: z.string().nullable(),
});
export type ReportingConnection = z.infer<typeof connectionSchema>;

export const connectionsSchema = z.object({
  meta: brandScopeSchema,
  items: z.array(connectionSchema),
});
export type ReportingConnections = z.infer<typeof connectionsSchema>;

const syncJobSchema = z.object({
  job_id: z.number().int(),
  brand_id: z.string(),
  account_id: z.number().int().nullable(),
  platform: platformSchema,
  stage: z.string(),
  status: z.string(),
  scheduled_for: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
  error_code: z.string().nullable(),
});
export type ReportingSyncJob = z.infer<typeof syncJobSchema>;

export const syncJobsSchema = z.object({
  meta: brandScopeSchema,
  items: z.array(syncJobSchema),
});
export type ReportingSyncJobs = z.infer<typeof syncJobsSchema>;

export const insightSchema = z.object({
  insight_id: z.number().int(),
  brand_id: z.string(),
  status: z.string(),
  date_from: z.string().nullable(),
  date_to: z.string().nullable(),
  summary: z.string().nullable(),
  recommendations: z.string().nullable(),
  connector_analysis: z.string().nullable(),
  anomalies: z.string().nullable(),
  platform_evaluations: z.string().nullable(),
  model: z.string().nullable(),
  error_message: z.string().nullable(),
  created_by_user_sub: z.string().nullable(),
  created_at: z.string(),
  completed_at: z.string().nullable(),
});
export type ReportingInsight = z.infer<typeof insightSchema>;

export const insightsSchema = z.object({
  meta: brandScopeSchema,
  items: z.array(insightSchema),
});

export const aiSummaryLimitSchema = z.object({
  provider_configured: z.boolean(),
  can_generate: z.boolean(),
  reason: z.string(),
  weekly_limit: z.number().int().positive(),
  used: z.number().int().nonnegative(),
  remaining: z.number().int().nonnegative(),
  window_days: z.number().int().positive(),
  last_generated_at: z.string().nullable(),
  next_available_at: z.string().nullable(),
  generation_in_progress: z.boolean(),
});
export type AiSummaryLimit = z.infer<typeof aiSummaryLimitSchema>;

export const readinessSchema = z.object({
  status: z.string(),
  runtime_mode: z.string(),
  writes_enabled: z.boolean(),
  database_configured: z.boolean(),
  scope: brandScopeSchema.nullable().optional(),
  platforms: z
    .array(
      z.object({
        platform: platformSchema,
        account_count: z.number().int().nonnegative(),
        last_sync_at: z.string().nullable(),
        pending_job_count: z.number().int().nonnegative(),
      }),
    )
    .default([]),
});
export type OperationsReadiness = z.infer<typeof readinessSchema>;

export const auditSchema = z.object({
  meta: brandScopeSchema,
  status: z.string(),
  reason: z.string(),
  items: z.array(z.unknown()),
});
export type ReportingAudit = z.infer<typeof auditSchema>;

export const tiktokConnectionSchema = z.object({
  meta: brandScopeSchema,
  state: z.string(),
  connection: connectionSchema.nullable(),
  capabilities: z.array(
    z.object({
      platform: platformSchema,
      capability: capabilitySchema,
      status: capabilityStatusSchema,
      reason: z.string(),
    }),
  ),
  checked_at: z.string(),
});
export type TikTokConnection = z.infer<typeof tiktokConnectionSchema>;

export const tiktokActivationReadinessSchema = z.object({
  handoff_ready: z.literal(true),
  brand_id: z.string(),
  launch_target: z.literal("tiktok_owner_activation"),
  fresh_until: z.string(),
  runtime_mode: z.string(),
  writes_enabled: z.boolean(),
  connection_state: z.string(),
  oauth_start_available: z.boolean(),
  reason: z.string(),
  checked_at: z.string(),
});
export type TikTokActivationReadiness = z.infer<typeof tiktokActivationReadinessSchema> &
  components["schemas"]["TikTokActivationReadinessResponse"];

export const tiktokSelfServiceReadinessSchema = z.object({
  brand_id: z.string(),
  can_manage: z.boolean(),
  connection_state: z.string(),
  linked_account_count: z.number().int().nonnegative(),
  oauth_start_available: z.boolean(),
  reason: z.string(),
  runtime_mode: z.string(),
  writes_enabled: z.boolean(),
  checked_at: z.string(),
});
export type TikTokSelfServiceReadiness = z.infer<typeof tiktokSelfServiceReadinessSchema>;

export const tiktokSelfServiceStartSchema = z.object({
  authorization_url: z.string().url(),
  expires_at: z.string(),
});
export type TikTokSelfServiceStart = z.infer<typeof tiktokSelfServiceStartSchema>;

export const metaDiscoverySchema = z.object({
  connection_id: z.number().int().positive(),
  platform: z.enum(["facebook", "instagram"]),
  external_id: z.string(),
  display_name: z.string(),
  status: z.string(),
});
export type MetaDiscovery = z.infer<typeof metaDiscoverySchema>;

export const metaLinkedAccountSchema = z.object({
  platform: z.enum(["facebook", "instagram"]),
  external_id: z.string(),
  display_name: z.string(),
});

export const metaSelfServiceReadinessSchema = z.object({
  brand_id: z.string(),
  can_manage: z.boolean(),
  connection_state: z.string(),
  facebook_linked_count: z.number().int().nonnegative(),
  instagram_linked_count: z.number().int().nonnegative(),
  linked_accounts: z.array(metaLinkedAccountSchema),
  discoveries: z.array(metaDiscoverySchema),
  oauth_start_available: z.boolean(),
  reason: z.string(),
  runtime_mode: z.string(),
  writes_enabled: z.boolean(),
  checked_at: z.string(),
});
export type MetaSelfServiceReadiness = z.infer<typeof metaSelfServiceReadinessSchema>;

export const metaSelfServiceStartSchema = z.object({
  authorization_url: z.string().url(),
  expires_at: z.string(),
});

export const metaLinkResponseSchema = z.object({
  connection_id: z.number().int().positive(),
  linked_count: z.number().int().positive(),
  connection_state: z.literal("connected"),
});

export const reportJobSchema = z.object({
  job_id: z.string().min(1),
  state: z.enum(["queued", "running", "ready", "failed"]),
  progress: z.number().int().min(0).max(100),
  stage: z.string(),
  filename: z.string().nullable(),
  created_at: z.string(),
  expires_at: z.string().nullable(),
  error_code: z.string().nullable(),
});
export type ReportJob = z.infer<typeof reportJobSchema> &
  components["schemas"]["ReportJobResponse"];

export const apiProblemSchema = z.object({
  detail: z.unknown().optional(),
});
