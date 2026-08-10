# Revision 6 / R17 — Full-data isolated loopback certification

Date: `2026-08-10`

Status: `FULL_DATA_LOOPBACK_VERIFIED / PUBLIC_CUTOVER_NOT_AUTHORIZED`

## Outcome

Social Media V2 now runs on its independent, loopback-only runtime with the complete migrated
customer scope. The active immutable release is
`/opt/social-media-v2/releases/20260810T090500Z-4fb9529`, built from Git commit `4fb9529` on
`main`. API and web remain bound only to `127.0.0.1:8026` and `127.0.0.1:3026`.

The active data target is the V2-owned `social_media_v2_shadow_20260810_0745` PostgreSQL database
and `/var/lib/social-media-v2-shadow-20260810_0745/media` media root. The pre-promotion Pine-only
staging environment remains available at
`/etc/social-media-v2/production.env.pre-full-shadow-20260810T090700Z` for exact rollback. Secret
values are not included in this report or repository.

No DNS, TLS, shared Nginx, Accumulate, SocialMedia V1, performance_marketing, public routing,
provider activation, collector, timer, or scheduler change was made.

## Full migration and parity evidence

| Surface | Verified count |
|---|---:|
| Brands | 67 |
| Social assets | 91 |
| Daily metric rows | 1,493,502 |
| Content items | 6,234 |
| Comments | 3,362 |
| DB-referenced media rows/files | 6,101 |
| Linked social accounts | 97 |
| Platform connections | 71 |
| Meta accounts | 358 |
| Stored AI summaries | 6 |

The source import was previously verified by a repeatable-read, transaction-read-only exact row
comparison and SHA-256 comparison of all 6,101 DB-referenced media files. Credential migration
sealed 167 access/refresh values with the target AES-256-GCM vault; plaintext equivalence,
expiry/revocation state, unique nonces, 71 connection projections, and source/target read-only
parity were verified without logging credential material.

Changing media ownership did not change file content. All 6,101 files are now
`social-media-v2:social-media-v2` mode `0640`; all 118 directories are mode `0750`. Real browser
requests for Facebook, Instagram, Instagram Stories, and TikTok media passed after this runtime
permission gate.

## Metric and dashboard coverage

The immutable legacy rows remain unchanged in the migration DB. The V2 reporting read boundary
classifies all 168 platform/metric pairs, 124 distinct raw metric identifiers, and 15 breakdown
dimensions. Canonical rows pass directly; audience and supported operational dimensions are
typed; TikTok content rows produce canonical daily video totals; content-level values already
projected into `content_items` are not duplicated; known dashboard-unused legacy diagnostics are
explicitly classified; unknown future metrics cannot crash the dashboard.

Final active-DB coverage executed read-only and passed:

- 67 Brand scopes;
- 201 platform dashboards (Facebook, Instagram, TikTok per Brand);
- 67 Overview dashboards;
- 41 Brands with metric values in the selected last-30-day window;
- 34 Brands with Instagram Story items in that window;
- exact single-Brand scope retained for every non-rollup query;
- every platform response contained its six-KPI contract, including honest unavailable values.

## SSO, role, AI, frontend, and browser evidence

Headless Chromium exercised the final release through `127.0.0.1:3026` and recorded zero API,
request, or console failures for:

- Accumulate `viewer` + signed `app_role=operator`: Settings hidden, Integrations visible;
- `agency_admin`: Settings and Integrations visible, explicit Hilton parent rollup resolved to
  Brands `19`, `28`, `29`, and `30`;
- `super_admin`: Settings and Integrations visible;
- Pine Beach Belek data scope and an empty Brand scope;
- Social Media Overview, Facebook, Instagram, Instagram Stories, and TikTok;
- exactly six KPI cards in the first platform section;
- Instagram Story gallery and History;
- AI Summary history plus backend-authoritative rolling 7-day/one-generation limit;
- authenticated local media and logout.

Exact `shadow-*` smoke sessions and their replay hashes were deleted after each final-runtime
browser pass. The disposable database `social_media_v2_shadow_e2e_20260810_0815` was dropped only
after its active connection count was verified as zero.

## Release, rollback, recovery, and soak

1. Commit `4fb9529` was pushed to `origin/main` with a clean worktree.
2. The immutable release was built, dependency hashes enforced, migrations checked, symlinks
   atomically switched, and API/web health verified on the Pine-only staging DB.
3. The root-owned runtime env was atomically promoted to the full-data DB/media target. API
   health and readiness passed.
4. The env was atomically rolled back to the retained Pine staging target. Health passed with
   exactly 1 Brand and 80,519 metric rows.
5. The same release was promoted forward to the full-data target again. Full browser E2E and the
   67-Brand coverage scan passed again.
6. Twelve consecutive soak probes passed: API `200`, loopback web `200`, public V1 root response
   unchanged at `307`, API/web services active.

Final state:

- `social-media-v2-api.service`: active/enabled;
- `social-media-v2-web.service`: active/enabled;
- `social-media-v2-collection.service`: inactive/disabled;
- `social-media-v2-collection.timer`: inactive/disabled;
- Meta account/collection gates: false;
- TikTok account/collection gates: false;
- worker schedule gate: false;
- health: `200`, `status=ok`;
- readiness: `200`, `runtime_mode=staging`, DB configured;
- release-window API/web journal warnings: none.

Rollback remains a V2-only operation: atomically restore the retained root-owned env to
`/etc/social-media-v2/production.env`, restart only `social-media-v2-api.service`, and verify
`/api/health` plus `/api/operations/readiness`. It does not require or authorize a change to any
protected project or public route.

## Quality gates

- backend: `147 passed`, `18` environment-gated skips;
- real full-data PostgreSQL coverage: passed independently of the skipped disposable test inputs;
- frontend: `29 passed`;
- TypeScript: passed;
- production Vite build: passed;
- Ruff on changed runtime/migration/verifier surfaces: passed;
- R6 runtime artifact gate: passed;
- repository secret leak guard: passed, including `backend/scripts`;
- protected source write guard: passed before and after release;
- Git whitespace/diff checks: passed.

## Public cutover gate

The current public Social Media V1 route remains unchanged and operational. R17 does not grant
permission to change DNS, issue/install TLS, edit/reload shared Nginx, or route public traffic to
V2. Those operations remain a separate final gate and require a new explicit user approval after
the user accepts this full-data loopback result.
