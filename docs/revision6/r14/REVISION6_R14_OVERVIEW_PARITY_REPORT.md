# Revision 6 / R14 — Executive Overview and stored AI opportunities report

Date: `2026-08-09`

## Outcome

Social Media Overview is a reachable V2-owned product surface at both `/` (Home) and
`/overview`. Its main content follows the user-approved executive Social Media layout while the
existing V2 sidebar, topbar, footer, Brand scope, SSO, and API boundaries remain intact.

All writes stayed inside `/home/api/colab_scripts/SocialMediadownstream`. No production provider,
database, schedule, worker, OAuth gate, live route, or protected-project runtime was changed.

## Product contract

The KPI row has exactly six cards, in order:

1. Overall Organic Health
2. Total Audience
3. Total Reach
4. Total Impressions
5. Total Interactions
6. Avg. Engagement

The seven canonical surfaces are What Changed?, Channel Health, Performance Trend, Content
Snapshot, Top Performing Content, Alerts & Opportunities, and the three-card platform summary.
Only Instagram, Facebook, and TikTok are present; LinkedIn, X, and YouTube placeholders were not
added.

`Total Impressions` displays the normalized `views` slot without claiming a new provider metric.
Avg. Engagement is `interactions / reach`; its comparison is the percentage-point difference from
the previous period. Invalid denominators remain unavailable.

Overall Organic Health evaluates the available audience, reach, interaction, and engagement
comparison signals: at least 75% non-declining is Healthy, at least 50% is Stable, otherwise Needs
Attention; fewer than two comparable signals is Limited Data. What Changed? selects the largest
absolute comparable delta per platform. Channel Health is Attention when one of its audience or
interaction signals is at most -5%, Growing when one is at least +2% without that decline, and
Stable otherwise.

Performance Trend exposes Performance, Reach, Engagement, and Audience views and uses the full
selected-period backend series. Content Snapshot groups real selected-period interactions by
content type; four or more minor types are aggregated into an exact Other row. Top Performing
Content ranks the three real content records by interactions and derives content engagement only
when reach is nonzero.

## AI insight boundary

The current Accumulate implementation was inspected read-only. It ranks the four largest metric
deltas, calls its AI summary endpoint, stores structured output, and has a deterministic fallback.
V2 intentionally does not inherit this generation or mutation path.

The source Pine Beach Brand has one completed stored insight for `2026-03-14` through
`2026-04-13`. The importer now copies only its strategic summary and action recommendations into
the isolated V2-local DB. Source access was forced to PostgreSQL `transaction_read_only=on`.
Credentials, OAuth state, provider settings, LLM configuration, raw metric snapshots, connector
analysis, anomalies, and platform evaluations are not copied.

Alerts & Opportunities reads up to three structured stored recommendations and visibly includes
the stored report period. It does not present them as a freshly generated current-period result.
The shared Dialog shows the summary and all recommendations with focus trap, Escape close,
backdrop close, and focus return. Opening the page or dialog performs no AI generation or write.

## Route and navigation behavior

- Home links to `/` and is the only visible navigation entry for Overview.
- `/overview` remains a direct deep-link but is not duplicated in the Social Media tree.
- Unauthorized Settings or Integrations deep-links fail closed to `/overview`.
- Existing sidebar/topbar/footer styling and role-driven Settings/Integrations visibility remain
  unchanged.

## Pine Beach local evidence

The isolated V2 local session returned an available `/api/dashboards/overview` payload for Pine
Beach Belek with three resolved accounts and expected aggregate metrics. Headless Chromium opened
the real Pine runtime and verified:

- Pine Beach Belek Brand scope;
- exactly six KPI labels;
- all seven canonical surfaces;
- exactly three platform summary cards;
- one visible Home entry and no duplicate Overview sidebar entry;
- three stored AI recommendation cards and their stored period;
- stored-insight dialog content;
- no horizontal overflow at 1680px or 390px;
- zero application HTTP or console errors.

The refreshed V2-local snapshot contains `80,519` metrics, `395` content rows, `611` comments,
`389` verified media rows, and `1` stored insight.

## Verification

- Frontend Vitest: `28 passed`.
- Backend pytest: `139 passed`, `17` environment-gated PostgreSQL tests skipped.
- Frontend TypeScript: passed.
- Frontend production build: passed.
- Overview Playwright: desktop passed, mobile expected project-specific skip.
- Pine Beach V2-local API/browser smoke: passed.
- Importer Ruff check: passed.
- Frontend/backend data contract tests: passed.
- `git diff --check`: passed.
- Protected source-write guard: passed.

## External work

R14 does not activate a live runtime. R8 still requires owner-provided public origin, trusted
issuer, provider credentials/approval, V2 staging infrastructure, and an authorized change
window.

## Completion state

- `R14_OVERVIEW_PARITY_COMPLETE=true`
- `STANDALONE_PRODUCT_COMPLETE=true`
- `STANDALONE_RUNTIME_COMPLETE=false`
- `READY_FOR_ACCUMULATE_SSO_HANDOFF=false`
- `SSO_LIVE_VERIFIED=false`
- `TIKTOK_CONNECTION_VERIFIED=false`
