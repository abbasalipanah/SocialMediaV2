# Faz 9 — Offline Release Rehearsal Report

> **ARCHIVED / SUPERSEDED:** Bu rapor tarihsel kanıttır ve güncel R7 sertifikasyonu değildir.
> Revizyon 6 R0-R8 kapıları ayrıca tamamlanmadan completion status'u üretmez.

## Scope and safety

Faz 9 uses only local files, fake provider responses and ephemeral PostgreSQL 16 containers. No production database credential, production database connection, provider network call, traffic route, service state, timer, scheduler or source-project write is permitted.

## Implemented rehearsal surfaces

- Immutable V1 migrations `0001`–`0009` are hash-checked against the Faz 0 baseline, copied to a temporary directory, applied to an empty local database and fingerprinted.
- Expected migration-built schema: head `0009_tiktok_organic_oauth_config`, 23 tables, 259 columns, 79 constraints, 81 indexes, fingerprint `fe786adb32c556b572e316457b4c008e39883ae4b4510f738800179d4be9ab15`.
- Fixture outbox records emitted/applied watermark `5`, ordered full `brand_access.sync` at `S=4`, duplicate acknowledgement, drain and post-snapshot event application.
- Owner activation requires a 5-minute fresh SSO consumed after the activation-gate timestamp,
  hashed SSO JTI, exact local session, write authority, Settings visibility and
  `tiktok.connection.manage` permission.
- Safe readiness GET performs no activation mutation. Only same-origin explicit POST creates and leases the internal intent and emits one-time state.
- Callback consumes state and intent before fake exchange, checks token/token-info scope equality, re-checks authority, encrypts access/refresh values, and creates the exact Brand link as `pending_verification`.
- The release candidate contains no live TikTok activation HTTP transport. The integration test injects a fake transport; production assembly injects no coordinator.
- Access revocation between exchange and persistence triggers fake revoke/discard with no credential or link.
- Dormant Nginx/systemd/environment drafts, cutover checklist, rollback checklist and writer inventory are committed but not installed.
- The Accumulate patch is a review draft only and was not applied to the immutable source project.

## Evidence

- Disposable production-schema fingerprint comparison: green.
- Full PostgreSQL-backed backend suite: `121 passed`, with the separate parity-database case
  skipped only in this final database set; the recursively invoked Faz 5 certification executes
  that differential case on its dedicated oracle/candidate databases and is green.
- Targeted Phase 9 production-schema/outbox/activation suite: `5 passed`.
- Faz 8 regression: targeted backend `15 passed`, frontend `13 passed`, Chromium `8 passed`
  with `4` intentional viewport skips, Vite build `1878` modules, npm audit `0` vulnerabilities.
- Secret, canonical vocabulary and immutable source guards are clean at both entry and exit.
- Canonical command: `./scripts/quality/fase9_offline_release_check.sh` — PASS.

## Production state assertion

V1 remains the sole production writer. V2 has no production database or provider credential, no production process or route, and no runnable writer/timer. TikTok account OAuth, collection and advertiser gates remain disabled by default. Phase 9 completion does not authorize deployment or Writer Ownership Cutover.
