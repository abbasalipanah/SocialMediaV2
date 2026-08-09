# Revision 6 — R1 Canonical Frontend ve Davranış Raporu

**Durum:** PASS

**Tarih:** 2026-08-07

**Kaynak:** `/home/api/colab_scripts/SocialMedia` — salt okunur

**Çıktı:** Yalnız `/home/api/colab_scripts/SocialMediadownstream`

## 1. Sonuç

Güncel SocialMedia çalışma ağacının production'da erişilebilir frontend render zinciri
tek canonical oracle olarak donduruldu. Route, navigation, platform, tab, section,
KPI, kart, chart, tablo, legend, kolon, görünür metin, responsive sıra ve state
davranışları makine-okunur envantere kaydedildi.

Kaynak projede test, build, format, migration veya herhangi bir yazma işlemi
çalıştırılmadı. Başlangıç ve kapanış source guard kontrolleri aynı Revision 6
baseline'ıyla geçti.

## 2. Teslimatlar

| Teslimat | Dosya | Sonuç |
|---|---|---|
| Makine-okunur frontend envanteri | `canonical_frontend_inventory.json` | PASS |
| Ortak source/V2 test oracle fixture sözleşmesi | `canonical_dashboard_fixture.json` | PASS |
| Envanter ve source-hash validator | `scripts/quality/revision6_r1_inventory.py` | PASS |
| Source component → V2 component → API alanı mapping'i | Envanter içindeki `component_api_mapping` | Tamamlandı |
| Onaylı tek fark listesi | Envanter içindeki `approved_visible_differences` | Donduruldu |

Dosya imzaları:

- Envanter SHA-256:
  `f3923eb690d345bb267557c1e921874b2538edb307440ff3662ebd60bd138620`
- Fixture SHA-256:
  `97876225c1ad8415640ed5760bd698fe3202e40c811659b39c38c60e1cb26ed5`

Envanter 21 canonical source dosyasının ayrı SHA-256 imzasını, 7 route-resolution
kuralını, 3 platformu, 51 benzersiz kart/öğe tanımını ve 8 fixture senaryosunu
içerir.

## 3. Canonical route ve shell kararı

Production'da authenticated ana route davranışı şöyledir:

| Route/durum | Canonical render |
|---|---|
| `/facebook` | SocialAppShell + Facebook Dashboard |
| `/instagram` | SocialAppShell + Instagram Dashboard |
| `/tiktok` | SocialAppShell + TikTok Dashboard |
| `/settings/audit` + local super role | Operations audit |
| `/`, `/settings`, bilinmeyen authenticated path | SettingsPage |
| Token yok | EntryGatePage |
| `/auth/sso/consume`, `/sso/consume` | SsoConsumePage |
| `/_dev/tiktok-main` | Yalnız development preview; production yüzeyi değil |

Kaynakta production `/overview` sayfası veya görünür `Overview` navigation satırı
yoktur. Dashboard shell navigation sırası `Home → Analytics → Social Media →
Facebook → Instagram → conditional TikTok → conditional Settings` şeklindedir.
Demo dışındayken Settings ayrıca footer'da ikinci kez görünür. SettingsPage ise
SocialAppShell içinde render edilmez.

## 4. Dondurulan tab ve section matrisi

| Platform | Tab'ler | Cover içeriği |
|---|---|---|
| Facebook | Cover, Page, Content, Audience | Page/Account + Content + Facebook Audience |
| Instagram | Cover, Page, Content, Stories, Audience | Page/Account + Content + Instagram Audience; Stories dahil değil |
| TikTok | Cover, Account, Content, Audience | Account + Content + TikTok Audience |

Standalone dashboard tab'leri URL'deki `?tab=` ile çift yönlü senkronize olur;
Cover seçimi query'yi kaldırır ve browser `popstate` davranışı korunur.

Ortak account section sırası:

1. Altı KPI
2. Followers Trend + New Followers Trend
3. Performance Trends
4. Page/Video View Type + Views Source Trend
5. Reach Distribution + Reach Source Trend

Ortak content section sırası:

