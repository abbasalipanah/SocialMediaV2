# Faz 8 — Social Sayfalar ve Settings Kapanış Raporu

Tarih: `2026-07-14`

Düzeltme tarihi: `2026-07-17`

Durum: **2026-07-14 KAPANIŞ KARARI GEÇERSİZ KILINDI — ürün parity düzeltmesi uygulandı**

## 2026-07-17 düzeltme notu

İlk rapordaki “ürün parity tamamlandı” sonucu doğru değildi. Overview, Accumulate'ın aktif
`components/SocialMediaOverview.tsx` → `components/accumulate/SocialMediaDashboard.tsx` render
zincirini taşımak yerine generic dashboard kartlarından oluşuyordu. Bölüm sırası, bilgi
yoğunluğu, tablo ve platform breakdown yapısı kaynak ürünle farklıydı.

2026-07-17 çalışma ağacı düzeltmesinde:

- Overview, aktif Accumulate ekranındaki sırayla `Social Media Overview`, altılı KPI bandı,
  Audience Growth, Cross-Channel, Content Type, AI Insights, Action Breakdown, Top Performing
  Posts ve Platform Breakdown olarak yeniden kuruldu;
- Facebook ekranı aktif Accumulate `PlatformDashboard` → `FacebookPulseDashboard` zincirindeki
  Page, Content ve Audience kart/grafik/tablo sırasına taşındı; Facebook Cover sekmesi kaynak
  üründeki gibi bu üç bölümün tamamını tek akışta gösterir;
- Instagram ekranı aynı aktif pulse zincirindeki Page, Content, Stories ve Instagram'a özgü
  Audience düzenine taşındı; Instagram Cover kaynak üründeki gibi dört bölümün tamamını tek
  akışta gösterir;
- Accumulate'ın resmi logo, light/dark branding ve favicon asset'leri V2 içine kopyalandı;
  kaynak KPI'daki üç follower avatarı local asset olarak Overview, Facebook ve Instagram ilk
  KPI kartlarında kullanıldı;
- TikTok için eski üründe karşılığı bulunmadığından Facebook/Instagram pulse tasarım sistemiyle
  yeni Overview, Videos ve capability-gated Audience yüzeyleri oluşturuldu. Kartlarda yalnız
  TikTok sözleşmesindeki Followers, Video Views/Likes/Comments/Shares, Engagements ve Engagement
  Rate kullanıldı; video-level views ve saatlik audience verisi desteklenmiyorsa açık `—`/empty
  state gösterildi;
- Settings ekranı doğrudan aktif Performance Marketing
  `frontend/src/features/settings/SettingsWorkspace.tsx` yapısına hizalandı: aynı başlık ve üst
  aksiyon bandı, altılı readiness özeti ve tek workspace kartı içindeki sekme/arama/çift filtre
  düzeni Social Media DTO'larına uyarlandı;
- DTO'da olmayan impressions, cover, saves veya engagement-rate değerleri uydurulmadı; destek
  yoksa `—` ya da açık unavailable state kullanıldı;
- Overview bilgi mimarisi ve Facebook birleşik Cover davranışı için regression testleri eklendi;
  Instagram birleşik Cover ve TikTok pulse davranışları da regression testine alındı; frontend
  suite `17 passed`, strict
  TypeScript ve Vite production build yeşil;
- 1440×1000 Overview/Facebook/Instagram/TikTok, tam sayfa görünümler ve 390×844 mobile gerçek browser
  smoke'ları çalıştırıldı.

Bu güncel düzeltme local ürün adayını ifade eder; production aktivasyonu ve global release gate'i
ifade etmez.

## Sonuç

Overview, Facebook, Instagram, TikTok ve Settings yüzeyleri gerçek Faz 6 DTO'larına bağlandı.
Frontend yalnız backend'in döndürdüğü destekli metrikleri gösterir; `null` veya `unavailable`
değerler sıfıra çevrilmez. Parent rollup frontend'de birleştirilmez ve tek backend cevabı kullanılır.

## Ürün parity kontrolü

- Overview: KPI bandı, follower/growth trendleri, platform health, content intelligence,
  community, recent/top content, stored AI Insights ve PNG export tamamlandı.
- Facebook: Page, Content ve Audience yüzeyleri aktif `FacebookPulseDashboard` bölüm sırasıyla
  tamamlandı; Cover bu üç yüzeyi birlikte render eder.
- Instagram: Page, Content, Stories ve Instagram'a özgü Audience yüzeyleri aktif pulse bölüm
  sırasıyla tamamlandı; Cover bu dört yüzeyi birlikte render eder ve Stories ayrı route değildir.
- TikTok: Overview, Videos ve capability-gated Audience içinde altılı KPI bandı,
  follower/video trends, video engagement mix, video format/engagement
  kartları, dürüst video performance tablosu ve objective winners Facebook/Instagram ile aynı
  pulse grid dilinde tamamlandı.
