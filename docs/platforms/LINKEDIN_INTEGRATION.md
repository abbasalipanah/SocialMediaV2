# LinkedIn integration

## Implemented scope

LinkedIn is implemented for administered Company Pages only. Personal profile
analytics are outside this integration. The implementation includes:

- OAuth 2.0 Authorization Code with `rw_organization_admin` and
  `r_organization_social`. LinkedIn names the reporting/admin permission `rw`, while
  this integration's transport remains GET-only and exposes no write operation;
- discovery and explicit Brand linking of Company Pages administered by the signed-in
  LinkedIn member;
- follower totals, daily follower gains, organic post impressions, unique impressions,
  clicks, engagements, engagement rate, and Company Page views;
- supported follower facets for company size and association type;
- published organic Company Page posts and their impressions, unique impressions,
  clicks, likes, comments, shares, and engagement rate;
- one post page of at most 25 records per collection run, with a durable cursor and a
  rolling 12-month analytics boundary.

Comments as a separate community feed, personal-profile reporting, and unsupported
audience demographics are deliberately not collected or inferred. The local canary
keeps scheduled collection disabled.

## LinkedIn Developer application

Use a dedicated development app associated with the Accumulate LinkedIn Company Page.
Request/enable the Community Management API product and configure this exact local
redirect URL:

```text
http://localhost:8126/api/social/linkedin/oauth/callback
```

The authorizing LinkedIn member must be an approved administrator of each Company Page
that should appear during discovery. Development-tier API access is sufficient for the
bounded local canary; production access review is a separate rollout decision.

## Local credential contract

Create the ignored file `.secrets/socialmedia/linkedin-dev-oauth.json` with mode
`0600`:

```json
{
  "web": {
    "client_id": "VALUE_FROM_LINKEDIN_DEVELOPER_PORTAL",
    "client_secret": "VALUE_FROM_LINKEDIN_DEVELOPER_PORTAL",
    "redirect_uris": [
      "http://localhost:8126/api/social/linkedin/oauth/callback"
    ]
  }
}
```

The launcher validates the file and exact callback before exporting credentials to the
backend child process. `.secrets/` is ignored by Git; never force-add this file.

## Local run and collection

From the isolated worktree:

```bash
cd frontend
npm run dev
```

Open `http://localhost:8126/integrations`, authorize LinkedIn, then use Settings to
select and link the discovered Company Page to the intended Brand. Collect LinkedIn
into the isolated development database only:

```bash
cd frontend
npm run collect:linkedin
```

The command defaults to Brand `18`. Set
`SOCIAL_LINKEDIN_CANARY_BRAND_ID=<ID>` when testing another local Brand. Re-run the
command until the account reports a completed content backfill, then refresh the
LinkedIn dashboard.

## Production boundary

This work does not register or enable the production callback, alter the live runtime,
or deploy the feature. Production activation later requires the exact callback
`https://social.theaccumulate.com/api/social/linkedin/oauth/callback`, credentials
injected outside Git, approved API access, and explicit activation of the account,
collection, write, and time-boxed release gates.

Official references:

- <https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow-native>
- <https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access>
- <https://learn.microsoft.com/en-us/linkedin/marketing/community-management/organizations/organization-access-control-by-role>
- <https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api>
- <https://learn.microsoft.com/en-us/linkedin/marketing/community-management/organizations/share-statistics>
- <https://learn.microsoft.com/en-us/linkedin/marketing/community-management/organizations/follower-statistics>
- <https://learn.microsoft.com/en-us/linkedin/marketing/community-management/organizations/page-statistics>
