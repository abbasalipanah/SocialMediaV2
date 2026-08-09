# Revision 6 / R10 — Pine Beach Belek V2-local snapshot report

Date: `2026-08-09`

## Outcome

The local Social Media V2 runtime now uses a dedicated PostgreSQL database instead of the
in-memory dashboard fixture. Its single workspace Brand is `Pine Beach Belek` (`18`). The source
SocialMedia database was opened with PostgreSQL read-only enforcement and remained unchanged.

This is a local visual-validation snapshot. It is not a production migration, cutover, dual
write, shadow read, provider activation, or continuous replication path.

## Isolation and safety

- Target container: `social-media-v2-postgres`
- Target DB: `social_media_v2_local`
- Target bind: loopback-only `127.0.0.1:55432`
- Runtime secret and data location: `.local/`, mode-restricted and ignored by Git
- Source DB mode: `transaction_read_only=on`
- Imported platforms: exactly `facebook|instagram|tiktok`
- Excluded: DV360/advertising assets, credential/token/OAuth/provider-security tables
- Media: only Pine Beach rows, copied read-only into V2 local storage after size and SHA-256
  verification; source media files were not changed

The importer rejects a target DB without the `social_media_v2` prefix and rejects identical
source/target endpoints. Re-running the import replaces only target Brand `18` in a target-side
transaction.

## Imported snapshot

| Surface | Rows |
|---|---:|
| Canonical accounts | 3 |
| Allowlisted/mapped metrics | 78,276 |
| Content | 395 |
| Comments | 611 |
| Verified media | 389 |

The lower metric count than the legacy Brand total is intentional: noncanonical advertising,
hashtag helper, provider-internal, and unsupported metric families are not copied. TikTok
content-level snapshots are explicitly mapped to the V2 video-total metric contract.

## Runtime verification

- `/api/auth/me`: Brand `18`
- `/api/workspace/brands`: only `Pine Beach Belek`
- Facebook dashboard: `200`, `available`
- Instagram dashboard: `200`, `available`
- TikTok dashboard: `200`, `available`
- Instagram Stories: correct title, heading, history and local media render
- Headless Chromium: no connection error; tested Facebook, Instagram, Stories, and TikTok media
  responses all returned `200`
- A deliberately persisted legacy `Demo Hotel Group` Brand/account selection was automatically
  replaced with Brand `18`; the stale account was removed and no dashboard error was rendered

The manual refresh entrypoint is `scripts/dev/import_pine_beach.sh`. Normal `npm run dev` starts
or reuses the isolated DB, applies idempotent V2 migrations, and reads dashboard data from it.

## Regression evidence

- Backend: `128 passed, 16 skipped` (external PostgreSQL gates only)
- Frontend: `26 passed`; TypeScript typecheck passed
- Ruff on application/tests/new importer: pass
- Shell syntax and `git diff --check`: pass
- Source write/content guard: pass before and after source reads

## Completion state

- `R10_PINE_BEACH_LOCAL_SNAPSHOT_COMPLETE=true`
- `STANDALONE_PRODUCT_COMPLETE=true` (unchanged from R7)
- `STANDALONE_RUNTIME_COMPLETE=false`
- `READY_FOR_ACCUMULATE_SSO_HANDOFF=false`
- `SSO_LIVE_VERIFIED=false`
- `TIKTOK_CONNECTION_VERIFIED=false`
