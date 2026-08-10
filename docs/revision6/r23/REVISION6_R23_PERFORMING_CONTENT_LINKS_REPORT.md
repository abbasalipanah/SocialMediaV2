# Revision 6 · R23 — All Performing Content type and permalink navigation

Date: `2026-08-10`

Status: `COMPLETE — V2 loopback certified`

Code commit: `97e47a0`

Release: `/opt/social-media-v2/releases/20260810T132946Z-r23content`

## Outcome

The shared All Performing Content table used by Facebook, Instagram and TikTok now separates the
content preview from its `Type`. The exact column order is `#, Content, Type, Date, Views, Reach,
Likes, Comments, Shares, Interactions`; the type chip is rendered from the typed
`DashboardContent.content_type` field.

When `DashboardContent.permalink` is a credential-free HTTP or HTTPS URL, the whole content cell
(cover, title and external content ID) links to the provider content in a new tab with
`noopener noreferrer`. Empty, malformed, credential-bearing or non-HTTP(S) values remain visibly
non-clickable. The frontend does not invent or reconstruct a provider URL.

The table keeps its existing maximum height, internal scrolling and sticky header behavior. No
dashboard API, backend model, collector, database, account scope, shell component or provider
configuration changed.

## Verification

| Check | Result |
|---|---|
| Frontend typecheck | pass |
| Frontend unit/component tests | `35 passed` |
| Canonical valid permalink | pass; exact `href` rendered |
| Missing permalink | pass; no link rendered |
| Full desktop/mobile Playwright | `17 passed`, `5 skipped` by explicit project applicability |
| Production build | pass; `2,537` modules transformed |
| Source/build/deployed PlatformPage chunk SHA | `6d95f691113a2ff067ff947b45be391eee386f66a5d1e6caa0f8d27cde631e50` |
| V2 API/web | active and healthy on loopback |
| V2 collection | service inactive, timer disabled |
| Protected-source guard | pass |
| V2 API/web warning journal since release | no entries |

Only `/home/api/colab_scripts/SocialMediadownstream` changed. SocialMedia, Accumulate,
Performance Marketing, provider state, DNS, TLS, shared Nginx and public routes were not mutated.

## Rollback

Immediate rollback inputs remain:

- backend: `/opt/social-media-v2/releases/20260810T131931Z-r22overview/backend`
- frontend: `/opt/social-media-v2/releases/20260810T131931Z-r22overview/frontend`

Public cutover remains blocked by the user until the full application re-certification is complete.
