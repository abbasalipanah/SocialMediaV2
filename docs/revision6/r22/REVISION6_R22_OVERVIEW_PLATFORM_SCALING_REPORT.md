# Revision 6 · R22 — Overview platform scaling and smooth trends

Date: `2026-08-10`

Status: `COMPLETE — V2 loopback certified`

Code commit: `d4d2f3b`

Release: `/opt/social-media-v2/releases/20260810T131931Z-r22overview`

## Outcome

The Overview no longer renders `Overall Organic Health`. Its KPI row contains exactly Total
Audience, Total Reach, Total Impressions, Total Interactions and Avg. Engagement. The bottom
platform summary contains the three connected platforms plus distinct planned slots for LinkedIn,
X and YouTube. A planned slot is filtered out automatically when its real connected platform is
present.

Channel Health uses only the actual `OverviewDashboard.platforms` response. Three or fewer
connected platforms remain static. Above three, a three-card circular window advances by one
platform every `4500 ms`, wraps after the last platform, exposes direct position controls and
pauses while hovered or keyboard-focused. Planned/demo cards never enter Channel Health.

Overview KPI, Channel Health and Performance Trend lines now use the same monotone visual curve
semantics as platform dashboards. The curve changes only SVG presentation: canonical samples,
dates and values are unchanged. Existing `1.25` non-scaling stroke and per-series `0.22 → 0`
gradient contracts remain intact.

## Verification

| Check | Result |
|---|---|
| Frontend typecheck | pass |
| Frontend unit/component tests | `35 passed` |
| Four-platform carousel fixture | pass; one-card step at `4500 ms`, no duplicate planned LinkedIn |
| Three-platform Playwright contract | pass; static three-card Channel Health |
| Full desktop/mobile Playwright | `17 passed`, `5 skipped` by explicit project applicability |
| Production build | pass; `2,537` modules transformed |
| Source/build/deployed Overview chunk SHA | `ccb020a49870cf42692310b270d91836f74cf2496de53d7c02007217f12320f0` |
| V2 API/web | active and healthy |
| V2 collection | service inactive, timer disabled |
| Protected-source guard | pass |

The deployed Overview artifact contains the carousel contract and contains no
`Overall Organic Health` string. No database, provider, collection, DNS, TLS, shared Nginx,
public route, SocialMedia, Accumulate or Performance Marketing mutation was performed.

## Rollback

Immediate rollback inputs remain:

- backend: `/opt/social-media-v2/releases/20260810T125436Z-r21logo/backend`
- frontend: `/opt/social-media-v2/releases/20260810T125436Z-r21logo/frontend`

Public cutover remains blocked by the user until the full application re-certification is complete.
