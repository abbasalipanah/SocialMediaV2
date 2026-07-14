# Social Media V2

Independent, downstream-owned rebuild of the Social Media application. The repository is
developed under the safety and migration rules in
[`docs/SOCIAL_MEDIA_V2_MASTER_PLAN.md`](docs/SOCIAL_MEDIA_V2_MASTER_PLAN.md).

## Current status

- Phase 0: immutable source baselines and downstream-only write guard complete.
- Phase 1: fail-closed backend/frontend bootstrap complete.
- Phase 2: SSO, local session and signed provisioning implementation complete; source
  immutability and disposable PostgreSQL exit gates are green. Closure evidence is tracked in
  [`docs/fase2/Faz2_SSO_Provisioning_Report.md`](docs/fase2/Faz2_SSO_Provisioning_Report.md).
- Phase 3: parent/child authority projection, hidden-parent rollup and cross-brand authorization
  gates are complete.
- Phase 4: backend independence and platform capability ports are next.
- Production DB access, provider activation, workers and schedules remain disabled.

## Verification

Local certification uses a disposable PostgreSQL container and also verifies the three
read-only source repositories:

```bash
./scripts/quality/fase2_contract_check.sh
```

GitHub Actions runs the self-contained downstream checks through
`./scripts/quality/ci_check.sh` with hash-locked Python dependencies, a PostgreSQL 16 service,
clean npm installation, production builds and artifact vocabulary scanning.
