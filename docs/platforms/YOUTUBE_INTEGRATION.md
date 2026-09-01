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

Provider references: [Google web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server), [YouTube OAuth](https://developers.google.com/youtube/reporting/guides/authorization/server-side-web-apps), [YouTube channel discovery](https://developers.google.com/youtube/v3/docs/channels/list), and [YouTube Analytics reports](https://developers.google.com/youtube/analytics/reference/reports/query).