1. Altı KPI
2. Content Type + Views & Reach Trend
3. Interaction Trend + Engagement Split
4. Content Type Reach + Comment Sentiment + Top Hashtags
5. All Performing Content tablosu

Instagram Stories sırası:

1. Altı Story KPI
2. Story Performance Trends + Last Story
3. Story Navigation Split + Story Actions + Story Sliders
4. Stories tablosu

Platform audience sıraları ve tekrar eden Followers/New Followers kartlarının her
biri ayrı canonical ID ile envantere yazılmıştır. Aynı başlığı taşıyan iki kart
birleştirilemez veya tek karta indirgenemez.

## 5. Kritik görünür kararlar

- `FacebookAudienceSection.tsx` kaynak çalışma ağacında untracked durumdadır ancak
  hiçbir reachable component tarafından import edilmez. İçindeki `Provider
  unavailable` Age & Gender kartı ve Facebook world map görünür canonical matrise
  dahil değildir.
- Instagram Stories yalnız Stories tab'inde render edilir; Cover'a eklenmez.
- TikTok navigation ve Home hedefi backend `dashboard_enabled` capability'sine
  bağlıdır; capability fetch başarısızsa TikTok gizlenir ve Home Facebook'a gider.
- TikTok connect kontrolü backend `can_connect` ile mevcut local role kontrolünün
  ikisini de gerektirir.
- Audience tab'leri capability ile gizlenmez. `audience_capabilities` şu an kart
  seçmek için kullanılmaz.
- Paid legend/series yalnız `source_breakdown.paid_available=true` iken görünür.
- Comment Sentiment daima açık bir unavailable panelidir; veri üretilmez veya
  tahmin edilmez.
- Eksik KPI kartı placeholder'a dönüşmez; grid'den tamamen çıkar.
- Stories contract'ı bulunmayan Instagram Stories tab'i kaynakta explicit
  unavailable paneli yerine boş panel üretir. Bu davranış da oracle'a kaydedildi;
  daha dürüst bir state ancak ayrıca onaylanmış görünür değişiklikle yapılabilir.

## 6. Desktop ve mobile yerleşim

| Aralık | Canonical davranış |
|---|---|
| `>=1280px` | KPI 6 kolon; iki-kolon 1:1; source 1:2; content 2:1; üçlü kart 3 kolon |
| `821–1279px` | KPI 3 kolon; source/content/üçlü grid tek kolon; temel iki-kolon 1:1 |
| `561–820px` | KPI 2 kolon; bütün çoklu kart grid'leri tek kolon; header dikey |
| `<=560px` | KPI yine 2 kolon; tabs full width; SSO badge/status/live dot gizli |
| `<=1050px` | 236px fixed sidebar off-canvas drawer olur |
| Settings `<=900px` | Toolbar tek kolon; hero/drawer actions dikey; tablo yatay scroll |

