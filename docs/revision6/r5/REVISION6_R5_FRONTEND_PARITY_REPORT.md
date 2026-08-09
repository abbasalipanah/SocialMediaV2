# Revision 6 / R5 Exact Frontend Render Parity Raporu

Tarih: 2026-08-07

Durum: `R5_LOCAL_CERTIFIED`

R5 yalnız `/home/api/colab_scripts/SocialMediadownstream` içinde uygulanmıştır. Canlı
`SocialMedia`, `Accumulate` ve `performance_marketing` projelerinde kod, yapılandırma,
veritabanı, media, process, port, servis, routing, build veya test değişikliği yapılmamıştır.
Başlangıç ve bitiş source-write guard kontrolleri geçmiştir.

## Sonuç

- Canonical route ve navigation yapısı Home, Analytics, Social Media, Facebook, Instagram,
  capability-gated TikTok ve Settings olarak uygulanmıştır. `/overview` ve `/integrations`
  görünür ürün rotaları kaldırılmıştır.
- `/sso/consume` canonical endpoint'i korunmuş, `/auth/sso/consume` uyumluluk alias'ı aynı V2
  consume ekranına bağlanmıştır. Authenticated kök ve bilinmeyen rotalar canonical Settings
  yüzeyine gider.
- Facebook, Instagram ve TikTok için Cover, Content ve Audience tab sırası; kart başlıkları,
  KPI'lar, grafikler, tablolar, kolonlar, legend'lar ve empty/unavailable metinleri R1 fixture'ına
  göre eşleştirilmiştir.
- Tarih aralığı `Last 7 Days`, `Last 30 Days`, `Last 90 Days`, `Last 365 Days` seçeneklerini
  destekler. Tab seçimi URL `?tab=` durumuyla ve browser history ile senkron çalışır.
- Settings canonical `Social media setup` tablosuna dönüştürülmüştür. Accumulate authority'sini
  ihlal edecek local Brand mutation backend capability'si olmadığı için `Add brand` kontrollü
  olarak disabled kalır; mevcut V2 SSO/provider-safe setup drawer korunur.
- Dashboard istekleri aynı-origin V2 API'yi kullanır; görünür sayfada stale-data sıçramasını
  azaltmak için önceki veri tutulur ve yalnız sayfa görünürken 60 saniyelik yenileme yapılır.
- Dashboard JSON export'u `<platform>-dashboard-<end_on>.json` adıyla çalışır.
- 2026-08-07 tarihli açık kullanıcı kararıyla Instagram Stories ana içeriği; Latest Story,
  Story Live Status, Evolution, Story Health, Behaviour ve History düzenine alınmıştır. R1
  tarihsel oracle'ı değiştirilmemiş, karar ayrı approved override olarak kaydedilmiştir.

## Canonical parity sayımları

R1 envanteri 51 canonical card/section ID'si içerir. Bunların içinde ayrı `<h3>` üretmeyen KPI
grid öğeleri de bulunduğundan görünür benzersiz başlık sayısı ayrıca ölçülmüştür.

| Ölçüm | Matched | Unavailable | Blocked |
|---|---:|---:|---:|
| Canonical card/section ID | 51 | 0 | 0 |
| Benzersiz görünür kart başlığı (Stories override dahil) | 36 | 0 | 0 |
| Canonical platform/tab render dizisi | 9 | 0 | 0 |
| Desktop/mobile görsel baseline | 8 | 0 | 0 |

Provider'ın gerçekten veri sunmadığı durumlar kart eksikliği olarak saklanmamıştır. İlgili kart
canonical sırada render edilir ve typed `unavailable`/empty açıklamasını gösterir. Bu nedenle
parity tablosundaki `Unavailable=0`, canonical render karşılığı olmayan öğe sayısını ifade eder;
provider metric availability iddiası değildir.

## Değişen yalnız V2 dosyaları

R5 değişiklikleri aşağıdaki V2 alanlarıyla sınırlıdır:

- Route ve shell: `frontend/src/routes/AppRoutes.tsx`, `LoginPage.tsx`,
  `frontend/src/layout/Sidebar.tsx`.
- Dashboard davranışı: `frontend/src/features/dashboard/PlatformPage.tsx`, `catalog.ts`,
  `useDashboard.ts`, `AudienceDemographicsCard.tsx`.
- Platform render'ları: Facebook, Instagram ve TikTok feature `index.tsx` ve
  `*PulseDashboard.tsx` dosyaları; ayrıca `InstagramStoriesWorkspace.tsx`.
- Settings ve stil: `frontend/src/features/settings/index.tsx`, `frontend/src/styles.css`.
- Typed frontend contract: `frontend/src/api/contracts.ts`, `openapi.generated.ts`.
- Reporting aralığı: `backend/app/application/queries/reporting_range.py` ve
  `backend/tests/test_reporting_range.py`.
