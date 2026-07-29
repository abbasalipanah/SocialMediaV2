# Social Media V2

Independent, downstream-owned rebuild of the Social Media application. The repository is
developed under the safety and migration rules in
[`docs/SOCIAL_MEDIA_V2_MASTER_PLAN.md`](docs/SOCIAL_MEDIA_V2_MASTER_PLAN.md).

## Current status

- Historical Phase 0–9 reports exist, but the repository must not currently be represented as
  `RELEASE_CANDIDATE_COMPLETE`. The status correction is recorded in the master plan and the
  Phase 7/8 reports.
- On 2026-07-17 the frontend shell was realigned to the Performance Marketing reference and the
  Social overview/platform surfaces were rebuilt from Accumulate's active Social render chain.
- The local frontend candidate passes strict TypeScript, production build and `19` Vitest tests;
  desktop, full-page and mobile browser smoke checks are green.
- The authenticated shell includes a Social-only Integrations catalog for Facebook, Instagram and
  TikTok, backed by the existing account, connection, capability, readiness and sync status APIs.
- TikTok now has a Brand-scoped self-service OAuth surface in Integrations. It is independent of
  the fresh owner-SSO handoff, remains fail-closed when provider activation is not configured, and
  never exposes provider tokens to the frontend.
- Facebook and Instagram now share a Brand-scoped Meta self-service flow: one explicit Meta login
  discovers Facebook Pages and linked Instagram Business profiles, then a separate explicit
  selection command attaches only the chosen accounts to the Brand.
- Meta OAuth state is session/Brand-bound and one-time, while provider credentials remain encrypted
  behind the backend vault. The default and local demo environments keep real Meta activation off.
- The real TikTok OAuth runtime is composed automatically behind explicit database, vault,
  provider-secret and time-boxed activation gates; the default and local demo environments keep
  those gates off.
- The full canonical release gate still requires a refreshed immutable-source baseline check and
  complete quality rerun.
- Production DB access, provider activation, workers and schedules remain disabled.

## Verification

Frontend parity verification:

```bash
cd frontend
npm test -- --run
npm run build
```

The full certification path remains `./scripts/quality/ci_check.sh`; it also checks the
read-only source baselines, backend, artifacts and vocabulary. A baseline mismatch is a release
blocker, not a reason to skip the guard.

## Local product demo

Run the frontend and its loopback-only demo backend together from the repository root:

```bash
./scripts/dev/start_local.sh
```

Then open `http://127.0.0.1:3010/`. The explicit local demo mode creates an in-memory session,
Brand hierarchy, linked social accounts and reporting rows. It does not use a production
database, external identity handoff, provider credentials or provider network calls. Stop both
processes with `Ctrl+C`.
