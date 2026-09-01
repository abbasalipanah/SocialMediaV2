# YouTube integration

## Status

YouTube is implemented on `feature/x-linkedin-youtube`. It has not been deployed or enabled in the live runtime. Meta and TikTok use their existing routes, configuration, and workers without delegation to this integration.

The implementation provides:

- read-only OAuth using OpenID identity, YouTube Data API, and YouTube Analytics scopes;
- backend-only encrypted access and refresh-token storage;
- owned-channel discovery, explicit Brand selection, and confirmed unlinking;
- bounded profile, daily metric, recent-video, and recent-comment collection;
- automatic near-expiry access-token refresh before collection;
- frontend authorization in Integrations and channel mapping in Settings;
- fail-closed activation, write, scope, authority, and provider-response checks.

Audience data is not collected because the implemented provider endpoints do not supply a compatible audience-demographic contract. Missing engagement counters remain unavailable rather than being converted to zero.

## Safe defaults

All YouTube activation switches in `backend/.env.example` are disabled by default:

```dotenv
SOCIAL_YOUTUBE_ACCOUNT_ENABLED=false
SOCIAL_YOUTUBE_ACCOUNT_OAUTH_MODE=disabled
SOCIAL_YOUTUBE_COLLECTION_ENABLED=false
SOCIAL_YOUTUBE_ACTIVATION_GATE_ENABLED=false
```

Do not change these values in the live environment as part of feature development. Enabling a non-live environment also requires:

- a separate Google OAuth application and exact redirect URI;
- `SOCIAL_YOUTUBE_OAUTH_APP_ID` and `SOCIAL_YOUTUBE_OAUTH_APP_SECRET`;
- a strong `SOCIAL_YOUTUBE_OAUTH_STATE_SECRET`;
- `SOCIAL_CREDENTIAL_ACTIVE_KEY_ID` and `SOCIAL_CREDENTIAL_KEYRING_JSON`;
- explicit development or staging write policy;
- a bounded activation window.

The requested scope ceiling is fixed to `openid`, `youtube.readonly`, and `yt-analytics.readonly`. No upload, edit, moderation, or other provider write scope is requested.

## Verification

Use only the isolated worktree and its PostgreSQL test database:

```bash
cd /home/api/worktrees/social-platform-expansion
. .local/platform-expansion-db.env
TEST_POSTGRES_URL="postgresql+psycopg://${SOCIAL_DB_USER}:${SOCIAL_DB_PASSWORD}@${SOCIAL_DB_HOST}:${SOCIAL_DB_PORT}/social_media_v2_platforms_test" \
  backend/.venv/bin/python -m pytest
cd frontend
npm test
npm run build
```

Before any later staging rollout, verify the OAuth consent screen and redirect URI with a dedicated test channel, then run one collection and inspect its persisted profile, daily metrics, videos, and comments. Live deployment remains a separate, explicit decision.

### Loopback OAuth canary

The Google project contains two separate web clients. They share the project's
billing, quota and consent configuration, but their secrets and redirect URIs do
not overlap:

| Client | Server file | Exact redirect URI | Used now |
| --- | --- | --- | --- |
| Development | `/home/api/.secrets/socialmedia/youtube-dev-client.json` | `http://localhost:8126/api/social/youtube/oauth/callback` | Yes, local canary only |
| Production | `/home/api/.secrets/socialmedia/youtube-production.json` | `https://social.theaccumulate.com/api/social/youtube/oauth/callback` | No, reserved for the later live cutover |

Both files must be owned by the service user with mode `0600`. They deliberately
remain outside the Git worktree so a broad `git add`, source archive, Docker build
context, or copied worktree cannot include an OAuth client secret. The application
receives the values in its process environment; the frontend and Git never receive
them.

The development canary's only redirect URI is:

```text
http://localhost:8126/api/social/youtube/oauth/callback
```

Place its downloaded JSON at `/home/api/.secrets/socialmedia/youtube-dev-client.json`
with mode `0600`, then start the isolated runtime:

```bash
./scripts/dev/start_youtube_canary.sh
```

The launcher reads the client values without copying them into the repository, creates
ignored local OAuth-state and credential-vault keys, enables writes only against the
platform-expansion PostgreSQL database on `127.0.0.1:56432`, and keeps scheduled
collection disabled. The frontend and callback listen only on loopback ports `3126`
and `8126`; access from a workstation requires an SSH tunnel. The production callback
and production client remain a separate cutover concern.

From the workstation, forward local port `8126` to the server's frontend port
`3126` and open the application through `localhost`:

```bash
ssh -N -L 8126:127.0.0.1:3126 api@SERVER
```

Then visit `http://localhost:8126/integrations`. Authorize YouTube there, open
Settings, select the discovered channel for Brand 18, and link it. Google account
selection and consent are the only steps that must be completed interactively by
the account owner.

After the channel is linked, run one bounded collection against the isolated local
database:

```bash
./scripts/dev/collect_youtube_canary.sh
```

The command enables YouTube provider reads only for that process, targets Brand 18,
keeps the scheduler disabled, and rejects every database except
`social_media_v2_platforms_dev` on `127.0.0.1:56432`. Refresh the browser after it
finishes; the YouTube navigation and dashboard then use the collected profile,
30-day analytics, recent videos, and available comments. Meta, TikTok, the live
database, the production OAuth client, and the live deployment are not used.

Provider references: [Google web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server), [YouTube OAuth](https://developers.google.com/youtube/reporting/guides/authorization/server-side-web-apps), [YouTube channel discovery](https://developers.google.com/youtube/v3/docs/channels/list), and [YouTube Analytics reports](https://developers.google.com/youtube/analytics/reference/reports/query).
