# Social Media V2 Dashboard and Operations API Contract

Tarih: `2026-07-14`

Bu sözleşme salt-okunur dashboard/Settings yüzeyini ve V2-owned operasyon sınırlarını tanımlar.

## Scope ve authorization

- Her dashboard, account, Settings, insight ve media isteği local session doğrular.
- `brand_id` seçimi imzalı SSO session kapsamı içinde çözülür.
- `rollup=true`, yalnız kullanıcının erişebildiği active child Brand kimliklerini döndürür.
- Account filtresi resolved Brand scope dışındaysa `dashboard_account_scope_denied` ile kapanır.
- Settings route'ları role string'iyle değil signed session `settings_visible` capability'siyle
  açılır.
- Her response requested Brand, rollup kararı, resolved Brand ve account kimliklerini taşır.

## Dashboard response

Canonical endpoint'ler:

```text
GET /api/dashboards/overview
GET /api/dashboards/facebook
GET /api/dashboards/instagram
GET /api/dashboards/tiktok
```

Desteklenen range anahtarları `last_7_days | last_30_days | last_90_days` değerleridir. Custom
range için `start_date` ve `end_date` birlikte zorunludur; en fazla 366 gün kabul edilir. Default
range D-1'de biter. Opsiyonel `account_id`, `content_type` ve `tab` filtreleri backend'de uygulanır;
`stories` yalnız Instagram'a aittir.

Typed response:

- `meta`: requested/resolved scope, date range, generated/last-sync, freshness, observed/expected
  days, overall data status ve warnings;
- `metrics`: canonical metric ID, current/previous value, delta, semantic type, unit ve data status;
- `series`: metric semantic type ile günlük noktalar;
- `breakdowns`: dimension, değer ve percentage;
- `content`: recent/top sıralamasına uygun content kartları;
- `community`: answered/unanswered ve comment-like özeti.

Overview aynı DTO ailesindeki platform dashboard'larını içerir. Frontend child veya account
response'larını kendisi toplayıp merge etmez.

## Metric semantiği

- Snapshot ve cumulative metric, dönem boyunca toplanmaz; account başına son geçerli sample
  alınır, sonra catalog rollup kuralıyla toplanır.
- Flow metric uyumlu dönem/account satırları üzerinden toplanır.
- Ratio yeniden numerator/denominator üzerinden hesaplanır; ratio değerleri toplanmaz veya basit
  ortalama yapılmaz.
- TikTok cumulative delta, ilk sample'ı flow saymaz; reset/decrease negatif flow üretmez.
- Missing metric `0` yapılmaz. `value=null`, `data_status=unavailable` ve warning döner.
- Account'ların yalnız bir kısmında veri varsa metric `partial` olur.

## Accounts, Settings, insights ve readiness

```text
GET /api/platforms/{facebook|instagram|tiktok}/accounts
GET /api/settings/brands
GET /api/settings/social-accounts
GET /api/settings/brand-links
GET /api/settings/connections
GET /api/settings/sync-jobs
GET /api/settings/audit
GET /api/settings/tiktok/connection
GET /api/insights
GET /api/operations/readiness
GET /api/workspace/capabilities
```

Yalnız stored data okunur. GET route'ları setup ensure/recalculate, token refresh, provider fetch,
media persistence, job enqueue, commit veya upsert yapamaz. Audit store bu fazda yapılandırılmamışsa
boş ama dürüst `unavailable` cevabı döner. Stored AI insight okunur; GET LLM generation başlatmaz.
Connection DTO token/credential/source URL içermez.

Workspace capability cevabındaki her platform kaydı `linked_account_count` ve
`navigation_available` taşır. Navigation availability, seçili backend scope'unda stored linked
account bulunması veya ilgili capability'nin `available/partial` olmasıyla belirlenir; frontend
rol ya da label'dan availability türetmez. Capability yalnız ilgili V2 collector ayarı gerçekten
açıksa `available/partial` olur.

## Media proxy

`GET /api/media/{platform}/{content_id}` yalnız authorized Brand/account kapsamındaki persisted
media metadata ve configured local media root'u kullanır. Path root dışına çıkamaz; dosya size ve
SHA-256 metadata ile eşleşmeden servis edilmez. Provider fallback, fetch veya persistence yoktur.

## Operasyon komutları

```text
POST /api/operations/sync
POST /api/operations/backfill
DELETE /api/settings/tiktok/connection
```

Bu HTTP komutları same-origin, concrete Brand ve write access doğrular. Merkezi `WritePolicy`
kapalıyken `writes_disabled` döner. Provider collection ayrı V2 worker entrypoint’inden çalışır;
V1'e proxy veya remote trigger yoktur.

## OpenAPI ve çıkış kapısı

Dashboard, accounts, Settings, connection, insights, readiness ve workspace capability response
modelleri OpenAPI component schema olarak yayınlanır. Canonical platform enum exact olarak
`facebook | instagram | tiktok` değerleridir.

Faz 6 çıkış kapısı:

- feature matrix satırlarının tamamı implemented veya explicit honest-unavailable olmalı;
- parent rollup/cross-Brand/account scope testleri yeşil olmalı;
- snapshot/flow/cumulative/ratio ve missing-is-not-zero testleri yeşil olmalı;
- bütün GET'lerde DB row count ve authority state değişimi sıfır olmalı;
- media root escape ve checksum mismatch fail-closed olmalı;
- OpenAPI response contract testi exact schema referanslarını doğrulamalı.
