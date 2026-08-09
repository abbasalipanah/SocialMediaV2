# Writer Ownership Cutover Checklist — Unexecuted Draft

> **ARCHIVED / SUPERSEDED:** Revizyon 6 V2'nin V1 writer sahipliğini devralmasını yasaklar. Bu
> belge uygulanamaz; güncel standalone akış `docs/STANDALONE_DEPLOYMENT.md` içindedir.

This checklist is **not** a cutover authorization. Every production step requires a new explicit approval after the V2 Release Candidate Complete gate.

## Preconditions

- [ ] Faz 0–9 certification is green at the reviewed commit.
- [ ] Source guards match SocialMedia `e69fc5c7e0f1648f1f8215aa98915c48f53943e0` and Accumulate `7d65db2da0a9c7cb866e984422b22bd5d8a1b5f7` or an explicitly re-reviewed successor baseline.
- [ ] Full V1 writer inventory covers API commands, timers, workers, manual CLI, backfill, repair, one-shot jobs, provisioning ingress and media writes.
- [ ] Online-consistent database backup and media snapshot have a successful restore rehearsal.
- [ ] Accumulate outbox patch is reviewed, rebased and tested but not yet routed to V2.
- [ ] V2 is dormant; writes, TikTok account OAuth, collection and advertiser gates are off.
- [ ] Rollback owner, observation window, writer fence and approval records are assigned.

## Read-only preflight

- [ ] Re-capture process/unit/timer/lock/manual-writer inventory.
- [ ] Use a read-only credential to compare the approved schema fingerprint and data invariants.
- [ ] Start only the read-only API under the approved dark route.
- [ ] Verify health, SSO, projections, dashboards and Settings without commits or provider calls.
- [ ] Record final V1 queue state, media checksum and data high-water marks.
- [ ] Abort on any mismatch; V1 continues unchanged.

## Short writer-fence window

- [ ] Fence every inventoried V1 mutation ingress; do not kill in-flight work.
- [ ] Wait for in-flight transactions/jobs and prove zero V1 writer/lock remains.
- [ ] Migrate credentials only under the dedicated migration policy; verify counts/decryption in memory and rollback restoration.
- [ ] Run isolated control-plane and social-data canaries; reconcile all effects before proceeding.
- [ ] Record Accumulate emitted watermark and pending/failed inventory from the oldest row.
- [ ] Requeue failed events explicitly; do not silently skip history.
- [ ] Emit the full `brand_access.sync` snapshot at ordered sequence `S`.
- [ ] Route provisioning first and drain every `sequence <= S`; require `S` applied/acknowledged.
- [ ] Drain post-snapshot events, freeze authority briefly, emit final barrier `Hf`, and require applied watermark `Hf`, zero lag, and zero pending/failed rows.
- [ ] Only then enter activation mode and coordinate token scrub, SSO launch routing and active write policy.
- [ ] Verify the first post-freeze authority event is applied before enabling any worker family.
- [ ] Enable worker families one by one; keep TikTok automated collection off until its separate owner/canary gate passes.

## Stop conditions

Any schema mismatch, unknown writer, nonzero projection lag, failed outbox row, token-count mismatch, provider-family mismatch, unexpected Brand write or missing rollback evidence cancels the cutover. Follow the rollback checklist without opening both writer families.
