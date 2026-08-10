# Revision 6 / R15 — Thin Overview trends and weekly V2 AI Summary

Date: `2026-08-10`

## Outcome

Overview now uses the reference's thin chart treatment and exposes a real `AI Summary` surface.
The existing V2 sidebar, topbar, footer, Home route, Brand scope, and three-platform information
architecture were not changed.

All writes stayed inside `/home/api/colab_scripts/SocialMediadownstream` or its isolated local V2
database. The protected SocialMedia, Accumulate, and performance_marketing Git/content baselines
remain unchanged. No protected runtime, database, service, timer, or provider configuration was
modified.

## Frontend contract

- Mini sparkline strokes are `1.15`; Performance Trend strokes are `1.35`; chart grids are `.55`
  with low contrast.
- The canonical card/drawer name is `AI Summary`, not Alerts & Opportunities or AI Insights.
- The card previews the latest completed strategic summary and stored action titles.
- The accessible drawer lists only completed previous summaries and renders Strategic Summary,
  Channel Analysis, Anomalies, Recommended Actions, Platform Evaluations, period, model, and
  generation date.
- Opening the card is read-only and never generates a summary.
- Only an exact Accumulate `viewer` + signed `app_role=operator` session on its exact Brand and
  non-rollup scope sees generation availability. Other roles can read in-scope stored history but
  cannot trigger generation.

## Backend and weekly-limit contract

The typed routes are:

```text
GET  /api/insights
GET  /api/insights/limit
POST /api/insights/generate
```

The backend repeats the exact authorization check and requires same-origin POST. Generation uses
a Brand-wide rolling `7x24 hour` window. A PostgreSQL advisory transaction lock serializes claims;
an active pending record blocks concurrent requests, stale pending records fail closed after 15
minutes, a completed record consumes the weekly allowance, and a failed attempt does not.

Stored output includes strategic summary, connector analysis, anomalies, action recommendations,
platform evaluations, model, status, period, creator subject, and timestamps. The migration adds
only these V2-owned fields and Brand/status indexes. Raw provider input is not persisted.

## Provider and privacy boundary

The V2 OpenRouter adapter is independently configured, endpoint/model allowlisted, and disabled by
default in the repository. By the user's explicit 2026-08-10 decision, the already approved shared
OpenRouter credential may be reused; a new key is not required. It is injected only into V2's
Git-ignored `0600` local runtime secret. The protected source file and runtime remain read-only,
and no credential is committed to source, Git, or documentation.

The provider payload is restricted to aggregate metrics, data availability, selected period, and
de-identified numeric statistics for at most five top content records. It excludes comments,
messages, content copy, usernames, permalinks, credentials, and raw persisted prompt snapshots.

## Pine Beach local evidence

The read-only importer applied migration `0004_ai_summary.sql` to the isolated V2 database and
refreshed Pine Beach Belek with `80,519` metrics, `395` content rows, `611` comments, `389` verified
media rows, and the legacy completed structured AI Summary. Source PostgreSQL access stayed
`transaction_read_only=on`; only non-secret structured output was copied.

Using the approved shared credential, a controlled real-provider canary generated a second Pine
Beach summary for `2026-07-11` through `2026-08-09`. It completed with `3` channel analyses, `2`
anomalies, `4` recommendations, and `3` platform evaluations. The backend then reported
`weekly_limit_reached`, `remaining=0`, and a next-available timestamp, proving that the successful
canary consumed exactly the Brand's rolling weekly allowance.

Real local Chromium verified:

- one AI Summary card and accessible history drawer;
- two completed previous summaries, with the new period selected first;
- Strategic Summary, Channel Analysis, Anomalies, Recommended Actions, and Platform Evaluations;
- mini/performance line strokes `1.15` and `1.35`;
- no generation button for the local agency-admin demo session;
- zero application HTTP or console errors.

A separate temporary V2-only runtime then consumed a real signed Accumulate-format
`viewer + app_role=operator` token in Chromium. It redirected to `/overview`, hid Settings,
showed Integrations, displayed the Generate Summary control as weekly-disabled, showed both
history records, returned `204` on logout, and produced zero browser/API errors. The temporary
`8001/3011` runtime was shut down after the check; the primary local runtime remained healthy.

## Verification

- Backend Ruff: passed.
- Backend pytest: `141 passed`, `18` environment-gated PostgreSQL tests skipped.
- Disposable isolated PostgreSQL adapter/weekly-limit suite: `3 passed`.
- Frontend Vitest: `29 passed`.
- Frontend TypeScript and production build: passed.
- Desktop Overview Playwright: passed.
- Pine Beach V2-local browser smoke: passed.
- OpenAPI routes and generated TypeScript contract: passed.
- Secret-leak and canonical-vocabulary guards: passed.
- Protected source Git/content baseline guard: passed.

The local real-provider canary is complete. Production secret injection and a controlled
production canary remain explicit deployment inputs; no production runtime was changed.
