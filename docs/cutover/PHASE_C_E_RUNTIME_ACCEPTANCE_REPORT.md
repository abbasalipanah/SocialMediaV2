# Social Media V2 cutover — Phase C–E runtime acceptance

Date: `2026-08-13`

Status: `PHASE_C_E_COMPLETE / LOOPBACK_ACCEPTED / PUBLIC_CHANGE_NOT_AUTHORIZED`

## Outcome

The fresh full-data candidate is active on the standalone V2 loopback runtime. The final immutable
release is:

```text
/opt/social-media-v2/releases/20260813T111500Z-cutover-candidate-r2
```

After acceptance, the Home platform-summary presentation was updated and deployed as the immutable
V2-only release:

```text
/opt/social-media-v2/releases/20260813T114800Z-home-cards
```

It combines the inactive LinkedIn, X, and YouTube cards into one responsive `Coming soon` card with
all three logos and moves audience deltas into normal document flow so they cannot overlap the
engagement metric. The focused component suite passed `9/9`; full frontend passed `37/37`;
TypeScript and production build passed; desktop Playwright verified the four-card layout and exact
non-overlap geometry. The real loopback runtime matrix was then repeated with all roles, scopes,
surfaces and flows passing and zero console/request/server errors.

The current V2-only release is:

```text
/opt/social-media-v2/releases/20260813T115800Z-period-deltas
```

All dashboard increase/decrease values were independently audited for `7`, `30`, `90`, and `365`
day selections. For Overview, Facebook, Instagram, and TikTok, every returned `previous_value` was
cross-checked against a separate custom query for the immediately preceding adjacent equal-length
period, and every `delta_pct` was recomputed from those values. The real loopback matrix passed.
The UI's stale placeholder behavior was removed so a newly selected range can never temporarily
display the old range's KPI/delta values; a loading surface is shown until the matching response
arrives. Dedicated Home and platform transition tests passed.

The latest V2-only release is:

```text
/opt/social-media-v2/releases/20260813T143727Z-country-labels
```

The three connected platform cards and the combined `Coming soon` card now occupy four equal
desktop columns. PNG export now captures only the complete live dashboard `<main>` layout—including
the dashboard header/controls, every rendered dashboard section, and content below the viewport—
instead of drawing a synthetic six-metric canvas. The sidebar, top bar, and export popover are
excluded. A real `1920x1080` loopback browser run verified the four computed column widths and
downloaded PNG dimensions against the `<main>` capture-root dimensions.

All shared line/area trend cards now follow the Followers Trend presentation contract. Every
visible series uses a gradient derived from its own stroke color rather than leaving secondary
series transparent. Areas are anchored explicitly to zero, so positive values fill below the line
and negative values fill between the line and zero above it. The full loopback product matrix
verified every visible trend series across Facebook, Instagram, TikTok, and Stories.

PNG capture geometry now uses the live `<main>` client width and the real browser viewport width,
not the `scrollWidth` inflated by intentionally overflowing SVG axis labels. This preserves the
same responsive breakpoint, card columns, and chart bounds in the exported image. A long Instagram
Cover export was compared with the native main-layout capture; PNG dimensions retained one uniform
scale and every Recharts wrapper stayed within its card boundary.

Comment-community output is now privacy-redacted before it leaves the canonical dashboard query.
The ranking calculation still uses the internal author identity, but every delivered author label
is `Anonymous`. Standalone `@mentions` in comment text retain only their first and final username
characters with exactly three stars between them. The same projection feeds the API, browser, PNG,
and XLSX; the frontend also repeats the masking as a defense against stale or fixture responses.
The real loopback matrix verified this contract for all four date ranges and nested Overview
platform projections.

Bar-chart tooltips now disable the Recharts hover cursor layer. Hovering Performance Trends and
audience-demographic bars continues to show the value tooltip without drawing the grey vertical
background. Real-browser hover checks passed on Facebook, Instagram, and TikTok Cover surfaces.

Country dimensions now use full English country names instead of provider abbreviations. Top
Countries tables show a locally rendered circular flag beside each real country; aggregate values
such as `Others` are excluded from country rankings. The Instagram `Audience by Country` card uses
the same full names without flags. The real loopback product matrix verified names, table-only flag
placement, and circular computed geometry across every platform surface.

API health, readiness, and web return `200`; API and web remain bound only to `127.0.0.1:8026` and
`127.0.0.1:3026`. The active DB is `social_media_v2_shadow_20260813_1045`; media is owned by V2
under `/var/lib/social-media-v2/candidates/20260813_1045/media`.

V1 remained public and healthy throughout. Accumulate source/runtime, V1 source, shared Nginx,
public routing, and V1 timers were not changed.

## Quality and release gates

| Gate | Result |
|---|---|
| Backend | `158 passed`, `18` environment-gated skips |
| Ruff | passed |
| mypy | `141` source files, zero errors |
| Frontend | `47/47` |
| TypeScript + production build | passed |
| Playwright component/product matrix | `17 passed`, `5` applicability skips |
| Fake provider/retry/persistence matrix | `50/50` |
| R6 runtime artifact scan | `216` files, passed |
| Candidate env rollback/forward | passed |
| Final release rollback/forward | passed |

The Vite build retains its non-blocking large-chunk warning. No critical or high product defect was
found in Phase C–E.

## SSO and authorization

The V2 SSO secret now matches the active Accumulate runtime secret without changing Accumulate.
Canonical signed `aud=social_media`, `app_id=social_media`, `token_type=app_sso` launches passed for:

- Super Admin;
- Agency Admin;
- Agency Operator;
- Viewer;
- Viewer with signed `app_role=operator`.

Single Brand, child Brand, hidden parent, parent rollup, account scope, and cross-scope denial passed.
Expired tokens and JTI replay returned `401`. Consume responses were `303` with `no-store` and
`no-referrer`; the session cookie was Secure, HttpOnly, SameSite=Lax. Logout revoked the session.

Settings, Integrations, and AI limit authority matched the role contract. Final browser evidence had
zero console errors, same-origin request failures, and API `5xx` responses.

All `v2:session:*` and `v2:sso-jti:*` test records were deleted from the candidate after acceptance;
zero remain. Full credential parity was re-run after cleanup and passed.

This is a real-secret contract test through the V2 loopback runtime, not a real Accumulate sidebar
click. `SSO_LIVE_VERIFIED` therefore remains false until the final team change window.

## Product and XLSX acceptance

The runtime browser covered Overview; Facebook Cover/Page/Content/Audience; Instagram
Cover/Page/Content/Stories/Audience; TikTok Cover/Account/Content/Audience; 7/30/90/365-day ranges;
account selection; exact Brand, child and rollup scope; media; Settings; Integrations; AI history and
weekly limit; desktop/mobile layout; and error/empty behavior.

The active candidate also produced `14` XLSX workbooks entirely in memory: `88` sheets, `45` charts,
and zero persistent artifacts. Workbook structure and source projections passed read-only checks.

Machine-readable evidence is in `docs/cutover/phase_c_e_runtime_acceptance.json`.

## Gate state

```text
PHASE_C_COMPLETE=true
PHASE_D_COMPLETE=true
PHASE_E_COMPLETE=true
CANDIDATE_PROMOTED=true
SSO_LOOPBACK_CONTRACT_VERIFIED=true
SSO_LIVE_VERIFIED=false
V1_TRAFFIC_ACTIVE=true
V1_COLLECTION_ACTIVE=true
PUBLIC_V2_ACTIVE=false
READY_FOR_ACCUMULATE_SSO_HANDOFF=false
```
