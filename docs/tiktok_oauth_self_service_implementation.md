# TikTok OAuth Self-Service Implementation

## Scope

This implementation adds TikTok as the first Social Media self-service platform. It follows the
same narrow-account-management principle used by Performance Marketing's Yandex Ads flow, while
respecting TikTok Business Accounts OAuth semantics: one Business account is returned by each
authorization and is linked as `pending_verification`.

The Accumulate SSO-only contract and existing owner-handoff route were not changed. No
provisioning payload or authority-sync endpoint exists; viewer/operator authorization comes only
from signed SSO claims and server-produced capabilities.

## Authorization boundary

The self-service API accepts a request only when all of the following are true:

- the local application session is valid;
- the requested Brand is exactly the session Brand (rollup and sibling Brands are rejected);
- the current authority projection grants write access to that Brand; and
- the session contains the narrow `tiktok.connection.manage` permission.

Settings visibility is deliberately not required. The frontend receives the resulting
`tiktok_connection_manage` capability from `/api/workspace/capabilities`, so Integrations can
offer TikTok connection management independently from Settings.

## API contract

- `GET /api/integrations/tiktok/self-service/readiness?brand_id=...` performs a read-only,
  no-provider-call readiness check.
- `POST /api/integrations/tiktok/oauth/start?brand_id=...` is same-origin protected and creates an
  OAuth intent only after the explicit Connect action.
- `GET /api/social/tiktok/oauth/callback` remains the single canonical TikTok callback. Existing
  owner handoffs retain their redirect behavior; self-service callbacks return a no-store popup
  completion page and a strict `postMessage` payload.

OAuth state remains signed, session-bound, Brand-bound, expiring and one-time. Provider tokens are
exchanged and stored only by the backend credential store. The browser receives only redacted
connection/link identifiers and state.

## Runtime state

The implementation is fail-closed. When the activation coordinator, write gate, provider secret,
or provider runtime is unavailable, readiness returns an explicit unavailable reason and the UI
keeps Connect disabled. Opening Integrations or the connection dialog does not create state and
does not contact TikTok.

The backend now assembles the real activation coordinator automatically when the account gate is
enabled. Runtime composition includes the allowlisted HTTP transport, signed/replay-protected
state, encrypted credential store, Brand authority re-check and time-boxed activation gate.

Activation requires all of these environment values together; startup fails closed when any one
is absent or invalid:

- `SOCIAL_WRITES_ENABLED=true` and a disposable-development `SOCIAL_DB_URL`;
- `SOCIAL_VAULT_ENABLED=true`, `SOCIAL_CREDENTIAL_ACTIVE_KEY_ID` and
  `SOCIAL_CREDENTIAL_KEYRING_JSON`;
- the Social TikTok Business App secret in `SOCIAL_TIKTOK_BUSINESS_APP_SECRET`;
- `SOCIAL_TIKTOK_SECRET_ROTATED_AT` recording the rotation of any secret previously exposed in a
  screenshot, terminal, log or chat;
- `SOCIAL_TIKTOK_OAUTH_STATE_SECRET` with at least 32 bytes;
- `SOCIAL_TIKTOK_ACCOUNT_ENABLED=true` and
  `SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE=manual_intent_only`; and
- `SOCIAL_TIKTOK_ACTIVATION_GATE_ENABLED=true` with timezone-aware
  `SOCIAL_TIKTOK_ACTIVATION_ENABLED_AT` and `SOCIAL_TIKTOK_ACTIVATION_EXPIRES_AT`.

The Social TikTok App ID is `7657818426198474768`. A secret issued for another App ID, including
the separate Performance Marketing TikTok App, must not be reused.

The TikTok Business portal was visually re-verified on 2026-07-20: the App ID, account-holder
authorization product and exact callback URI match this runtime contract. The advertiser/Ads URL
shown in the same portal remains out of scope and disabled.

Collection, advertiser sync and automated schedules remain separate gates and stay disabled. The
local demo without credentials therefore exercises readiness and UI without provider calls.

## Verification coverage

- self-service readiness without fresh owner SSO or Settings visibility;
- exact-Brand, write-authority and narrow-permission rejection paths;
- JSON OAuth start contract and popup callback message contract;
- owner SSO handoff regression coverage;
- Integrations modal rendering with provider activation unavailable;
- route boundary, OpenAPI, TypeScript, Vitest and backend regression checks.
