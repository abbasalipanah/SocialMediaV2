# Revision 6 / R12 — Six-KPI and frontend/backend data-contract report

Date: `2026-08-09`

## Outcome

The V2 full-data dashboard now renders exactly six KPI cards in every Facebook, Instagram, and
TikTok Page/Account, Content, and Audience section. The null `Frequency` placeholder was removed.
Facebook and Instagram use a real backend-derived `engagement_rate`; TikTok retains its canonical
`video_engagement_rate`.

All changes are confined to `/home/api/colab_scripts/SocialMediadownstream`. The protected
SocialMedia, Accumulate, and Performance Marketing source projects still match their approved
read-only baselines.

## Engagement-rate contract

- Facebook and Instagram: selected-period `interactions / views`.
- TikTok: `video_engagements_total / video_views_total` at the same sample/window.
- The backend recomputes the ratio from components; ratios are not summed across accounts or days.
- A zero/missing denominator remains unavailable.
- OpenAPI exposes unit `ratio`; the frontend formats that value as a percentage.

Pine Beach last-30-day API results:

| Platform | Value | API unit | Status | Methodology |
|---|---:|---|---|---|
| Facebook | `0.00748056404066123` | `ratio` | `available` | `derived:ratio_from_components:v1:selected_period` |
| Instagram | `0.009199059344307649` | `ratio` | `available` | `derived:ratio_from_components:v1:selected_period` |
| TikTok | `0.014293845028051061` | `ratio` | `available` | `derived:ratio_from_components:v1:same_sample` |

## Metric audit

The executable matrix is
`docs/contracts/social-media-v2-frontend-data-matrix.json`. A backend test scans the actual
frontend source files and fails if a canonical metric literal is added, removed, or left without
an explicit backend route.

| Surface | Consumed IDs | Provider-native now | Backend-derived | Snapshot-compatible | Explicit aliases/nested |
|---|---:|---:|---:|---:|---:|
| Facebook | 15 | 5 | 2 | 7 | 1 |
| Instagram | 15 | 5 | 2 | 7 | 1 |
| TikTok | 15 | 5 | 3 | 6 | 1 |
| Overview | 8 | 7 Overview aggregates | — | — | 1 nested TikTok metric |

The Overview mismatch found by this audit was fixed: its backend aggregation now returns
Followers, New Followers, Reach, Views, Interactions, Website Clicks, and Reactions. TikTok Video
Engagements remains a nested TikTok platform metric, matching the frontend access path.

Instagram `new_followers` was also incorrectly described as provider-native even though the V2
Meta daily reader does not request it. It is now honestly derived from consecutive follower
snapshots, while imported direct samples continue to take precedence.

## Dimension and typed-contract audit

- Facebook country/city: native Meta audience breakdowns.
- Facebook Page Like Types: demo-only today; unavailable in the Pine/native runtime rather than
  synthesized.
- Facebook age/gender and activity: explicit `provider_unavailable` capability.
- Instagram country/city/age/gender: native Meta audience breakdowns.
- Instagram Best Time to Engage: V2 snapshot-compatible, not currently produced by the native
  V2 Meta audience reader.
- TikTok country/age/gender/activity: native TikTok audience breakdowns.
- Content type/reach/views, hashtags, and community leaderboards: derived from persisted typed
  content/comments, not free-form frontend inference.
- Story views, reach, interactions, replies, shares, profile visits, follows, navigation,
  completion, saves, and sticker taps are checked across persistence, reporting, and API models.
  Sticker Taps remains explicitly unavailable when Meta does not return it.

## Important interpretation

The V2 read model, persistence model, catalog, aggregation, OpenAPI, and frontend routes now cover
every consumed metric/dimension. That does **not** mean every field is produced natively by a new
standalone provider collection today.

Snapshot-compatible metric groups still requiring native-collector closure are:

- Facebook/Instagram: Follows, Unfollows, Net Followers, organic/paid Views, and organic/paid
  Reach.
- TikTok: Follows, Unfollows, Net Followers, account Views, Reach, and Profile Views.
- Instagram Best Time to Engage is snapshot-compatible; Facebook Page Like Types is demo-only;
  Facebook activity/age-gender and Story Sticker Taps are explicit provider limitations.

Pine Beach renders these snapshot-compatible fields because they were copied into the isolated
V2-local database through the read-only snapshot import. A fresh standalone collector must not be
certified as fully native until the planned R13 producer-closure work validates and fills only
provider-supported fields.

## Verification evidence

- Backend: `133 passed, 16 skipped`; all skips require separately configured disposable
  PostgreSQL integration/parity databases.
- Backend Ruff: passed for the changed files; mypy passed for `129` source files.
- Frontend: TypeScript passed; `28 passed`; production build passed.
- Full-data render test: all 9 platform sections contain exactly 6 KPI cards.
- Pine Beach headless Chromium: all 9 sections contain exactly 6 KPI cards; no console errors and
  no HTTP responses at or above 400.
- OpenAPI export check, secret scan, vocabulary scan, and `git diff --check`: passed.
- Source write guard: passed; protected source-project Git/content baselines are unchanged.

## Completion state

- `R12_FRONTEND_BACKEND_DATA_CONTRACT_COMPLETE=true`
- `STANDALONE_PRODUCT_COMPLETE=true` (unchanged from R7)
- `STANDALONE_RUNTIME_COMPLETE=false`
- `READY_FOR_ACCUMULATE_SSO_HANDOFF=false`
- `SSO_LIVE_VERIFIED=false`
- `TIKTOK_CONNECTION_VERIFIED=false`
