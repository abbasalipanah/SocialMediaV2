# YouTube integration

## Status

YouTube is implemented on `feature/x-linkedin-youtube`. It has not been deployed or enabled in the live runtime. Meta and TikTok use their existing routes, configuration, and workers without delegation to this integration.

The implementation provides:

- read-only OAuth using OpenID identity, YouTube Data API, and YouTube Analytics scopes;
- backend-only encrypted access and refresh-token storage;
- owned-channel discovery, explicit Brand selection, and confirmed unlinking;
- bounded profile, 365-day daily metric, recent-video, and recent-comment collection;
- YouTube-native views, engaged views, watch time, engagement, subscriber, playlist,
  content-type, country, device, operating-system, playback-location, YouTube-product,
  live/on-demand, traffic-source, and subscription-status reporting;
- privacy-thresholded 28-day viewer age and gender percentages when YouTube returns them;
- automatic near-expiry access-token refresh before collection;
- frontend authorization in Integrations and channel mapping in Settings;
- fail-closed activation, write, scope, authority, and provider-response checks.

The audience page uses aggregate playback breakdowns supplied by YouTube Analytics.
It does not request or invent individual viewer data. Age and gender are queried only as
aggregate percentages for the latest 28-day window and can be empty when YouTube's
privacy thresholds are not met. Each supported audience surface remains visible with an
honest empty state when its report is withheld. Per-video share counts are not exposed by
the YouTube Data API and remain unavailable rather than being converted to zero.

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
| Development | `.secrets/socialmedia/youtube-dev-client.json` | `http://localhost:8126/api/social/youtube/oauth/callback` | Yes, local canary only |
| Production | `.secrets/socialmedia/youtube-production.json` | `https://social.theaccumulate.com/api/social/youtube/oauth/callback` | No, reserved for the later live cutover |

Both files live inside the isolated worktree as requested, but `.secrets/` is ignored
at the repository root and each JSON remains mode `0600`. Never override the ignore
rule with `git add -f`. The launcher reads only the development JSON into the backend
process environment; the frontend and Git never receive either secret. The production
JSON remains dormant until the later, explicit live cutover.

The development canary's only redirect URI is:

```text
http://localhost:8126/api/social/youtube/oauth/callback
```

Place its downloaded JSON at `.secrets/socialmedia/youtube-dev-client.json` with mode
`0600`, then start the isolated runtime from the frontend directory using the normal
development command:

```bash
cd frontend
npm run dev
```

The launcher reads the development client, creates ignored local OAuth-state and
credential-vault keys, enables writes only against the platform-expansion PostgreSQL
database on `127.0.0.1:56432`, and keeps scheduled collection disabled. The frontend
listens on `localhost:8126`; its Vite proxy sends API and OAuth callback traffic to the
loopback-only backend on `127.0.0.1:8127`. This keeps the browser and Google callback
on one origin. The production callback and production client remain a separate cutover
concern.

Visit `http://localhost:8126/integrations` using the same local-server access method
used for the project's existing `npm run dev` workflow. Authorize YouTube there, open
Settings, select the discovered channel for Brand 18, and link it. Google account
selection and consent are the only steps that must be completed interactively by
the account owner.

After the channel is linked, run one bounded collection against the isolated local
database:

```bash
npm run collect:youtube
```

The command enables YouTube provider reads only for that process, targets Brand 18,
keeps the scheduler disabled, and rejects every database except
`social_media_v2_platforms_dev` on `127.0.0.1:56432`. Refresh the browser after it
finishes; the YouTube navigation and dashboard then use the collected profile,
up to 365 days of analytics, recent videos, and available comments. Initial analytics
backfill is split into provider-safe 31-day windows; later runs refresh only the current
window. Meta, TikTok, the live
database, the production OAuth client, and the live deployment are not used.

Provider references: [Google web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server), [YouTube OAuth](https://developers.google.com/youtube/reporting/guides/authorization/server-side-web-apps), [YouTube channel discovery](https://developers.google.com/youtube/v3/docs/channels/list), and [YouTube Analytics reports](https://developers.google.com/youtube/analytics/reference/reports/query).
