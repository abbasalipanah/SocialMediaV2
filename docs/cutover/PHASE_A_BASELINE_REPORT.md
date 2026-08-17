# Social Media V2 cutover — Phase A baseline

Date: `2026-08-13`

Status: `PHASE_A_COMPLETE / PHASE_B_AUTHORIZED / PUBLIC_CHANGE_NOT_AUTHORIZED`

## Outcome

The pre-change boundary is recorded. Social Media V1 and Accumulate are protected by a new,
cutover-specific fingerprint guard. The guard captures their already-existing dirty working-tree
states without accepting or replacing the older Revision 6 baseline.

No V1 or Accumulate file, DB row, service, timer, Nginx route, or public target was changed. The
new guard passed immediately after capture. V2 provider and worker schedule gates remain closed.

## Protected source boundary

The machine-readable baseline is
`docs/cutover/phase_a_protected_source_baseline.json`; verification is:

```bash
backend/.venv/bin/python scripts/quality/parallel_cutover_source_guard.py verify
```

| Project | Branch | HEAD | Existing status entries | Content files |
|---|---|---|---:|---:|
| Social Media V1 | `feature/tiktok-integration` | `a6de5d6b6517481c0b8feeb0baac10358d06f563` | 42 | 360 |
| Accumulate | `feature/social-ai-insights-ui` | `7d65db2da0a9c7cb866e984422b22bd5d8a1b5f7` | 7 | 1,411 |
| Active Accumulate runtime | `main` | `8cef416858107f1b139be529e320706e22b7d7fa` | 3 | 1,520 |

These trees were already dirty when Phase A began. Their exact status, tracked diff, origin, and
content fingerprints are stored as SHA-256 values. The active Accumulate runtime path was added as
a supplemental baseline before the first SSO secret read; secret env contents are excluded from its
content manifest while their Git status presence remains fingerprinted. The historical Revision 6
guard still reports pre-existing drift in V1 and `performance_marketing`; its baseline was
intentionally not replaced.

## Runtime and routing baseline

- V1 backend is active/enabled and healthy on `0.0.0.0:52120`.
- All currently enabled V1 provider/data timers remain active.
- Public `https://social.theaccumulate.com/` returns `307`; active Nginx upstream remains
  `127.0.0.1:52120`.
- Active Social Nginx config SHA-256 is
  `cd8adfd9dfea26078f534fc8b4b0a9b853359f540d6d43329b7c041acd9e3668`.
- V2 API and web are healthy on loopback ports `8026` and `3026`.
- V2 collection service and timer are inactive/disabled.
- All Meta, TikTok, activation, collection, advertiser, and worker schedule gates are disabled.
- V2 API/web journal contains no warning-or-higher entries in the capture window.

## Read-only database snapshot

Both snapshots used `REPEATABLE READ` transactions with `transaction_read_only=on`.

| Table | V1 | Existing V2 |
|---|---:|---:|
| Brands | 68 | 67 |
| Assets | 366 | 91 |
| Platform connections | 72 | 71 |
| Linked social accounts | 99 | 97 |
| Daily metrics | 1,567,094 | 1,493,502 |
| Content items | 6,624 | 6,234 |
| Comments | 3,608 | 3,362 |
| Media rows | 6,524 | 6,101 |

The existing V2 database has the exact `0001`–`0004` migration set. It is retained as rollback
input; Phase B will create a new empty candidate rather than overwrite it.

## Media snapshot

| Root | Files | Bytes | Manifest SHA-256 |
|---|---:|---:|---|
| V1 | 6,655 | 1,642,263,522 | `5584b4d14ff0a159e377528fa19b284bf79aa51e8b6a3327b3d7c67951f19151` |
| Existing V2 | 6,101 | 1,516,985,160 | `cf1ae2885d26f4f38a9449260bb3f140fdc3d2b1cd7e54365207afbf56a5f891` |

V1 has more filesystem entries than DB media rows. Phase B's importer copies and verifies only
the exact DB-referenced set and rejects extra files in the candidate target.

The complete non-secret runtime record is in `docs/cutover/phase_a_runtime_baseline.json`.

## Gate state

```text
PHASE_A_COMPLETE=true
V1_PROTECTED_SOURCE_UNCHANGED=true
ACCUMULATE_PROTECTED_SOURCE_UNCHANGED=true
V1_TRAFFIC_ACTIVE=true
V1_COLLECTION_ACTIVE=true
V2_COLLECTION_ACTIVE=false
PUBLIC_V2_ACTIVE=false
READY_FOR_ACCUMULATE_SSO_HANDOFF=false
```
