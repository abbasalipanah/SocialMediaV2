# Revision 6 / R6 Standalone Runtime ve SSO-Only Raporu

Tarih: 2026-08-07

Durum: `R6_LOCAL_CERTIFIED`

R6 yalnız `/home/api/colab_scripts/SocialMediadownstream` içinde uygulanmıştır. Canlı
`SocialMedia`, `Accumulate` ve `performance_marketing` projelerinde kod, config, DB, media,
process, port, servis, timer, routing, build veya test değişikliği yapılmamıştır. Source-write
guard başlangıç ve bitiş kontrolleri geçmiştir.

## Sonuç

- Runtime sözleşmesi yalnız `development → dormant → staging → standalone_ready → active`
  durumlarından oluşur. Beş tarihsel `cutover_*` modu backend enum, OpenAPI, generated TypeScript
  ve frontend runtime contract'ından çıkarılmıştır.
- WritePolicy yalnız disposable development, V2-owned staging ve explicit active production
  modlarında yazmaya izin verir. `dormant` ve `standalone_ready` her koşulda write-disabled'dır.
- Production env örneği artık `standalone_ready`, writes off, vault off, Meta/TikTok account ve
  collection off, activation gates off ve schedule off başlar. Doğrudan active writer başlatmaz.
- Normal signed SSO launch R1 canonical `/settings` yoluna; owner target yalnız
  `/settings/tiktok/connect` yoluna çözülür. `/auth/sso/consume` frontend alias'ı tokenı canonical
  same-origin `/sso/consume` backend endpoint'ine taşır.
- Canonical `docs/contracts/social-media-v2-sso-only.md` oluşturulmuştur. Tarihsel
  `sso-provisioning` yolu ve Faz 2/Faz 9 provisioning/cutover belgeleri açıkça
  `ARCHIVED / SUPERSEDED` işaretlenmiştir.
- Accumulate handoff metni `DRAFT — GÖNDERİLMEDİ` durumundadır ve
  `STANDALONE_RUNTIME_COMPLETE` öncesinde kullanılmaz.
- API start'tan otomatik migration kaldırılmıştır. Migration ayrı, install target'ı olmayan
  explicit `social-media-v2-migrate.service` one-shot artifact'idir.
- API, migration, collector, timer, Nginx, journal, health/readiness ve yalnız V2 yüzeylerini
  hedefleyen rollback runbook artifact'leri ayrılmıştır. Bunların hiçbiri hosta kurulmamış veya
  etkinleştirilmemiştir.
- Runtime/import/path scan production yüzeyinde source-project absolute path/import,
  provisioning endpoint/port, inbox/outbox consumer, shared DB/filesystem veya V1 proxy bulmaz.

## Runtime gate davranışı

| APP_ENV / runtime | Writes | Provider egress / schedule | Sonuç |
|---|---:|---:|---|
| development / development | explicit | explicit local fixture | yalnız local V2 DB |
| any / dormant | off | off | fail-closed |
| staging / staging | explicit | ayrı explicit gates | yalnız V2-owned staging |
| production/staging / standalone_ready | off | off | güvenli ilk başlangıç |
| production / active | explicit | ayrı explicit gates | R7/R8 ve operasyon onayı gerekir |

Production-like writable runtime güçlü SSO secret, Secure cookie, `social_media_v2*` isimli
dedicated DB URL ve remote DB için TLS olmadan boot etmez. Scheduled collector flag kapalıysa DB
bağlantısı/provider egress öncesinde reddedilir.

## SSO-only ve authorization kanıtı

Backend testleri şu sınırları doğrular:

- yalnız HS256, conditional-v1 issuer, exact audience/app/token type ve signature;
- expiry/access window, canonical role/access/visibility invariant'ları;
- hash-only JTI ve session, atomic replay rejection, 12 saatlik üst sınır;
- signed single-Brand veya parent/child Brand scope, hidden parent rollup ve cross-Brand denial;
- same-origin logout, session revoke ve expiry sonrası access denial;
- allowlisted default/owner launch target, arbitrary path/URL rejection;
- `/internal/provisioning/events` için `404` ve başka authority ingress'i bulunmaması;
- fresh owner SSO context/capability ve fail-closed provider activation davranışı.

