# Social Media V2 — final provider ownership and public cutover runbook

Status: `DRAFT / DO NOT EXECUTE BEFORE READY GATES AND TEAM APPROVAL`

This runbook does not authorize a cutover. It is the exact coordinated sequence to use only after
the accelerated pre-cutover acceptance passes, V2 reports no critical/high product defect, and
Accumulate/Operations/provider owners approve the same change window. The original 24-hour
pre-cutover wait was explicitly waived by the user on `2026-08-13`; the post-activation observation
period remains unchanged.

## Non-negotiable boundaries

- Do not stop V1 API/UI before public V2 browser acceptance.
- Do not enable V2 collection while any V1 provider timer is active.
- Do not refresh TikTok from V2 before the provider owner confirms rollback credential handling.
- Do not edit Accumulate from the V2 workstream; its team owns its flag/profile change.
- Do not delete V1 DB, media, release, env, or credential records.

## 1. Preconditions

Verify all of the following:

```bash
systemctl is-active ars-social-backend.service
systemctl is-active social-media-v2-api.service
systemctl is-active social-media-v2-web.service
systemctl is-enabled social-media-v2-collection.timer
curl --fail --silent http://127.0.0.1:8026/api/health
curl --fail --silent http://127.0.0.1:8026/api/operations/readiness
curl --fail --silent http://127.0.0.1:3026/
```

Expected collection timer state is `disabled`. Audit the soak:

```bash
systemctl list-timers social-media-v2-soak-probe.timer --all
journalctl -u social-media-v2-soak-probe.service \
  --since '2026-08-13 11:16:36 UTC' --no-pager
```

There must be no failed invocation. The substitute accelerated gate must show `120/120` successful
health/readiness/web cycles, zero API/web error-priority rows, backend `152 passed`, frontend
`37 passed`, and passing TypeScript checks. Operations must also perform one controlled V2-only
API/web restart and repeat the three loopback probes before any provider or routing mutation; the
current automation identity cannot perform that privileged restart.

## 2. Capture V1 timer state, then pause provider writers

The exact V1 timer set currently in scope is:

```text
facebook-audience-canary.timer
facebook-daily.timer
facebook-followers-hourly.timer
facebook-media-refresh-morning.timer
facebook-media-refresh-night.timer
facebook-monthly.timer
facebook-weekly.timer
instagram-daily.timer
instagram-followers-hourly.timer
instagram-media-refresh-morning.timer
instagram-media-refresh-night.timer
instagram-monthly.timer
instagram-story.timer
instagram-weekly.timer
social-backfill-jobs.timer
social-cover-repair.timer
social-d1-coverage-check.timer
social-daily-orchestration.timer
social-rolling-refresh-monthly-close.timer
social-rolling-refresh-nightly.timer
social-rolling-refresh-weekly.timer
tiktok-backfill-jobs.timer
tiktok-organic-sync.timer
```

Operations must record each unit's active/enabled state in the change record, then stop only these
timers and wait for their associated service invocations to finish. Do not stop
`ars-social-backend.service`.

If a provider-writing service cannot quiesce, abort before any token refresh or routing change and
restore the recorded timer states.

## 3. Final data and credential reconciliation

Run the full import verifier and credential verifier with V1 still available. The active candidate
must match the now-quiesced V1 source. If it does not, create a new empty final candidate and repeat
the Phase B import; do not patch individual rows ad hoc.

The final report must record exact counts and timestamp. No public/Accumulate change is allowed on a
failed or stale parity result.

## 4. TikTok ownership transfer gate

The refresh-free canary currently rejects both TikTok links. Provider/V1 operations must first
confirm the current app's refresh-token rotation and rollback procedure. The ownership operation
must preserve the newly returned access and refresh token in the V2 AES-256-GCM vault before any
V2 collection attempt, then validate exact business identity and required scopes.

Allowlisted links:

```text
99
100
```

After the provider owner has transferred/refreshed the credentials, rerun:

```bash
/opt/social-media-v2/backend/.venv/bin/python \
  /opt/social-media-v2/backend/scripts/provider_read_canary.py \
  --env /etc/social-media-v2/production.env \
  --link-id 1 --link-id 11 --link-id 99
```

Repeat with TikTok link `100`. Both runs must report zero POST/refresh requests, three passed reads,
and unchanged credential fingerprints. If either fails before a refresh, restore V1 timers. If a
refresh has already rotated credentials, follow the provider owner's recorded credential rollback;
do not blindly re-enable V1 with a potentially stale refresh token.

## 5. Public and Accumulate canary

Only after provider and parity gates pass:

1. Validate `deploy/nginx/social-media-v2.conf` with `nginx -t`.
2. Accumulate team deploys its downstream profile/sidebar change with its flag off.
3. Operations replaces only the Social hostname config and performs graceful Nginx reload.
4. Probe health, readiness, root, assets, SSO consume logging policy, and authenticated media.
5. Accumulate opens a small internal cohort.
6. Run real sidebar SSO, Brand/hidden-parent/rollup, dashboard, logout/re-login, Meta OAuth callback,
   and TikTok callback tests.
7. Expand the cohort only with zero critical/high findings.
8. Enable V2 provider gates/schedule only after V1 provider ownership is confirmed inactive.
9. Remove V1 traffic ownership only after the full cohort passes; retain all V1 artifacts.

## 6. Routing rollback

Before credential rotation, rollback is:

1. Accumulate disables the downstream launch flag.
2. Operations restores the captured V1 Nginx config and graceful reloads.
3. V2 collection remains disabled.
4. Recorded V1 timer states are restored.

After a TikTok refresh-token rotation, routing rollback is still possible, but collection rollback
requires the provider owner's preserved valid credential procedure. Public routing and provider
credential rollback are separate decisions.