- Unit/component testleri: `frontend/src/test/AppRoutes.test.tsx`,
  `Phase8Products.test.tsx`, `Revision6CanonicalFixture.test.tsx`.
- Browser ve visual testleri: `frontend/e2e/r5-fixtures.ts`, `shell.spec.ts`, `product.spec.ts`,
  `revision6-r5.spec.ts`, `instagram-stories.spec.ts`; altı canonical ve iki kullanıcı-onaylı
  Stories Chromium/Linux screenshot baseline'ı.
- Test altyapısı: `frontend/playwright.config.ts`, `frontend/package.json`,
  `frontend/package-lock.json`.
- Kalite kapısı: `scripts/quality/revision6_r5_frontend.py` ve
  `scripts/quality/revision6_r5_frontend_check.sh`.

Repository'deki diğer dirty dosyalar R0'da dondurulan ve R2-R4 boyunca doğrulanan önceki V2 WIP
çalışmasının parçasıdır; R5 raporu bunları yeni R5 değişikliği olarak yeniden sınıflandırmaz.

## Doğrulama kanıtları

`./scripts/quality/revision6_r5_frontend_check.sh` temiz çıkış koduyla tamamlanmıştır:

- Source-write guard başlangıç: pass.
- R1 inventory doğrulaması: pass.
- R5 statik gate: pass; 36 benzersiz kart başlığı, 6 canonical ve 2 kullanıcı-onaylı Stories
  görsel baseline bulundu.
- Python Ruff: pass.
- Backend hedef testleri: `11 passed`.
- Frontend Vitest: `23 passed`.
- Frontend typecheck ve production build: pass.
- Playwright tam R5 seti: 20 scheduled; `16 passed`, `4 skipped`.
- Source-write guard bitiş: pass.

Dört Playwright skip'i hata veya eksik parity değildir; yalnız ilgili browser/project scope'una
ait olmayan test kombinasyonları bilinçli olarak skip edilmiştir. Fonksiyonel E2E'nin hedef koşusu
`8 passed, 4 skipped`, görsel E2E koşusu `8 passed` sonucunu vermiştir. Build'deki 500 kB chunk
uyarısı non-blocking'dir; typecheck/build hatası veya görünür parity farkı değildir.

Playwright test-only sunucusu `3011` portunu kullanır. Kullanıcının `3010` üzerindeki development
Vite process'i durdurulmamış, yeniden başlatılmamış veya değiştirilmemiştir.

## Onaylı görünmez V2 uyarlamaları

- V2 Brand/account seçicileri ve SSO profil bağlamı topbar'da korunur.
- Transport yalnız same-origin typed V2 API üzerinden çalışır.
- Accumulate Brand authority'sini ihlal edecek local create mutation'ı olmadığı için Add brand
  capability-gated/disabled durumdadır.
- TikTok owner activation normal navigation içinde açılmaz; master planın ayrı activation
  kapısında fail-closed kalır.
- Browser test portu yalnız disposable test runtime'ı için `3011` olarak ayrılmıştır.

Bu uyarlamalar canonical kart adı, sırası, ölçüsü, kopyası veya tab render sözleşmesini
değiştirmez.

## Açık dış işler ve status bayrakları

- R5 için açık frontend parity blocker'ı yoktur.
- Gerçek V2-owned staging DB/runtime kurulumu, provider secret/callback doğrulaması, Meta/TikTok
  canary, canlı Accumulate SSO ve worker schedule aktivasyonu yapılmamıştır; R6-R8 kapılarına
  aittir.
- V1 veritabanındaki tarihsel veri R5'te kopyalanmamıştır. V2 kendi DB'sini kullanacaktır; legacy
  veri aktarımı canlı kaynağa yazmadan, ayrıca tasarlanmış export/import rehearsal ve açık onay
  gerektirir.
- `STANDALONE_PRODUCT_COMPLETE`: false
- `STANDALONE_RUNTIME_COMPLETE`: false
- `READY_FOR_ACCUMULATE_SSO_HANDOFF`: false
- `SSO_LIVE_VERIFIED`: false
- `TIKTOK_CONNECTION_VERIFIED`: false

R5 exact frontend render parity ve yerel sertifikasyon kapısı tamamlanmıştır. Sonraki plan adımı
R6 standalone runtime ve SSO-only temizliktir. R6 içinde yalnız V2 kodu ve disposable V2
yüzeyleri üzerinde çalışılabilir; staging/production DB, servis, secret, DNS, Nginx veya dış ekip
işlemi gerektiğinde ayrıca durulup kullanıcı yetkisi istenir.