## Canonical frontend parity sayımları

R6 normal dashboard render sözleşmesini değiştirmemiştir:

| Ölçüm | Matched | Unavailable | Blocked |
|---|---:|---:|---:|
| R1 canonical card/section ID | 51 | 0 | 0 |
| R6 nedeniyle eklenen görünür dashboard kartı | 0 | 0 | 0 |
| R6 nedeniyle kaldırılan/değiştirilen görünür dashboard kartı | 0 | 0 | 0 |

Owner-only hidden activation yüzeyindeki “before cutover” metni runtime-policy terminolojisine
dönüştürülmüştür; normal Facebook/Instagram/TikTok kart matrisi değişmemiştir. Canonical
`Not provided by TikTok Organic API` unavailable cümlesi vocabulary guard'da yalnız exact copy
için dar allowlist alır; platform kimliği olarak `*_organic` üretimine izin verilmez.

## Değişen yalnız V2 alanları

- Runtime/config/policy: `backend/app/core/config.py`, `core/__init__.py`, `write_policy.py`,
  worker runtime/CLI ve package açıklamaları.
- SSO/API: `backend/app/application/services/sso.py`, auth/operations/settings davranışı ve
  R6/SSO contract testleri.
- Frontend: SSO consume alias davranışı, runtime Zod/OpenAPI contract'ı ve hidden owner activation
  runtime-policy metni.
- Generated contract: `docs/contracts/social-media-v2-openapi.json` ve
  `frontend/src/api/openapi.generated.ts`.
- Deploy: güvenli production env, API/collector systemd güncellemeleri ve ayrı migration unit'i.
- Dokümantasyon: canonical SSO-only contract, standalone runbook, guarded Accumulate handoff ve
  tarihsel archive/supersede marker'ları.
- Kalite: `revision6_r6_runtime.py`, `revision6_r6_runtime_check.sh`, güncel offline env assertion'ı
  ve exact canonical unavailable copy için dar vocabulary allowlist'i.

## Doğrulama sonuçları

`./scripts/quality/revision6_r6_runtime_check.sh` temiz çıkış koduyla tamamlanmıştır:

- Source-write guard başlangıç/bitiş: pass.
- R6 statik runtime/deploy scan: `193` dosya, pass.
- Runtime mode contract: `5/5`, pass.
- Python Ruff: pass.
- Backend tam test seti: `122 passed`, `16 skipped`.
- OpenAPI export + frontend type generation: pass.
- Frontend Vitest: `23 passed`.
- TypeScript typecheck + production build: pass.
- Git whitespace/diff kontrolü: pass.

On altı backend skip'i canlı eksikliği değildir; `TEST_POSTGRES_URL` veya ayrı parity PostgreSQL
URL'leri verilmediği için yalnız disposable PostgreSQL integration testleridir. R7 bunları geçici
V2-owned PostgreSQL üzerinde koşacaktır. Build'deki 500 kB chunk uyarısı non-blocking'dir.

## Açık dış işler ve durum bayrakları

- V2-owned staging DB/user/TLS/secret/runtime oluşturulmamış ve deploy edilmemiştir.
- Provider callback/secret panel doğrulaması, Meta/TikTok sandbox/canary ve owner consent
  yapılmamıştır.
- Accumulate handoff gönderilmemiş ve Accumulate tarafında değişiklik yapılmamıştır.
- V1 tarihsel veri/token/media kopyalanmamıştır. Ayrı DB import işi, salt-okunur export rehearsal
  ve ayrıca açık kullanıcı/Operations onayı olmadan yapılmaz.
- `STANDALONE_PRODUCT_COMPLETE`: false
- `STANDALONE_RUNTIME_COMPLETE`: false
- `READY_FOR_ACCUMULATE_SSO_HANDOFF`: false
- `SSO_LIVE_VERIFIED`: false
- `TIKTOK_CONNECTION_VERIFIED`: false

R6 local code/artifact kapısı tamamlanmıştır. Sonraki normatif adım R7 Standalone Product Complete
yeniden sertifikasyonudur. R7 yalnız V2-owned disposable yüzeylerde çalışır; staging/production
veya dış sistem işlemi içermez. R8 için yeni operasyon yetkisi gerekecektir.
