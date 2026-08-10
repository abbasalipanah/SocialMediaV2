# Revision 6 · R24 — Final uygulama ve veri sertifikasyonu

Tarih: `2026-08-10`

Durum: `COMPLETE — V2 loopback certified, public cutover blocked`

Kod commitleri: `fdff9e8`, `4053506`

Aktif release: `/opt/social-media-v2/releases/20260810T140721Z-r24audit`

## Sonuç

Overview, Facebook, Instagram, Instagram Stories ve TikTok yüzeylerinin gerçek Pine Beach Belek
V2 verisi, tarih/scope davranışı, XLSX üretimi, yetki matrisi, Settings/Integrations, AI Summary,
SSO, güvenlik ve operasyon kapıları birlikte sertifikalandı. Açık kritik ve yüksek bulgu
sayısı sıfırdır.

Bu tur yalnız `/home/api/colab_scripts/SocialMediadownstream` içinde ve V2'nin `127.0.0.1:3026`
ile `127.0.0.1:8026` runtime'ında yürütüldü. SocialMedia, Accumulate ve Performance Marketing
source projelerine yazılmadı; DNS, TLS, shared Nginx, public routing ve provider activation
değiştirilmedi. V2 collection service inactive, timer inactive/disabled kaldı.

## Gerçek veri matrisi

Sabit denetim anı `2026-08-10T12:00:00Z`, rapor bitiş tarihi `2026-08-09` olarak kullanıldı.
Pine Beach Belek `brand_id=18`; Facebook `1411`, Instagram `1412`, TikTok `2862` hesaplarıyla
çalışıldı.

| Aralık | Facebook | Instagram | TikTok | İçerik özeti |
|---|---:|---:|---:|---|
| Son 7 gün | 7 gün | 7 gün | 7 gün | FB 2, IG 2, IG Story 0, TikTok 0 |
| Son 30 gün | 30 gün | 30 gün | 30 gün | FB 14, IG 29 = 13 normal + 16 Story, TikTok 3 |
| Son 90 gün | 90 gün | 90 gün | 90 gün | FB 37, IG 50, IG Story 56, TikTok 3 |
| Son 365 gün | 259 gün | 260 gün | 100 gün | FB 50, IG 50, IG Story 116, TikTok 25 |

365 günlük aralıkta görülen gün sayısı provider snapshot'ının gerçek tarihsel kapsamıdır; eksik
günler demo değerle doldurulmadı. Son 7 günde TikTok içeriğinin ve Instagram Story'nin olmaması
da gerçek boş durum olarak gösterilir. Provider'ın vermediği Comment Sentiment sıfır veya demo
değer yerine açıkça unavailable kalır.

Facebook'ta 16, Instagram ve TikTok'ta 17'şer typed metric doğrulandı. Birincil KPI'lar dolu;
Follows, Unfollows ve Net üç ayrı seri olarak mevcut. TikTok Son 30 Gün Performance Trends
Views/Reach serileri tam 30 noktadır. Story completion rate `0–100` yüzde biriminde taşınır;
ratio olarak ikinci kez çarpılmaz.

Brand scope testi exact Pine hesabını, child scope'u, account filtresini ve rollup'ı kapsadı.
`brand_id=19` rollup'ı `[19, 28, 29, 30]` Brand setine ve `[2386, 2388, 2800]` hesap setine
çözüldü; exact parent hesabı boş kaldı. Scope dışı istekler fail-closed sonuçlandı.

Makine-okunur kanıt:
`docs/revision6/r24/revision6_r24_data_xlsx_certification.json`.

## XLSX sertifikasyonu

Overview ve her platform/tab için toplam 14 workbook bellek içinde üretildi. 88 sheet ve 45
chart; `Report Info`, Pine Beach kimliği, `11 Jul 2026 – 09 Aug 2026` dönemi, sheet setleri,
ham günlük veriler, content/story satırları ve toplamları kaynak dashboard projection'ıyla
karşılaştırıldı.

Her workbook'ta yalnız canonical Accumulate logosunun PNG türevi bulundu. Logo SHA-256 değeri
`46e27509774512dccdc506ccd74ff80c9cd38d4d5096ebe31034480b54e801a7` olarak eşleşti. Formül,
macro, external link, `#REF!` ve `#VALUE!` yoktur. Job tamamlandıktan/indirildikten sonra kalıcı
XLSX artifact'i bırakılmadı.

## Yetki ve oturum matrisi

| Rol | Settings | Integrations | Yeni AI Summary |
|---|---:|---:|---:|
| Super Admin | Evet | Evet | Hayır |
| Agency Admin | Evet | Evet | Hayır |
| Viewer | Hayır | Hayır | Hayır |
| Viewer + app role Operator | Hayır | Evet | Evet |

