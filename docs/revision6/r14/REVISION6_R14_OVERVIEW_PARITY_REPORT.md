# Revision 6 / R14 — Overview surface parity report

Date: `2026-08-09`

## Outcome

Social Media Overview is now a reachable V2-owned product surface at both `/` (Home) and
`/overview`. The main content follows the read-only Accumulate Social Media Dashboard information
architecture while the existing V2 sidebar, topbar, footer, Brand scope, SSO and API boundaries
remain intact.

All writes stayed inside `/home/api/colab_scripts/SocialMediadownstream`. No production provider,
database, schedule, worker, OAuth gate, live route, or protected-project runtime was changed.

## Product contract

The KPI row has exactly six cards, in order:

1. Total Audience
2. Total Reach
3. Total Impressions
4. Total Interactions
5. Avg. Engagement
6. Activity Score

The page has the seven canonical sections: Audience Growth, Cross-Channel, Content Type,
AI Insights, Action Breakdown, Top Performing Posts, and Platform Breakdown. Platform Breakdown
contains only Facebook, Instagram, and TikTok.

`Total Impressions` displays the existing normalized `views` slot, matching the canonical
fallback without claiming a new provider metric. Avg. Engagement is `interactions / reach`.
Activity Score uses the documented canonical display formula. Invalid denominators remain
unavailable. Overview Saves is not present in the current typed backend contract, so the UI shows
`—` instead of a synthetic zero.

Cross-Channel no longer truncates a 30-day selection to seven samples. The full selected period is
shown with at most 12 contiguous aggregate buckets. Top Performing Posts uses impressions/views,
interactions, and an explicitly derived interactions/reach rate.

AI Insights opens only the stored read endpoint result. Opening the dialog performs no AI
generation or write. The shared Dialog primitive provides focus trap, Escape close, backdrop
close, and focus return.

## Route and navigation behavior

- Home links to `/` and is the only visible navigation entry for Overview.
- `/overview` remains a direct deep-link but is not duplicated in the Social Media tree.
- The final user correction explicitly prohibits simultaneous Home and Overview menu entries.
- Unauthorized Settings or Integrations deep-links fail closed to `/overview`.
- Existing sidebar/topbar/footer styling and role-driven Settings/Integrations visibility remain
  unchanged.

## Pine Beach local evidence

The isolated V2 local session returned an available `/api/dashboards/overview` payload for Pine
Beach Belek with three resolved accounts and the expected aggregate metrics. Headless Chromium
opened `/overview` and verified:

- Pine Beach Belek Brand scope;
- exactly six KPI labels;
- all seven section headings;
- exactly three Platform Breakdown cards;
- one visible Home entry and no duplicate Overview sidebar entry;
- Saves shown as unavailable;
- stored-insight dialog opens;
- zero application HTTP or console errors.

## Verification

- Frontend Vitest: `28 passed`.
- Frontend TypeScript: passed.
- Frontend production build: passed.
- Desktop Playwright: `10 passed`, `1` expected project-specific skip.
- Pine Beach V2-local API/browser smoke: passed.
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
