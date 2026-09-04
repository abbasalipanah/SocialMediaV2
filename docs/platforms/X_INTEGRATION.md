# X integration

## Implemented scope

- OAuth 2.0 Authorization Code with S256 PKCE for a confidential Web App.
- Exact scopes: `tweet.read`, `users.read`, `offline.access`.
- Authenticated X account discovery and explicit Brand linking.
- Profile snapshots: followers and post count.
- Owned-post timeline: text, published time, media, impressions, likes, replies,
  reposts plus quotes, bookmarks, engagements and profile clicks when X returns them.
- One page of at most 25 owned posts per collection run. Replies and reposts are
  excluded from the owned-post feed.

Comments and audience demographics are deliberately unsupported. Scheduled collection
remains disabled in the local canary.

## Local credential contract

Create the ignored file `.secrets/socialmedia/x-dev-oauth.json` with mode `0600`:

```json
{
  "web": {
    "client_id": "VALUE_FROM_X_DEVELOPER_CONSOLE",
    "client_secret": "VALUE_FROM_X_DEVELOPER_CONSOLE",
    "redirect_uris": [
      "http://localhost:8126/api/social/x/oauth/callback"
    ]
  }
}
```

The canary launcher validates this shape and exact callback before exporting values to
its child processes. The file is ignored by Git and the values are never returned to
the browser.

## Local run

```bash
cd frontend
npm run dev
```

Open `http://localhost:8126`, connect X from Settings, select the discovered account,
then collect only X into the isolated development database:

```bash
cd frontend
npm run collect:x
```

The manual collection defaults to Brand `18`. Override it with
`SOCIAL_X_CANARY_BRAND_ID=<ID>` when needed.

## Production boundary

No production callback or runtime switch is changed by this work. A later production
activation must register the exact callback
`https://social.theaccumulate.com/api/social/x/oauth/callback`, inject credentials
outside Git, and explicitly enable the account, collection and time-boxed activation
gates.

X API reads are pay-per-usage. Review the X Developer Console spending limit before
production activation; the implementation intentionally bounds each account to one
timeline page per run.

Official references:

- <https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code>
- <https://docs.x.com/fundamentals/authentication/oauth-2-0/user-access-token>
- <https://docs.x.com/x-api/users/lookup/quickstart/authenticated-lookup>
- <https://docs.x.com/x-api/users/get-timeline>
- <https://docs.x.com/x-api/fundamentals/metrics>
- <https://docs.x.com/x-api/getting-started/pricing>
