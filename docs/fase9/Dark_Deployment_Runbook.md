# Dark Deployment Runbook — Offline Draft

> **ARCHIVED / SUPERSEDED:** Bu tarihsel dark-deployment taslağı Revizyon 6 runtime modelinin
> yerine geçmez. Güncel güvenli başlangıç `standalone_ready` durumudur.

Status: **NOT EXECUTED**. This document is a review artifact; it grants no production authority.

## Safety boundary

- Do not install, enable, start, reload or copy any draft unit or Nginx file during the release-candidate gate.
- Do not provide V2 with a production database URL, database credential, SSO secret, provisioning secret, vault key or TikTok secret.
- Do not stop, restart, mask or edit any V1 service, timer, worker, command or routing entry.
- Do not create cron, timer, scheduler or orchestrator entries for V2.
- The only approved rehearsal target is an ephemeral local PostgreSQL container with a non-production database name.

## Draft artifact inventory

- `deploy/env/social-media-v2.dormant.env`: all mutation and TikTok gates explicitly off.
- `deploy/systemd/social-media-v2-api.service`: static unit with no install target and a missing-by-default local sentinel.
- `deploy/systemd/social-media-v2-writers.service`: non-runnable placeholder; no worker command and no timer.
- `deploy/nginx/social-media-v2-dark.conf`: loopback-only listener exposing health/readiness and returning `404` elsewhere.

No artifact is installed under `/etc`, `/opt`, `/run` or the active Nginx include tree by Phase 9 automation.

## Offline validation

1. Run `scripts/source_write_guard.sh`.
2. Confirm `find deploy -type f` matches the reviewed inventory above.
3. Confirm `find deploy -type f \( -name '*.timer' -o -name '*cron*' \)` is empty.
4. Validate unit syntax with `systemd-analyze verify` when available; do not copy the units.
5. Confirm the environment draft contains `dormant`, `SOCIAL_WRITES_ENABLED=false`, and all four TikTok gates off.
6. Inspect the Nginx draft: it must listen only on `127.0.0.1`, expose only health/readiness, and never appear in the active include tree.
7. Run the Phase 9 disposable PostgreSQL rehearsal and the full test/certification script.

## Future dark-deployment approval gate

The following requires a separate user-approved production operation after the release candidate is signed:

- immutable artifact checksum and reviewer approval;
- real service/timer/process inventory captured immediately before change;
- production credentials issued as read-only and stored outside Git;
- an approved host path, user/group, firewall rule and loopback health port;
- explicit proof that no public proxy route, writer sentinel, provider egress or scheduler is enabled;
- a rollback owner and observation window.

If any prerequisite is missing, stop. V1 remains the sole owner and V2 remains absent from production.