- Reporting DTO'sunda bulunmayan post views/reach, frequency, sentiment, hashtag ve saatlik
  audience breakdown değerleri için dürüst `—`/unavailable state gösterilir; sahte veri üretilmez.
- Reporting catalog'da ayrı impressions metriği bulunmadığı için türetilmiş veya reklam metriği
  gösterilmez; mevcut reach/views sözleşmesi korunur.
- Ortak loading, error, empty, partial, freshness ve retry durumları tamamlandı.

## Settings parity kontrolü

- Performance Marketing ile aynı `Brand Setup and Account Mapping` başlığı, `Linked brands`,
  `Manual sync`, `Refresh Platform` üst aksiyonları ve altılı readiness özeti tamamlandı.
- Brands, Platform Accounts, Mappings ve Sync & Backfill sekmeleri tek table-first workspace
  kartına taşındı. Social Media sözleşmesinde bulunmayan GA4 Allocation sekmesi eklenmedi.
- Her sekmede `Showing n of n`, `Search by name or ID`, gerçek durum filtresi ve Platform/Brand
  hiyerarşisi ikincil filtresi; sıralama, sticky header ve yatay tablo scroll tamamlandı.
- Brand satırlarındaki Setup/Edit aksiyonu setup drawer'ını açar; account ve mapping review
  dialogları gerçek backend durumlarını gösterir.
- Üst aksiyonlar ilgili Mappings/Sync görünümüne geçer; Refresh Platform yalnız mevcut GET
  sorgularını yeniler ve backend'de yazma ya da provider operasyonu başlatmaz.
- Brand Setup drawer adımları: Brand Information, Social Accounts, Sync Settings ve Readiness
  Summary.
- Setup yüzeyinde yalnız Facebook, Instagram ve TikTok bulunur.
- Pending/running iş varken 3 saniyelik polling; tamamlanınca dashboard/settings invalidation ve
  toast uygulanır.
- Backend mutation capability kapalıyken sync, backfill ve repair aksiyonları disabled ve
  açıklamalıdır; GET hiçbir operasyon başlatmaz.

## TikTok owner handoff güvenliği

- Signed `launch_target=tiktok_owner_activation` session payload'ında korunur.
- Handoff GET'i fresh SSO için hem upstream `issued_at` hem local consume zamanını 10 dakikalık
  pencereyle doğrular.
- Handoff yalnız session'daki exact somut Brand, güncel write authority ve Settings permission
  ile açılır; wrong Brand, rollup, read access, eksik target ve stale session fail-closed olur.
- Readiness GET'i `no-store`, GET-only ve read-only'dir; intent/state/credential üretmez,
  provider OAuth veya dış ağ çağrısı yapmaz.
- Provider başlangıcı cutover öncesinde `oauth_start_available=false` kalır.

## Erişilebilirlik

- Tablist/tabpanel, table header, status/alert/live-region semantiği eklendi.
- Dialog ve drawer focus trap, Escape close, backdrop close ve opener focus return uygular.
- Desktop/mobile responsive grid ve horizontal table scroll uygulanır.
- Reduced-motion tercihi mevcut shell kontratıyla korunur.

## Kanıt

Canonical komut:

```text
./scripts/quality/fase8_social_pages_settings_check.sh
```

Tek başarılı canonical koşunun sonuçları:

- Disposable PostgreSQL full backend regression: `117 passed`.
- Faz 8 owner-handoff/dashboard/boundary hedefli backend suite: `15 passed`.
- Vitest + React Testing Library: `13 passed`.
- Playwright Chromium: `8 passed`, `4 skipped`; skip'ler yalnız karşı viewport'a ait intentional
  desktop/mobile project ayrımıdır.
- PNG download, table-first Settings, social-only setup drawer, dialog focus return ve direct
  TikTok activation GET-only denial browser üzerinde doğrulandı.
- TypeScript strict typecheck ve Vite production build geçti (`1878 modules transformed`).
- `npm audit --audit-level=high`: `0 vulnerabilities`.
- Ruff, OpenAPI export/type generation, secret scan, canonical vocabulary ve source-write guard:
  temiz.

## Güvenlik ve kapsam

- Kaynak projeler yalnız read-only referans olarak kullanıldı.
- Production DB/provider/traffic/schedule, gerçek OAuth, credential, timer veya Git push yoktur.
- V2 dormant ve bütün production writer gate'leri kapalıdır.

## Tarihsel çıkış kapısı kararı — superseded

Ürün parity checklist'i ve accessibility testleri yeşildir. Faz 8 kapanmıştır. Sıradaki izinli
iş **Faz 9 — Offline release rehearsal** kapsamıdır.

Yukarıdaki 2026-07-14 kararı 2026-07-17 düzeltme notuyla supersede edilmiştir.
