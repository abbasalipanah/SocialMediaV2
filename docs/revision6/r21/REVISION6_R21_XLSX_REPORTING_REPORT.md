# Revision 6 · R21 — Queued transient XLSX reporting

Date: `2026-08-10`

Status: `COMPLETE — V2 loopback certified`

Release: `/opt/social-media-v2/releases/20260810T125436Z-r21logo`
Code commit: `38440a1`
Canonical logo correction commit: `cb2354a`

## Outcome

Social Media V2 now exports the active Overview, Facebook, Instagram or TikTok dashboard as
either the existing PNG snapshot or a professional XLSX workbook. XLSX creation runs in a
bounded single-worker in-process queue and reports `queued/running/ready/failed`, a current
stage and monotonic `0-100` progress to the frontend.

The supplied `docs/Accumulate_Instagram_Report_Prototype_v2.xlsx` was inspected read-only and
used only as a visual/structural reference. Its demo values, formulas, chart formatting and
Microsoft rich in-cell image representation are not runtime inputs.

## Scope and safety

- Only `/home/api/colab_scripts/SocialMediadownstream` and the isolated
  `/opt/social-media-v2` loopback release were changed.
- `/home/api/colab_scripts/SocialMedia`, `/home/api/colab_scripts/Accumulate` and
  `/home/api/colab_scripts/performance_marketing` remained read-only. The source baseline guard
  passed before and during release.
- No provider request, collection, sync, AI generation, DNS, TLS, shared Nginx or public route
  change was made.
- The XLSX query path reads the existing canonical dashboard projection. It performs no DB write
  and does not create a second metric calculation path.
- V2 collection remains disabled: `social-media-v2-collection.timer=disabled` and
  `social-media-v2-collection.service=inactive` after release.

## API and queue contract

| Endpoint | Boundary | Purpose |
|---|---|---|
| `POST /api/reports/xlsx` | command | Validate scope and enqueue one workbook |
| `GET /api/reports/xlsx/{job_id}` | query | Return state, stage and percentage |
| `POST /api/reports/xlsx/{job_id}/download` | command | Consume the ready workbook exactly once |

Every job is bound to the authenticated session hash and requested Brand scope. Status and
download revalidate both session ownership and current Brand authority. Unknown/cross-session
job IDs return the same not-found contract. POST endpoints require the same origin.

Runtime limits are one worker, at most 16 retained jobs, at most two active jobs per owner,
25 MiB per workbook and a ten-minute ready/failed TTL. Workbook bytes exist only in memory.
The first successful download consumes the job immediately; the TTL timer removes an
undownloaded result. No runtime `.xlsx` is written to DB, repository or filesystem.

## Workbook structure

All exports start with `Report Info`, containing the standard Accumulate logo derived exactly
from `docs/accumulate-sidebar-logo.svg`, Brand, account, surface, active tab, scope,
reporting/comparison periods, generated/last-sync times, freshness, coverage, data status and
export version. XlsxWriter cannot embed SVG directly, so the workbook packages the pinned
transparent PNG derivative at `frontend/public/branding/accumulate-sidebar-logo.png`; the legacy
`accumulate-dark.png` asset is not a report-logo fallback.

- Overview: Overview cards/chart, per-platform summary, top content, community and dictionary.
- Platform Cover: Page/Account, Content, optional Instagram Stories, Audience and their raw data
  tables.
- Focused tab: only that tab's presentation sheet plus the necessary raw data and dictionary.
- Large content, story history, breakdown and community results use filterable tables and frozen
  panes rather than one worksheet per small card.

Native Excel charts use the dashboard palette and `1.25` line width. Follower flow is ordered
and colored as Follows blue, Unfollows orange and Net teal. Views/reach, organic/paid and TikTok
interaction series use the same canonical semantics as the frontend. Story Evolution reads the
structured story trend, not the generic Instagram daily series. Overview Performance Trend has
distinct Instagram/Facebook/TikTok data columns, avoiding duplicate metric-column collisions.

Workbooks disable automatic string-to-formula and string-to-URL conversion. OOXML verification
confirmed no worksheet formulas, macros, external links, `#REF!` or `#VALUE!` values. The logo
is a standard Excel drawing image rather than a compatibility-dependent in-cell rich value.

## Frontend behavior

The dashboard download control opens an accessible PNG/XLSX menu. Excel selection sends the
exact Brand, rollup, account, tab and dashboard start/end dates. While the job runs, the menu is
kept visible and shows its stage, percentage and a progress element. When ready, the same-origin
download starts automatically and the UI states that the temporary file is removed after
download. Queue saturation, size limit and generation errors have bounded user-facing messages.

## Verification evidence

| Check | Result |
|---|---|
| Backend Ruff | pass |
| Backend tests | `151 passed`, `18 skipped` only for unavailable external PostgreSQL fixtures |
| Report manager/API/OOXML tests | pass |
| Frontend typecheck | pass |
| Frontend tests | `34 passed` |
| Frontend Playwright | `17 passed`, `5 skipped` by explicit project applicability |
| Frontend production build | pass; `ReportExport` emitted as a production chunk |
| Deterministic OpenAPI + generated TypeScript | pass/current |
| Backend wheel build | pass; report modules included |
| Secret/vocabulary guards | pass |
| Protected-source write guard | pass |
| Canonical/deployed logo SHA-256 | `46e27509774512dccdc506ccd74ff80c9cd38d4d5096ebe31034480b54e801a7` |
| V2 API/web health | active and healthy; no warning/error journal entries during release |
| Unauthenticated runtime report create | `401`, fail-closed |

The V2-owned database was queried read-only with the deployed code for Pine Beach Belek,
Instagram account `1412`, period `2026-07-11` through `2026-08-09`:

- Stories focused workbook: 17 metric series, 16 stories, 6 sheets, one native chart and a
  standard embedded logo.
- Cover workbook: 29 content rows, 16 stories, 12 sheets, 8 native charts, 107,069 bytes, embedded
  logo, and zero `#REF!`/`#VALUE!` tokens.

Both were constructed and inspected in memory; no diagnostic workbook was retained.

## Release and rollback

The upgrade used an exact V2 database-name guard accepting only `social_media_v2_staging` or a
timestamped `social_media_v2_shadow_YYYYMMDD_HHMM` database. It then built an isolated release,
installed hash-locked dependencies (including XlsxWriter), atomically switched the backend and
frontend symlinks, restarted only the two V2 loopback services and passed all health probes.

Rollback inputs remain intact:

- immediate rollback backend: `/opt/social-media-v2/releases/20260810T122500Z-r21xlsx-final/backend`
- immediate rollback frontend: `/opt/social-media-v2/releases/20260810T122500Z-r21xlsx-final/frontend`
- pre-R21 backend: `/opt/social-media-v2/releases/20260810T090500Z-4fb9529/backend`
- pre-R21 frontend: `/opt/social-media-v2/releases/20260810T112200Z-c2dd2fc/frontend`

No DNS/TLS/public cutover is authorized by R21. Those steps remain blocked until the user confirms
the full application—not only XLSX reporting—is complete.
