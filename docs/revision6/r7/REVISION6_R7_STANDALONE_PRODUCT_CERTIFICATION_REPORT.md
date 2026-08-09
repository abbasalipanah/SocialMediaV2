# Revision 6 / R7 Standalone Product Sertifikasyon Raporu

Tarih: `2026-08-07`

Durum: `R7_CERTIFIED`

Karar: `STANDALONE_PRODUCT_COMPLETE=true`

Bu karar Social Media V2'nin ürün/kod ve release-candidate olarak tamamlandığını, fakat
production'da dormant kaldığını ifade eder. Staging runtime kurulumu, gerçek provider canary,
Accumulate tarafı SSO değişikliği, canlı trafik, schedule veya owner TikTok consent'i yapılmış
değildir.

## Kapsam ve güvenlik sınırı

R7 yalnız `/home/api/colab_scripts/SocialMediadownstream` içinde uygulanmıştır. Canlı
`SocialMedia`, `Accumulate` ve `performance_marketing` projelerinde kod, config, Git state, DB,
media, build, process, port, service, timer, routing veya secret değişikliği yapılmamıştır.
Canonical sertifikasyonun başlangıç ve bitiş source-write guard kontrolleri geçmiştir.

Kullanıcının `3010` portundaki frontend süreci durdurulmamış, yeniden başlatılmamış ve mevcut
`node_modules` ağacı temiz kurulum amacıyla değiştirilmemiştir. Frontend release testleri ayrı
geçici repository kopyasında ve `3011` portunda çalıştırılmıştır.

## R7 sırasında tamamlanan V2-only işler

- Backend type gate'i gerçek release kapısına alındı ve `129` app source dosyası mypy-clean hale
  getirildi; davranış değiştirmeyen dar type/narrowing düzeltmeleri yapıldı.
- OpenAPI exporter'a generated contract'ı yazmadan doğrulayan deterministic `--check` modu
  eklendi.
- Disposable PostgreSQL, temiz package build/install, temiz frontend install, audit, Playwright
  ve artifact taramasını tek fail-closed turda çalıştıran R7 kalite komutları eklendi.
- Güncel npm advisories nedeniyle güvenli bir ortak `react-router-dom` V7 aralığı kalmadığı için
  dış Router bağımlılığı kaldırıldı. V2'nin kullandığı Browser/Memory routing, Link/NavLink,
  nested Route/Outlet ve URL state davranışı V2-owned dar bir istemci modülüne taşındı. Görünür
  route, kart, metin veya layout sözleşmesi değişmedi.
- React StrictMode altında history state-updater'ın iki kez URL yazması engellendi; browser geri
  navigasyonu Playwright ile doğrulandı.
- Eski DB platform alias normalizasyonu master plandaki tek izinli consume-only
  `infrastructure/persistence/legacy_socialmedia` sınırına taşındı. Alias raw değeri domain,
  API, log veya UI çıktısına çıkmıyor; artifact allowlist'i yalnız bu exact dosyaya açıktır.
- Frontend lock dosyasında Redocly/js-yaml, brace-expansion, nanoid ve postcss güvenlik yamaları
  sabitlendi; clean-install audit sıfır bulguyla kapandı.
- Açık kullanıcı kararıyla yalnız Instagram Stories ana içeriği referans düzene uyarlandı.
  Sidebar/topbar/footer ve diğer platformlar değiştirilmedi; R1 tarihsel oracle'ı korunup karar
  ayrı approved override, component testi ve iki viewport görsel baseline'ıyla kaydedildi.

## Canonical doğrulama sonuçları

`./scripts/quality/revision6_r7_release_check.sh` tek, temiz çıkış kodlu canonical turda
tamamlandı.

