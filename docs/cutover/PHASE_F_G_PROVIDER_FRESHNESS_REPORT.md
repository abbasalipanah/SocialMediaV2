# Social Media V2 cutover — Phase F/G provider and freshness report

Date: `2026-08-13`

Status: `PHASE_F_G_IN_PROGRESS / TIKTOK_OWNERSHIP_TRANSFER_PENDING / PUBLIC_CHANGE_BLOCKED`

## Outcome

The existing Meta and TikTok developer applications are configured in V2; no new app was created.
Both app IDs and secrets match their current operational sources, while V2 has separate OAuth state
secrets and its own AES-256-GCM credential vault.

Facebook and Instagram real, bounded profile GET canaries passed. Both imported TikTok access
tokens were rejected by the provider's token-info endpoint. The canary tool made no POST, refresh,
revoke, collection, or credential write; the encrypted credential fingerprint remained unchanged.

This is handled as a safe gate, not by refreshing while V1 is still the live collection owner.
TikTok refresh/ownership transfer remains in the final coordinated window after V1 provider timers
are paused. Therefore V1 continues working with its current credential family.

## Existing app transfer state

| Provider | Existing app ID | V2 secret | Runtime ownership |
|---|---|---|---|
| Meta | `1133669534788144` | source-matched, not logged | still V1 until cutover |
| TikTok | `7657818426198474768` | source-matched, not logged | still V1 until cutover |

Canonical callbacks remain:

```text
https://social.theaccumulate.com/api/social/meta/oauth/callback
https://social.theaccumulate.com/api/social/tiktok/oauth/callback
```

The callback origin is still routed to V1; OAuth callback live verification is intentionally
deferred until canonical routing changes in the final window.

## Provider evidence

- fake/retry/persistence provider matrix: `50 passed`;
- Facebook link `1`: one profile GET, passed;
- Instagram link `11`: one profile GET, passed;
- TikTok links `99` and `100`: one token-info GET each, provider rejected;
- provider POST requests: `0`;
- provider refresh requests: `0`;
- V2 credential rows/nonces after probes: `170 / 170`;
- credential projection fingerprint: unchanged.

The reusable command is `backend/scripts/provider_read_canary.py`; it requires exactly one explicit
link ID per platform, refuses open collection/schedule/account gates, permits only GET behavior, and
checks credential immutability.

A read-only V1 service audit on `2026-08-13` found the latest `tiktok-organic-sync.service` run
completed successfully at `04:50:46Z`; the latest `tiktok-backfill-jobs.service` invocation also
returned systemd `Result=success` at `11:17:01Z`, although its application log contains mixed
item-level success/failure classifications. This confirms that V1 remains the operational owner; it
does not prove that V2's distinct token-info preflight is valid. Consequently the V2 rejection stays
as an open ownership-transfer gate, and no V1 token refresh or mutation was attempted.

## Worker and schedule safety

The fake provider worker/recovery tests passed. Starting the actual collection systemd service with
the schedule gate closed failed before DB lock/provider work with `Scheduled collection is disabled`.
The failed unit state was reset; final state is:

```text
social-media-v2-collection.service: inactive/disabled
social-media-v2-collection.timer: inactive/disabled
all Meta/TikTok account, activation, collection and schedule gates: disabled
```

## Freshness

At `2026-08-13T11:17:34Z`, the full streamed read-only verifier again matched V1 and V2:

- `68` Brands;
- `72` connections and `99` linked accounts;
- `1,567,094` metrics;
- `6,624` content items;
- `3,608` comments;
- `6,524` media rows/files;
- `170` credential plaintext/nonces.

V1 collection remains active, so this timestamp is evidence, not a permanent promise. Final
reconciliation must run again after V1 provider timers are paused and before routing changes.

## Soak

`social-media-v2-soak-probe.timer` began at `2026-08-13T11:16:36Z`. Every five minutes it performs
read-only loopback health, readiness, and web probes. On `2026-08-13`, the user explicitly waived
the 24-hour pre-cutover wait in favor of an accelerated acceptance gate. That substitute gate
passed: `120/120` consecutive health/readiness/web cycles, zero API/web error-priority rows,
backend `152 passed / 18 skipped`, frontend `37 passed`, and TypeScript checks passed. The soak timer
remains enabled for additional observation. A V2-only controlled restart and the secret-protected
real-browser rerun require the privileged final window; the current automation identity could not
perform/read those protected operations, so neither V1 nor runtime secrets were altered.

## Open readiness gates

1. Audit the continuing soak and perform the privileged V2 restart/browser preflight.
2. Pause V1 provider timers in the final coordinated ownership window.
3. Perform the final read-only freshness/parity check.
4. Refresh/transfer TikTok credentials under provider-owner control and pass token-info/collection
   canary without a second live scheduler.
5. Only after those pass set `READY_FOR_ACCUMULATE_SSO_HANDOFF=true`.

Machine-readable evidence is in `docs/cutover/phase_f_g_provider_freshness.json`.

## Gate state

```text
PHASE_F_COMPLETE=false
PHASE_G_COMPLETE=false
EXISTING_PROVIDER_APPS_CONFIGURED_IN_V2=true
EXISTING_PROVIDER_APPS_TRANSFERRED_TO_V2=false
META_REFRESH_FREE_READ_VERIFIED=true
TIKTOK_REFRESH_FREE_READ_VERIFIED=false
PROVIDER_COLLECTION_LIVE_VERIFIED=false
PARALLEL_PREPROD_FRESH_AS_OF=2026-08-13T11:17:34Z
SOAK_24H_COMPLETE=false
SOAK_24H_GATE_WAIVED=true
ACCELERATED_ACCEPTANCE_COMPLETE=true
OPEN_CRITICAL_FINDINGS=0
OPEN_HIGH_READINESS_FINDINGS=1
READY_FOR_ACCUMULATE_SSO_HANDOFF=false
```
