# Rollback Checklist — Unexecuted Draft

Rollback preserves the sole-writer invariant; it does not simply reverse mode names.

- [ ] Hold new SSO launches and keep V1 mutation ingress fenced.
- [ ] Disable all V2 mutations, provider egress and future writer selection.
- [ ] Let safe in-flight V2 work finish; stop and mask V2 processes.
- [ ] Prove zero V2 process, writer lock, transaction and scheduled entry remains.
- [ ] Reconcile canary/active database, checkpoint and media effects from the reviewed manifest.
- [ ] Restore the latest encrypted credentials to the approved rollback format without logging plaintext.
- [ ] Route Accumulate provisioning to V1 first.
- [ ] Emit/replay a versioned full authority snapshot and drain until V1 applied watermark equals emitted watermark with no pending/failed rows.
- [ ] Route SSO launch back to V1 only after control-plane restore is green.
- [ ] Re-enable inventoried V1 mutation ingress families one by one.
- [ ] Verify health, prior-day coverage, rate guards, backfill state and media checksums.
- [ ] Keep additive V2 projection rows for incident review; do not delete them during emergency rollback.

If credential restoration, control-plane drain or zero-writer evidence fails, keep both writer families closed and escalate. Never run V1 and V2 writers concurrently on the same production scope.
