# Revision 6 / R20 — Overview trend and area parity

Date: `2026-08-10`

Status: `LOOPBACK_OVERVIEW_TREND_PARITY_VERIFIED / PUBLIC_CUTOVER_NOT_AUTHORIZED`

## Outcome

The Overview surface now uses the same thin-line and soft area-fill language as the platform
dashboards. This applies to KPI mini sparklines, Channel Health mini trends, and the main
Performance Trend.

The binding rendering contract is:

- mini and Performance line width: `1.25` with non-scaling stroke;
- area gradient: `0.22` top opacity to `0` bottom opacity;
- Performance Instagram: `#ec4899`;
- Performance Facebook: `#2563eb`;
- Performance TikTok: `#111827`;
- every available Performance platform series owns its matching area fill;
- grid lines remain `0.55` and low contrast.

Existing Inter typography, near-black copy colors, cards, tabs, data semantics, sidebar, topbar,
and footer were preserved.

## Verification

- frontend component/contract tests: `33 passed`;
- TypeScript: passed;
- production Vite build: passed (`2,536` modules, `24` output files);
- Playwright desktop/mobile suite: `17 passed`, `5` expected project-conditional skips;
- Overview browser contract: three platform paths, three area fills, exact colors and `1.25`
  stroke width;
- real Pine Beach local Overview Performance Trend: manually inspected;
- isolated full-data signed SSO browser: viewer/operator, agency admin and super admin passed;
- browser brands: data, parent rollup and empty Brand passed;
- browser/API errors: `0`;
- secret leak guard: passed;
- protected source write guard: passed;
- Git diff/whitespace check: passed.

## Isolated loopback release

Code commit `c2dd2fc` was pushed to `origin/main`. Only the V2 frontend was promoted:

- active frontend: `/opt/social-media-v2/releases/20260810T112200Z-c2dd2fc/frontend`;
- frontend rollback target: `/opt/social-media-v2/releases/20260810T111200Z-e7f74bb/frontend`;
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

R20 does not authorize DNS/TLS or public cutover. Those operations remain pending until all
remaining product work is complete and the user gives a separate explicit approval.
