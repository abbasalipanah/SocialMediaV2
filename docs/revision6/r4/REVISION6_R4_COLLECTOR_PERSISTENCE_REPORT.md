# Revision 6 / R4 Collector, Persistence ve Media Raporu

Tarih: 2026-08-07

Durum: `CODE_AND_LOCAL_CERTIFICATION_COMPLETE`

R4 yalnız `/home/api/colab_scripts/SocialMediadownstream` içinde uygulanmıştır. Canlı
`SocialMedia`, `Accumulate` ve `performance_marketing` projelerinde kod, yapılandırma,
veritabanı, media, process, port, servis veya routing değişikliği yapılmamıştır. Başlangıç,
ara ve bitiş source-write guard kontrolleri geçmiştir.

## Sonuç

- Facebook collector country/city audience değerlerini provider verisiyle yazar. Provider'ın
  sunmadığı age/gender/activity değerleri üretilmez ve unavailable kalır.
- Instagram posts/reels ve Stories ayrı checkpoint stream'leriyle toplanır. Media/Story insight
  alanları nullable olarak V2 veritabanına yazılır; expired ilk media URL'sinden sonraki doğrulanmış
  cover/thumbnail adayı atomik olarak saklanabilir.
- TikTok profile, paged videos, video insights, provider audience ve `comment.list` scope'u varsa
  comments akışı worker'a bağlanmıştır. Token her collector başlangıcında provider token-info ile
  scope/identity açısından yeniden doğrulanır; gerektiğinde refresh edilir.
- TikTok transport 429/5xx ve transport hatalarında bounded retry, `Retry-After`, toplam 500 istek
  bütçesi, response-size limiti ve body/secret içermeyen hata kodları kullanır.
- Audience breakdown güncellemesi aynı hesap/gün/metrik/dimension için atomik replace yapar; eski
  dimension satırları kalmaz. Eksik provider alanından sentetik `0` veya fixture veri üretilmez.
- Content/Story/TikTok watch ve media candidate alanları migration, persistence model, store ve
  reporting hydration boyunca korunur.

## V2 veritabanı sınırı

R4 migration'ı `0002_content_story_parity.sql` yalnız V2-owned `content_items` tablosuna nullable
provider alanlarını ve JSONB media adaylarını ekler. Disposable PostgreSQL üzerinde `0001` ve
`0002` iki kez çalıştırılarak checksum/idempotency doğrulanmıştır.

Bu fazda V1 veritabanından tarihsel veri, token veya media kopyalanmamıştır. V1'e runtime fallback
yoktur. Tarihsel export/import ayrı bir işlem olup mevcut planda otomatik değildir; ancak kullanıcı
ayrıca açıkça onaylarsa, canlı kaynağa yazmadan ve ayrı bir migration/import planıyla ele alınabilir.

## Değişen V2 alanları

- Collection services: audience projection, typed content fields, independent checkpoints ve
  durable media candidate fallback.
- Provider adapters: Meta audience/Instagram media+Story insights; TikTok content, audience,
  comments, exact wire fields ve bounded transport.
- Worker: Meta audience ve Instagram Stories; TikTok scope-aware comments/audience, token refresh
  ve partial sonuç bağlantıları.
- Persistence: content detail kolonları, atomic audience breakdown replacement ve reporting
  hydration.
- Configuration: canonical TikTok comment endpoint allowlist'i ve fail-closed endpoint seti.
- Tests/quality: PostgreSQL schema fixtures, replay/idempotency/media fallback, provider adapters,
  request budget/redaction ve `revision6_r4_collector_check.sh`.

Ayrıntılı makine-okunur eşleme: `r4_collector_persistence_mapping.json`.

## Kanıtlar

- R4 statik collector gate: pass.
- R4 backend hedef seti: `50 passed`.
- Disposable PostgreSQL migration: iki çalıştırma, `0001 + 0002`, pass.
- V2 persistence/reporting PostgreSQL seti: `6 passed`.
- Faz 5 collector differential sertifikasyonu: full `125 passed`; hedef `39 passed`; pass.
- Frontend regresyon: `22 passed`.
- Frontend typecheck + production build: pass. Yalnız mevcut 500 kB chunk uyarısı vardır; build
  hatası değildir ve görünür kart sözleşmesini değiştirmez.
- Source write guard: pass.

## Frontend parity durumu

R4 görünür frontend yapısını değiştirmemiştir: R1'deki 51 canonical kart/öğe tanımı korunmuştur;
yeni kart `0`, kaldırılan kart `0`, R4 nedeniyle blocked öğe `0`'dır. Provider unavailable
durumları mevcut typed contract ile açıkça gösterilir. Exact DOM/screenshot parity yeniden
sertifikasyonu R5'in konusudur.

## Açık dış işler ve status bayrakları

- Gerçek Meta/TikTok hesaplarıyla canary yapılmadı; provider secret/consent/panel işlemleri R8'e
  aittir.
- TikTok optional comments yalnız gerçek token `comment.list` scope'u içerirse çalışır.
- Expired geçmiş Instagram Stories provider tarafından tekrar verilmiyorsa V2 bunları uydurmaz;
  previous period zaman içinde V2'de biriken durable satırlardan oluşur.
- `STANDALONE_PRODUCT_COMPLETE`: false
- `STANDALONE_RUNTIME_COMPLETE`: false
- `READY_FOR_ACCUMULATE_SSO_HANDOFF`: false
- `SSO_LIVE_VERIFIED`: false
- `TIKTOK_CONNECTION_VERIFIED`: false

R4 kod ve yerel sertifikasyon kapısı tamamlanmıştır. Sonraki plan adımı R5 exact frontend render
parity'dir ve başlanmadan önce kullanıcı onayı alınmalıdır.
