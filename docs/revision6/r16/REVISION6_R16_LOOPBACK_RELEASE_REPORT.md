# Revision 6 / R16 — Isolated V2 loopback staging release

Date: `2026-08-10`

## Outcome

Only the independent Social Media V2 runtime was upgraded. The active immutable release is
`/opt/social-media-v2/releases/20260810T072209Z`; the previous
`/opt/social-media-v2/releases/20260810T071423Z` release remains available for rollback. A second
idempotent upgrade pass created the active release and re-ran the already-applied migration set
without changing migration count or V2 data.

The API and loopback web services are healthy on `127.0.0.1:8026` and `127.0.0.1:3026`.
`social-media-v2-api.service` and `social-media-v2-web.service` are active/enabled. The V2
collection service and timer remain inactive/disabled.

## Database and secret boundary

The target is the dedicated `social_media_v2_staging` database. Migrations `0003` and `0004`
were applied after the existing `0001` and `0002` checksums were verified. The database now has
exactly four ordered V2 migrations.

The already approved shared AI provider credential was copied from the Git-ignored V2 local secret
to the root-owned V2 runtime env. It was not printed, committed, copied into a release artifact, or
written to documentation. The runtime confirmed only `ai_enabled=true` and
`ai_key_present=true`. The pre-change env is retained as a root-only rollback backup.

## Pine Beach staging snapshot

The existing V2-local Pine Beach snapshot was copied into the independent staging database after
runtime activation. The copy tool requires exact `social_media_v2_local` and
`social_media_v2_staging` database names, opens the source transaction read-only, accepts only
Brand `18` and the `legacy-brand:18` provenance projection, refuses non-empty target application
tables, and performs all database inserts in one transaction.

The staging result contains 1 Brand, 3 linked accounts, 80,519 metrics, 395 content items, 611
comments, 389 media records, and 2 completed AI Summaries. The 389 V2-local media files were copied
to a separate staging directory; file count and aggregate checksum matched before the media
directory was atomically switched. The previous empty media directory remains as a V2-owned
rollback backup.

## Runtime verification

- health: `200`, `status=ok`;
- readiness: `200`, `runtime_mode=staging`, writes enabled, V2 DB configured;
- loopback web: `200`;
- deployed OpenAPI includes `/api/insights`, `/api/insights/limit`, and
  `/api/insights/generate`;
- deployed frontend contains the canonical `AI Summary` surface;
- exact signed Accumulate `viewer` + `app_role=operator` SSO returned `303`, then authenticated;
- Settings was hidden, Integrations visible, and AI limit reported its provider configured;
- logout returned `204`;
- the exact pre-snapshot smoke Brand/session/JTI records were deleted after that test; staging
  returned to zero Brand, projection, and AI insight rows before the Pine Beach copy;
- V2 API/web/migration journals had no warning-or-higher entries for the release window;
- an existing release ID was explicitly refused without changing the active symlinks or release
  count;
- Overview, Facebook, Instagram Stories, TikTok, insight history, AI limit, and a persisted media
  endpoint returned `200` with non-empty Pine Beach payloads;
- headless Chromium consumed a signed viewer/operator SSO launch on `3026`, reached `/overview`,
  displayed Pine Beach and AI Summary, hid Settings, showed Integrations, logged out with `204`,
  and recorded zero browser/API failures. Exact smoke session/JTI rows were removed afterward.

Repository verification after deployment: backend `141 passed` with `18` environment-gated skips,
frontend `29 passed`, TypeScript/production build, Ruff, secret leak guard, canonical vocabulary
guard, source write guard, runtime artifact check, shell syntax, and `git diff --check` passed.

## Protected systems and public cutover

The protected SocialMedia, Accumulate, and performance_marketing source baselines passed the
read-only guard. No protected service, timer, database, provider setting, or source file was
changed.

`https://social.theaccumulate.com` still proxies to the protected V1 upstream
`127.0.0.1:52120` and remained reachable. Shared Nginx was neither edited nor reloaded. V2 has no
public route because a separate V2 hostname, DNS record, and TLS certificate have not yet been
provided. Public activation remains a distinct operations gate.
