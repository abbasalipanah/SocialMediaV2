# Meta OAuth Self-Service Implementation

## Scope

This implementation adds Brand-scoped Meta self-service connection for Facebook Pages and their
linked Instagram Business accounts. It uses the Social Meta app contract and the existing Social
Graph transport; it does not use the Performance Marketing Meta Ads integration.

One explicit Facebook authorization discovers both account types. Discovery never links an
account automatically. The user chooses the Facebook and/or Instagram accounts that should be
attached to the exact selected Brand and confirms that selection in a second command.

The Accumulate SSO-only token claims and Settings-visibility contract were not changed. No
provisioning payload or authority-sync endpoint exists in the standalone runtime.

## Authorization boundary

The self-service API accepts a request only when all of the following are true:

- the local application session is valid;
- the requested Brand is exactly the session Brand;
- rollup and sibling-Brand scopes are not used; and
- the current authority projection grants write access to that Brand.

Settings visibility is deliberately not required. The frontend receives the narrow
`meta_connection_manage` capability from `/api/workspace/capabilities`. Every start, callback and
link command re-resolves the same Brand authority. Discovery selections are also checked against
the connection and Brand before persistence.

## API contract

- `GET /api/integrations/meta/self-service/readiness?brand_id=...` is read-only and does not contact
  Meta. It returns linked counts, pending discoveries and an explicit activation reason.
- `POST /api/integrations/meta/oauth/start?brand_id=...` creates an OAuth intent only after an
  explicit Connect Meta action and a same-origin check.
- `GET /api/social/meta/oauth/callback` consumes the signed one-time state, exchanges the code,
  verifies the granted permission set and discovers Facebook/Instagram accounts.
- `POST /api/integrations/meta/accounts/link?brand_id=...` links only the explicitly submitted
  discoveries to the exact Brand.

The callback returns a no-store popup completion page with a strict `postMessage` payload. OAuth
state is signed, session-bound, Brand-bound, expiring and replay-protected. The browser never
receives a provider token or credential reference.

## Credential and persistence contract

The provider user token and per-account tokens are encrypted by the backend credential vault.
Only opaque references are written to projection metadata. A failed permission check, provider
exchange or persistence transaction revokes/discards credentials on a best-effort basis.

The pending connection and discoveries are durable. Facebook Pages and linked Instagram Business
profiles remain `discovered` until the selection command creates the Brand account links. Existing
Facebook/Instagram reporting continues to use the Social application schema.

## Runtime activation

The implementation is fail-closed and disabled by default. Opening Integrations or the Meta modal
does not contact Meta. The local demo exercises the complete permission, readiness and UI path
without provider calls.

Real provider activation requires all of these values together:

- `SOCIAL_WRITES_ENABLED=true` with an explicitly disposable development database;
- `SOCIAL_VAULT_ENABLED=true`, `SOCIAL_CREDENTIAL_ACTIVE_KEY_ID` and
  `SOCIAL_CREDENTIAL_KEYRING_JSON`;
- the Social Meta App secret in `SOCIAL_META_APP_SECRET`;
- `SOCIAL_META_OAUTH_STATE_SECRET` with at least 32 bytes;
- `SOCIAL_META_ACCOUNT_ENABLED=true` and
  `SOCIAL_META_ACCOUNT_OAUTH_MODE=manual_intent_only`; and
- `SOCIAL_META_ACTIVATION_GATE_ENABLED=true` with timezone-aware
  `SOCIAL_META_ACTIVATION_ENABLED_AT` and `SOCIAL_META_ACTIVATION_EXPIRES_AT`.

The canonical Social Meta App ID is `1133669534788144`. The callback URI is:

`https://social.theaccumulate.com/api/social/meta/oauth/callback`

That exact URI must be registered in the Meta app before enabling the gate. A Meta App secret that
has appeared in terminal output, logs, chat or repository history must be rotated in Meta and
injected from the approved secret store; it must not be copied into Git or reused as-is.

## Verification coverage

- exact-Brand, write-authority and no-Settings access paths;
- same-origin OAuth start and explicit account-link commands;
- signed state binding, expiry and single-use replay protection;
- short-token to long-token exchange with granted-permission verification;
- Facebook Page and linked Instagram Business discovery;
- provider-token redaction from DTOs, errors and object representations;
- Integrations modal behavior without implicit OAuth start;
- OpenAPI generation, TypeScript, Vitest, production build, backend lint and regression tests.