| Gate | Sonuç |
|---|---|
| Source-write guard başlangıç / bitiş | pass / pass |
| R1, R3, R4, R5, R6 statik zinciri | pass |
| Disposable PostgreSQL | PostgreSQL 16; üç izole V2 DB |
| V2 migration | `0001` + `0002`; ikinci uygulama idempotent |
| Ruff / Python syntax | pass |
| mypy | `129` source dosyası, sıfır hata |
| Backend testleri | `138 passed`, `0 skipped` |
| Fake Meta/TikTok, differential, recovery, redaction | tam backend suite içinde pass |
| Production-like safe start / rollback smoke | pass; writes/provider/schedule fail-closed |
| OpenAPI + generated TypeScript | deterministic, temiz karşılaştırma |
| Temiz frontend install | `240` package |
| TypeScript | pass |
| Vitest | `23 passed` |
| Production frontend build | pass |
| npm audit | `0 vulnerabilities` |
| Desktop/mobile Playwright + visual baseline | `16 passed`, `4` bilinçli project skip |
| Installed wheel import smoke | pass |
| Release artifact taraması | `16` frontend dosyası, `134` wheel üyesi, pass |

Dört Playwright skip'i eksik ortam veya canlı bağımlılık değildir; aynı spec'lerin yalnız ilgili
desktop/mobile project'inde çalışması için test matrisinde tanımlanmış bilinçli koşullardır.
Production build'deki `500 kB` chunk uyarısı non-blocking performans uyarısıdır; build, test veya
parity hatası değildir.

## Frontend parity sayımı

| Ölçüm | Matched | Unavailable | Blocked |
|---|---:|---:|---:|
| R1 canonical card/section ID | 51 | 0 | 0 |
| Kullanıcı-onaylı Stories görünür başlığı | 7 | 0 | 0 |
| Canonical desktop/mobile visual baseline | 6 | 0 | 0 |
| Stories override desktop/mobile visual baseline | 2 | 0 | 0 |

## Package ve artifact kanıtı

Makine-okunur manifest:
`docs/revision6/r7/r7_release_artifact_manifest.json`

- Wheel SHA-256:
  `f4aa3445b1e469a2350514d6d9364e472721e0b3a13d603a2c5a32d03139d148`
- Wheel boyutu: `178783` byte
- Source filesystem path bulgusu: `0`
- Yasak runtime/source API bulgusu: `0`
- Secret bulgusu: `0`
- Yasak platform/product vocabulary bulgusu: `0`
- Wheel içinde `tests/`, `docs/` veya `frontend/` runtime-dışı ağaç: `0`

Sertifikasyon wheel'i ve frontend dist'i disposable çalışma alanında üretildi ve tarandı;
repository'deki eski ignored wheel kanıt olarak kullanılmadı. Önceki stale ignored wheel
silinmeden `/tmp/social_media_v2-0.1.0-pre-r7-stale.whl` konumuna taşındı.

## DB ve veri taşıma durumu

V2 ayrı PostgreSQL DB/role/schema sözleşmesine sahiptir ve migration/full integration davranışı
disposable DB üzerinde doğrulanmıştır. V1 production DB'ye bağlantı kurulmamış, migration veya
write yapılmamış ve production verisi henüz V2 DB'ye taşınmamıştır.

Tarihsel veri taşıma; yetkili ekibin sağlayacağı salt-okunur export/offline snapshot, ayrı V2 DB
import rehearsal'i, satır/sayım/hash/parity doğrulaması ve ayrıca açık kullanıcı/Operations onayı
gerektirir. Bu iş R7 kod sertifikasyonunun parçası değildir ve kaynak DB'yi hiçbir zaman
değiştirmez.

## Açık dış işler ve durum bayrakları

- V2-owned staging DB/user/TLS/secret/media/runtime henüz oluşturulmadı veya deploy edilmedi.
- Provider panellerinde exact callback/rotated secret doğrulanmadı; Meta/TikTok sandbox/canary
  ve TikTok owner consent'i yapılmadı.
- Accumulate handoff taslağı gönderilmedi; Accumulate kodu/config/routing'i değiştirilmedi.
- Worker schedule ve production traffic açılmadı.
- `STANDALONE_PRODUCT_COMPLETE`: **true**
- `STANDALONE_RUNTIME_COMPLETE`: **false**
- `READY_FOR_ACCUMULATE_SSO_HANDOFF`: **false**
- `SSO_LIVE_VERIFIED`: **false**
- `TIKTOK_CONNECTION_VERIFIED`: **false**

Sonraki normatif faz R8'dir. R8 staging altyapısı, secret/provider paneli ve dış ekip değişikliği
gerektirdiğinden yeni ve açık operasyon yetkisi alınmadan başlatılmaz.