Dashboard header'ın mobile kontrol sırası CSS order nedeniyle `date/download →
conditional TikTok connect → tabs` olur. Bu sıra DOM sırasından farklıdır ve exact
parity kapsamındadır.

## 7. State ve boş veri sözleşmesi

Envanter aşağıdaki state'leri ayrı ayrı dondurur:

- initial skeleton;
- stale content'i koruyan background refresh;
- initial error ve stale-data error;
- platform zero state ve `Open Settings` aksiyonu;
- partial KPI omission;
- trend/distribution/content/audience empty state'leri;
- Stories contract'ı eksik durumu;
- `limited_non_business` TikTok uyarısı;
- comment-sentiment unavailable durumu;
- medya candidate/fallback zinciri.

Dashboard 60 saniyede bir yalnız document görünürken refresh edilir. Tarih seçenekleri
tam olarak `Last 7 Days`, `Last 30 Days`, `Last 90 Days`, `Last 365 Days` biçimindedir.

## 8. Canonical fixture

Fixture tek bir base `PlatformDashboardResponse` ve atomik array replacement kullanan
deterministic deep-merge case'lerinden oluşur:

1. `facebook_full`
2. `instagram_full_with_stories`
3. `tiktok_full`
4. `zero_data`
5. `organic_only`
6. `limited_non_business_tiktok`
7. `partial_metrics`
8. `instagram_missing_stories_contract`

Aynı materialized case iki tüketiciye ayrılmıştır:

- source adapter oracle;
- V2 render testi.

Kaynak frontend build edilmez. R2/R5'te V2 test adapter'ı aynı fixture'ı kullanacak;
ayrı veya elle farklılaştırılmış bir V2 fixture kabul edilmeyecektir.

## 9. V2 mapping sonucu ve sonraki faz girdileri

R1 bir WIP doğrulama fazı değildir; aşağıdaki maddeler R2/R3/R5'e girdi olarak
kaydedilmiştir:

- V2 route/sidebar'da canonical source dışında görünen Overview, Integrations,
  Support, Back to Accumulate ve Sign out yüzeyleri vardır.
- V2 range seçeneklerinde canonical `Last 365 Days` bulunmaz ve mevcut etiketler
  canonical metinlerle aynı değildir.
- V2 tab state'i canonical `?tab=` deep-link/popstate davranışını henüz taşımaz.
- Mevcut V2 dashboard response contract'ı structured Stories, `source_breakdown`,
  `audience_capabilities`, source content views/reach/media candidate alanları,
  `content_summary`, `top_hashtags` ve source community/story semantiğinin tamamını
  exact karşılamaz.
- Mevcut V2 Pulse dashboardlarda canonical matriste bulunmayan Content Winners ve
  comment queue türü görünür öğeler vardır; bunlar kaynak parity'si sayılmaz.
- Unimported `FacebookAudienceSection.tsx` içeriğini V2'ye taşımak yeni görünür kart
  eklemek olur ve kullanıcı ayrıca istemedikçe yasaktır.

Bu maddelerin PASS/FAIL dosya bazlı sınıflandırması R2'de yapılacaktır.

## 10. Onaylı tek farklar

Görünür parity dışında kalmasına izin verilen farklar yalnız şunlardır:

1. SSO consume/login güvenlik akışı
2. V2 Brand authority ve zorunlu Brand/account selector'ları
3. Same-origin API transport
4. Normal navigation'da görünmeyen owner activation yüzeyi
5. Görünür kart/navigation matrisini değiştirmeyen accessibility altyapısı

Bunların dışında kart, tab, route, navigation, metin, sıra, tablo kolonu, legend
veya state değişikliği R1 freeze'i ihlal eder.

### 10.1 R1 sonrası kullanıcı onaylı Instagram Stories kararı

2026-08-07 tarihinde kullanıcı, R1/R7 tamamlandıktan sonra yalnız Instagram Stories
ana içeriğinin sağlanan referans görsele göre yeniden düzenlenmesini açıkça onayladı.
Bu karar R1'in tarihsel source oracle'ını değiştirmez; ayrı ve makine-okunur bir
visible-override olarak `../overrides/instagram_stories_main_2026-08-07.json`
dosyasında tutulur. Sidebar, topbar, footer, diğer platformlar, backend ve veri
sözleşmesi bu kararın dışındadır. R5/R7 yeniden sertifikasyonu bu override'ın iki
viewport görsel kanıtını ayrıca doğrulamak zorundadır.

## 11. Doğrulamalar

| Kontrol | Sonuç |
|---|---|
| Revision 6 source write guard — başlangıç | PASS |
| 21 canonical source dosya hash'i | PASS |
| Route/platform/tab/card referential integrity | PASS |
| Fixture schema/case/consumer integrity | PASS |
| FacebookAudienceSection reachable-import negative check | PASS |
| Kaynak frontend test/build | Çalıştırılmadı |
| Revision 6 source write guard — kapanış | PASS |

## 12. R1 çıkış kararı

Her görünür öğenin tek canonical karşılığı belirlenmiştir. “Benzer”, “yaklaşık” veya
unimported dosyadan türetilmiş kart tanımı kalmamıştır. Envanter kullanıcı ayrıca kart
matrisi değişikliği istemedikçe dondurulmuştur. R2 bu freeze'e karşı mevcut V2 WIP'yi
dosya bazında doğrulayacaktır.
