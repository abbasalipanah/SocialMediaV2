# Revision 6 / R11 — Dashboard data completeness report

Date: `2026-08-09`

## Outcome

The requested V2-only dashboard corrections are implemented against the isolated Pine Beach
Belek snapshot. The live SocialMedia, Accumulate, and Performance Marketing projects were not
changed. Source SocialMedia data was read only through PostgreSQL-enforced read-only access.

## Product corrections

- Instagram Cover now renders Page, Content, Stories, and Audience in that order.
- Facebook, Instagram, and TikTok follower-flow charts render `Follows`, `Unfollows`, and `Net`
  from three distinct daily metric series.
- Pine Beach organic/paid views and reach metrics are exposed to Facebook/Instagram cards rather
  than leaving those cards empty.
- TikTok daily views, reach, profile views, and interactions are preserved by the V2 importer;
  Performance Trends uses the full selected period instead of the shorter cumulative content
  snapshot.
- All Performing Content is capped at `520px`; Stories History is capped at `455px`. Both use
  internal scrolling and sticky table headers.
- The selected Story shows its own Replies, Shares, Profile Visits, Follows, Sticker Taps, and
  Saves below the KPI cards. Behaviour shows the same action family aggregated over the selected
  date range.
- Missing provider data and a reported zero remain distinct. Pine Beach has no sticker-specific
  metric, so Sticker Taps renders `Not provided`; its persisted Story saves are real zeros and
  render as `0`.

## Story percentage definition

The percentage rows were retained because they carry a valid comparison:

- Story Views, Reach, and Interactions: relative percentage change from the immediately previous
  chronological Story in the gallery.
- Completion Rate: percentage-point difference from that previous Story.
- When no previous Story or valid denominator exists, the UI displays `Previous story
  unavailable` and does not invent a percentage.

## Pine Beach verification

- Refreshed V2-local import: `3` accounts, `80,519` metrics, `395` content rows, `611` comments,
  and `389` verified media rows.
- Instagram last 30 days: all three follower-flow series contain `30` daily points.
- Instagram organic/paid views and reach cards are available.
- Stories selected Story actions: Replies `4`, Shares `11`, Profile Visits `27`, Follows `1`,
  Sticker Taps unavailable, Saves `0`.
- Stories period totals: Replies `55`, Shares `185`, Profile Visits `609`, Follows `7`, Sticker
  Taps unavailable, Saves `0`.
- TikTok Last 30 Days range: `2026-07-10` through `2026-08-08`; daily Views and Reach series both
  contain `30` points across the same endpoints.

## Regression evidence

- Backend: `128 passed, 16 skipped`; skips require separately configured disposable PostgreSQL
  integration databases.
- Changed Python files: Ruff format/check passed.
- Frontend: TypeScript passed; `27 passed`; production build passed.
- Headless Chromium: Cover Stories heading present, long-table internal overflow active, selected
  and period Story action grids distinct, TikTok Performance Trends spans Jul 10–Aug 08, and no
  browser console errors were emitted.
- `git diff --check`: passed.

## Completion state

- `R11_DASHBOARD_DATA_COMPLETENESS_COMPLETE=true`
- `STANDALONE_PRODUCT_COMPLETE=true` (unchanged from R7)
- `STANDALONE_RUNTIME_COMPLETE=false`
- `READY_FOR_ACCUMULATE_SSO_HANDOFF=false`
- `SSO_LIVE_VERIFIED=false`
- `TIKTOK_CONNECTION_VERIFIED=false`
