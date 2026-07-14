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
  access_mode: z.enum(["read", "write"]),
  settings_visible: z.boolean(),
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
    internal_audit_visible: z.boolean(),
    rollup_available: z.boolean(),
    operation_mutation_available: z.boolean(),
  }),
  runtime: z.object({
    mode: z.enum([
      "development",
      "dormant",
      "cutover_read_only",
      "cutover_credential_migration",
      "cutover_canary",
      "cutover_control_plane_drain",
      "cutover_activation",
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

export const apiProblemSchema = z.object({
  detail: z.unknown().optional(),
});