Navigation görünürlüğü, doğrudan route ve backend endpoint izinleri birlikte test edildi.
Operator için mevcut provider/key yapılandırması ve önceki Pine özeti okundu; yeni üretim limiti
7 günlük pencerede 1 olarak doğrulandı. Sertifikasyon gereksiz dış AI tüketimi yaratmadı; gerçek
provider çağrısı yerine generation yolu deterministik provider testleriyle, canlı runtime ise
history/config/limit üzerinden doğrulandı.

İmzalı SSO consume, geçersiz/expired token reddi, session okuma ve logout sonrası `auth/me=401`
akışları geçti. Runtime rol ve oturum kanıtı:
`docs/revision6/r24/revision6_r24_runtime_certification.json`.

## Bulunan ve kapatılan bulgular

| Önem | Bulgu | Düzeltme | Durum |
|---|---|---|---|
| Yüksek | Instagram Content odak yüzeyi Story satırlarını da içeriyordu | Content API, previous-period query ve XLSX projection'ına typed `story` exclusion eklendi; Stories yalnız Story olarak kilitlendi | Kapalı |
| Yüksek | `cryptography 46.0.7` dependency audit'te dört advisory üretiyordu | Runtime/lock/requirement `cryptography 50.0.0` sürümüne taşındı; fresh-env audit sıfır vulnerability verdi | Kapalı |
| Orta | Strict mypy taramasında 14 type hatası vardı | Legacy TikTok, XLSX platform/iteration ve xlsxwriter typing düzeltildi | Kapalı |
| Düşük | Dev lock yanked `build 1.5.1` çözüyordu | Lock `build 1.5.0` ile yeniden üretildi | Kapalı |
| Düşük | Runtime role testi navigation tamamlanmadan DOM sayıyordu | Home/Settings/Integrations readiness wait eklendi | Kapalı |

Kalan tek teknik uyarı Vite'ın minified `PlatformPage` chunk'ı için verdiği `500 kB` performans
uyarısıdır. Build'i veya runtime doğruluğunu bozmaz; kritik/yüksek bulgu değildir ve ayrı bir
code-splitting iyileştirmesi olarak izlenebilir.

## Test ve kalite kapıları

| Kapı | Sonuç |
|---|---|
| Backend default suite | `152 passed`, `18` yalnız harici TEST_POSTGRES_URL/parity DB olmadığı için skipped |
| Disposable PostgreSQL faz suite | tekrar eden tam fazlarda `169 passed / 1` ayrı parity DB skip; ilgili fazlarda `170 passed` |
| Collector parity | `39 passed` |
| Dashboard/operations API | `27 passed` |
| Backend strict mypy | `140 source file`, 0 error |
| Ruff | pass |
| OpenAPI generated contract/check | pass |
| Wheel build + pip check | pass |
| Frontend Vitest | `35 passed` |
| Frontend typecheck + production build | pass |
| Desktop/mobile Playwright | `17 passed`, `5` bilinçli project-applicability skip |
| R24 signed runtime browser matrisi | pass; console/request/API 5xx = 0 |
| npm audit | 0 vulnerability |
| Fresh-env pip-audit | 0 known vulnerability |
| Secret/vocabulary/import/source guards | pass |

`local_demo.py` yalnız açık test gate'i altında kalır; production import zincirinde değildir.
Dashboard runtime'ında demo fallback, açıklanamayan boş kart, yanlış yüzde/`pp`, unavailable→0
dönüşümü veya frontend/backend typed contract sapması bulunmadı.

## Restart ve rollback provası

1. Aktif R24 API/web servisleri kontrollü restart edildi ve probe'lar geçti.
2. Backend/frontend symlink'leri doğrulanmış R23 release'i
   `/opt/social-media-v2/releases/20260810T132946Z-r23content` üzerine rollback edildi.
3. API/web probe'ları geçtikten sonra R24 release'ine atomik forward yapıldı.
4. Son durumda API/web active; `/api/health` 200, operations readiness `ready/staging`, web 200.
5. API ve web yalnız loopback'te dinliyor; collection service/timer kapalıdır.

## Çıkış durumu

- `OPEN_CRITICAL_FINDINGS=0`
- `OPEN_HIGH_FINDINGS=0`
- `STANDALONE_PRODUCT_COMPLETE=true`
- `STANDALONE_RUNTIME_COMPLETE=true`
- `READY_FOR_ACCUMULATE_SSO_HANDOFF=false` — kullanıcı public geçiş izni vermedi
- `SSO_LIVE_VERIFIED=false` — yalnız V2 loopback signed SSO doğrulandı
- `TIKTOK_CONNECTION_VERIFIED=false` — snapshot verisi doğrulandı, canlı collection activation yapılmadı

R24 ürün sertifikasyonu tamamlandı. Bu sonuç DNS/TLS veya canlı Accumulate bağlantısına geçiş
izni değildir; onlar ayrı kullanıcı kararı ve ayrı kesintisiz geçiş planı gerektirir.
