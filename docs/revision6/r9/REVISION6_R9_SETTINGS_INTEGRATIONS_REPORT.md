# Revision 6 R9 — Settings, Integrations and RBAC Report

Date: `2026-08-09`

Status: **COMPLETE — V2 SOURCE/CONTRACT ONLY; NO LIVE SOURCE PROJECT CHANGED**

## Product outcome

- The Social Media navigation tree contains only Facebook, Instagram and TikTok.
- Exactly one Settings link remains in the sidebar footer.
- Integrations is a separate footer link and authenticated route.
- Settings uses the active Performance Marketing table-first composition: header actions, six
  summary cards, Brands, Platform Accounts, Mappings and Sync & Backfill tabs.
- Integrations uses its own stored-status API surface and does not borrow Settings authority.

## Authority outcome

| Surface | Allowed authority |
|---|---|
| Settings UI and `/api/settings/*` | `super_admin`, `agency_admin` |
| Integrations UI/status/connection | `super_admin`, `agency_admin` |
| Integrations scoped exception | Accumulate `viewer` with signed `app_role=admin|operator`, exact session Brand, non-rollup |
| All other roles/combinations | fail-closed |

The legacy signed `settings_visible` boolean remains contract-shape input but cannot widen
Settings access. V2 derives the decision from the canonical workspace role. Optional signed
`app_role` is preserved in the hash-only local session and auth response.

## Backend and API

- Added integration-scoped stored query endpoints for social accounts, connections and sync jobs.
- Added `integrations_visible` to auth/workspace capability contracts.
- Meta and TikTok self-service connection authority now shares the same exact Brand-scoped rule.
- Settings and Integrations checks are enforced before reporting-store queries or provider work.
- OpenAPI and generated TypeScript types were regenerated deterministically.

## Verification

- Backend: Ruff clean; `124 passed`, `16 skipped` because external PostgreSQL test URLs are not
  configured on this host.
- Frontend: `25 passed`; TypeScript typecheck and Vite production build passed.
- Wheel build, canonical vocabulary guard and repository secret scan passed.
- OpenAPI `--check` passed.
- The local `npm run dev` launcher now watches V2 backend application files, preventing a new
  frontend bundle from running against a stale in-memory Python contract. A real headless browser
  rendered Facebook Dashboard with zero session error, one Settings link and one Integrations link.
- `scripts/source_write_guard.sh` passed: SocialMedia, Accumulate and performance_marketing
  approved Git/content baselines are unchanged.

No source project service, DB, process, timer, route, configuration or repository was changed.
No commit, push or deployment was performed in this R9 implementation turn.
