# Revision 6 / R19 — V1 chart palette parity

Date: `2026-08-10`

Status: `LOOPBACK_CHART_PALETTE_PARITY_VERIFIED / PUBLIC_CUTOVER_NOT_AUTHORIZED`

## Outcome

V2's active Facebook, Instagram, and TikTok dashboard charts now use one shared, test-locked V1
data-series palette. The concrete mismatch reported by the user is removed: `Unfollows` is orange
instead of platform-specific pink/red, while `Follows` remains blue and `Net` remains teal.

Follower flow presentation now also matches V1 semantics:

- legend order: `Follows`, `Unfollows`, `Net`;
- provider/DB `unfollows` counts remain unchanged and non-negative;
- chart-only display uses `-abs(value)` for Unfollows;
- subtitle totals show Follows, absolute Unfollows, and native Net values;
- line stroke width is `1.25`;
- first-series gradient is `0.22 → 0` and bar opacity is `0.82`.

Performance, Views/Reach, organic/paid source, engagement trend, KPI accent, and relevant donut
colors were aligned to the same V1 mapping. The shared contract lives in
`frontend/src/features/dashboard/visualPalette.ts`; platform components no longer define divergent
follower-flow palettes.

## Verification

- frontend component/contract tests: `33 passed`;
- TypeScript: passed;
- production Vite build: passed (`2,536` modules, `24` output files);
- Playwright desktop/mobile suite: `17 passed`, `5` expected project-conditional skips;
- browser assertions on all three platform Covers: three follower-flow paths, exact colors,
  `1.25` stroke width, and exact legend order;
- real Pine Beach local V2 screenshot: manually inspected, including orange negative Unfollows;
- isolated full-data signed SSO browser: viewer/operator, agency admin and super admin passed;
- browser brands: data, parent rollup and empty Brand passed;
- browser surfaces: Facebook, Instagram Stories and TikTok passed;
- browser/API errors: `0`;
- secret leak guard: passed;
- protected source write guard: passed;
- Git diff/whitespace check: passed.

## Isolated loopback release

Code commit `e7f74bb` was pushed to `origin/main`. Only the V2 frontend was promoted:

- active frontend: `/opt/social-media-v2/releases/20260810T111200Z-e7f74bb/frontend`;
- frontend rollback target: `/opt/social-media-v2/releases/20260810T104500Z-5066eb7/frontend`;
- unchanged backend: `/opt/social-media-v2/releases/20260810T090500Z-4fb9529/backend`;
- web: `127.0.0.1:3026`, healthy and enabled;
- API: `127.0.0.1:8026`, healthy and enabled;
- built/released SHA-256 artifact set: exact match across all `24` files;
- frontend-only rollback and forward recovery: passed;
- final API/web probes: `5/5` passed;
- web journal warning-or-higher lines in the release window: `0`;
- collection service/timer: inactive and disabled.

## Protected systems and public gate

SocialMedia V1, Accumulate, and performance_marketing were read only. Their source baseline guard
passed after the release. No backend, V2 DB/media, credential, provider gate, collector, timer,
public route, DNS, TLS, or shared Nginx change was made.

R19 does not authorize DNS/TLS or public cutover. Those operations remain explicitly pending and
require a separate future user approval after all remaining product work is complete.
