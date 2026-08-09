# Revision 6 / R13 — Native collector producer closure report

Date: `2026-08-09`

## Outcome

The R12 frontend/backend read contract now has a V2-owned producer decision for every consumed
metric and dimension: provider-native, versioned-derived, explicit alias, or provider-limited.
No missing provider value is converted to zero and no organic/paid split is inferred.

All writes remained inside `/home/api/colab_scripts/SocialMediadownstream`. The protected
SocialMedia, Accumulate, and Performance Marketing repositories passed the source-write guard
throughout the work. Production provider egress, production databases, schedules, workers, OAuth
activation gates, and live routing were not enabled or changed.

## Implemented producers

### Directional follower flow

Facebook, Instagram, and TikTok use the same versioned fallback when no direct provider flow row
exists:

- `follows` and `new_followers`: `max(current_followers - previous_followers, 0)`;
- `unfollows`: `max(previous_followers - current_followers, 0)`;
- `followers_net`: `current_followers - previous_followers`.

Only consecutive UTC-day snapshots are eligible. A missing day does not create a flow. The day
immediately before the selected range is loaded only as an anchor, so the first selected day is
calculated without leaking the anchor into selected-period totals. Direct provider rows retain
precedence and are reported as `provider_flow`; fallback rows are reported as
`derived:<operator>:v1:consecutive_utc_day_snapshots`.

This fallback measures directional net movement. It cannot reveal simultaneous gross acquisition
and churn hidden inside the same day.

### TikTok daily account insights

The V2 TikTok Business account reader now requests at most 30 inclusive days and normalizes:

- `followers_count` to Followers;
- `video_views` to Views;
- `unique_video_views` to Reach;
- `profile_views` to Profile Views;
- complete `likes + comments + shares` rows to Interactions.

Partial interaction components remain unavailable rather than being summed as if complete. The
standalone worker collects the previous 30 days during backfill and yesterday after backfill.
Provider account collection remains disabled until the existing R8 activation gates are met.

### Facebook paid/organic views

The Facebook daily reader requests `page_media_view` with `breakdown=is_from_ads`. Bucket `0` is
persisted as Organic Views and bucket `1` as Paid Views, including typed breakdown rows. A provider
`400` for this breakdown is treated as unsupported for that scope; other transport failures still
fail the collection attempt.

## Honest provider limitations

The executable capability contract is
`docs/contracts/social-media-v2-provider-capabilities.json`; the frontend matrix points to it.

- Facebook Organic/Paid Reach is provider-limited.
- Instagram Organic/Paid Reach and Organic/Paid Views are provider-limited.
- Facebook Page Like Types and Best Time to Engage are provider-unavailable.
- Instagram Best Time to Engage remains snapshot-compatible but its standalone provider contract
  is unverified.
- Instagram Story Sticker Taps remains provider-unavailable.

The platform metric inventory contains `39` native/derived/aliased contract entries, `6`
provider-limited snapshot entries, and `0` blocked entries. Dimension consumers contain `9`
provider-native entries, `3` explicit provider-limited/unavailable entries, and `0` blocked
entries. Overview's eight consumed paths remain covered by the R12 contract.

## Fresh-database and Pine Beach evidence

The TikTok fake-provider fixture crosses reader normalization, collection service, isolated
PostgreSQL persistence, V2 reporting readback, and dashboard aggregation. Missing-day and direct
provider-precedence tests cover the follower derivation edge cases. Facebook fixture tests cover
request shape, Organic/Paid normalization, typed persistence, and unsupported-breakdown behavior.

Against the already isolated Pine Beach Belek V2 snapshot:

- `/api/auth/me` and all three platform dashboard routes returned `200` after the explicit local
  demo session was opened;
- the single available Brand is Pine Beach Belek (`18`);
- Facebook, Instagram, and TikTok each returned 30 observed days and available follower-flow
  series;
- Instagram Stories returned 16 items and available period totals/trend;
- headless Chromium opened Facebook, Instagram, Instagram Stories, and TikTok without a session
  connection error;
- each platform Cover Page/Account, Content, and Audience KPI grid rendered exactly six cards;
- Instagram Cover still contains the Stories section and the focused Stories tab still opens.

One expired external Meta CDN image returned `403` during the browser check. It is a remote media
asset failure, not an application API or metric-contract failure; dashboard data and local session
remained available.

## Certification evidence

- Canonical disposable PostgreSQL collector-parity suite: `156 passed`.
- Targeted R13/phase integration checks: passed.
- Backend Ruff: passed.
- Backend mypy: passed for `130` source files.
- Frontend TypeScript, `28` component tests, and production build: passed.
- OpenAPI export, secret leak guard, vocabulary guard, and `git diff --check`: passed.
- Source-write guard: passed before, during, and after certification.

## Open external work

R13 does not make the runtime live. R8 still requires owner-provided public origin, trusted issuer,
provider credentials/approval, V2 staging infrastructure, and activation authorization. Those
inputs must not be guessed or copied from a protected live project.

## Completion state

- `R13_NATIVE_COLLECTOR_PRODUCER_COMPLETE=true`
- `STANDALONE_PRODUCT_COMPLETE=true` (unchanged from R7)
- `STANDALONE_RUNTIME_COMPLETE=false`
- `READY_FOR_ACCUMULATE_SSO_HANDOFF=false`
- `SSO_LIVE_VERIFIED=false`
- `TIKTOK_CONNECTION_VERIFIED=false`
