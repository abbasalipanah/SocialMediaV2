# Social Media V2 cutover — Phase B candidate certification

Date: `2026-08-13`

Status: `PHASE_B_COMPLETE / CANDIDATE_NOT_YET_PROMOTED / PUBLIC_CHANGE_NOT_AUTHORIZED`

## Outcome

A fresh, independent V2 candidate was created from the current live V1 data. The source
transaction was `REPEATABLE READ` and explicitly `READ ONLY`; the target was a different empty
database with the exact `0001`–`0004` migration set.

Exact row streaming, Brand/platform scope, DB-referenced media size/SHA-256, credential
plaintext-in-memory, AES-256-GCM nonce, and connection projection parity all passed.

V1 traffic and collection stayed active. Accumulate, public Nginx, V1 files/services/timers, and
the current V2 runtime env were not changed.

## Candidate identity

- DB: `social_media_v2_shadow_20260813_1045`
- media: `/var/lib/social-media-v2/candidates/20260813_1045/media`
- media: `6,524` files, `1,629,815,048` bytes
- media manifest SHA-256:
  `fbd2b63549fbe5b49c8c5268e320d047dbf79bf94353f9745288b48e624aac8f`
- candidate env SHA-256:
  `cc141fce192da3ecd9dd3cf705e87924fdd54d073621098bfd66127e9b3b1d44`

The candidate media lives under `/var/lib/social-media-v2`, the only writable data boundary
granted to the hardened V2 systemd services. It is separate from both V1 and the previous V2
candidate.

## Data parity

| Surface | Verified rows |
|---|---:|
| Brands | 68 |
| Assets | 93 |
| Platform connections | 72 |
| Linked social accounts | 99 |
| Metrics | 1,567,094 |
| Content | 6,624 |
| Comments | 3,608 |
| Media rows/files | 6,524 |
| Meta account inventory | 358 |
| AI insights | 6 |

The verifier re-ran after the media directory's final placement and passed all streamed rows,
scope groups, and file checksums.

## Credential parity

| Surface | Verified count |
|---|---:|
| Legacy connections | 72 |
| Meta connection projections | 70 |
| TikTok connection projections | 2 |
| Access credentials | 168 |
| Refresh credentials | 2 |
| AES-256-GCM credential rows | 170 |
| Unique nonce claims | 170 |

Every credential was decrypted/compared only in process memory and stored only as V2 vault
ciphertext. Four cross-Brand links and one intentionally unbound link retained their source
semantics. No credential value was printed or written to Git.

The migration scripts require the backend module root on `PYTHONPATH` when executed by file path;
the successful command supplied it explicitly. The first preflight invocation failed at import
time before opening either database and made no target write.

## Isolation proof

- Active V2 runtime still uses `social_media_v2_shadow_20260810_0745` and its previous media root.
- Candidate DB/media are not referenced by an active service yet.
- V2 collection service/timer and every provider/schedule gate remain disabled.
- Public root still returns `307`; active upstream remains V1 on `127.0.0.1:52120`.
- Social Nginx SHA-256 still equals the Phase A value.
- Cutover-specific V1/Accumulate source guard passes.

Machine-readable evidence is in `docs/cutover/phase_b_candidate_certification.json`.

## Gate state

```text
PHASE_B_COMPLETE=true
PARALLEL_PREPROD_FRESH=true
DATA_PARITY_VERIFIED=true
CREDENTIAL_PARITY_VERIFIED=true
CANDIDATE_PROMOTED=false
V1_TRAFFIC_ACTIVE=true
V1_COLLECTION_ACTIVE=true
V2_COLLECTION_ACTIVE=false
PUBLIC_V2_ACTIVE=false
READY_FOR_ACCUMULATE_SSO_HANDOFF=false
```
