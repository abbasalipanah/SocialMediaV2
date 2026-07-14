# Faz 8 — Social Sayfalar ve Settings Kapanış Raporu

Tarih: `2026-07-14`

Durum: **KAPALI — çıkış kapısı yeşil**

## Sonuç

Overview, Facebook, Instagram, TikTok ve Settings yüzeyleri gerçek Faz 6 DTO'larına bağlandı.
Frontend yalnız backend'in döndürdüğü destekli metrikleri gösterir; `null` veya `unavailable`
değerler sıfıra çevrilmez. Parent rollup frontend'de birleştirilmez ve tek backend cevabı kullanılır.

## Ürün parity kontrolü

- Overview: KPI bandı, follower/growth trendleri, platform health, content intelligence,
  community, recent/top content, stored AI Insights ve PNG export tamamlandı.
- Facebook: Cover, Page, Content ve Audience sekmeleri tamamlandı.
- Instagram: Cover, Page, Content, Stories ve Audience aynı sayfa altında tamamlandı; Stories
  için ayrı route veya navigation öğesi oluşturulmadı.
- TikTok: profile header, Overview, Videos ve capability-gated Audience tamamlandı.
- Cover asset'i mevcut reporting DTO'sunda bulunmadığı için dürüst `unavailable` state gösterilir;
  sahte görsel üretilmez.
- Reporting catalog'da ayrı impressions metriği bulunmadığı için türetilmiş veya reklam metriği
  gösterilmez; mevcut reach/views sözleşmesi korunur.
- Ortak loading, error, empty, partial, freshness ve retry durumları tamamlandı.

## Settings parity kontrolü

- Brands, Social Accounts, Brand Links ve Sync & Backfill table-first görünümleri tamamlandı.
- Arama, platform filtresi, sıralama, result count, sticky header, hiyerarşi indent/pill,
  durum/health/backfill/failure hücreleri tamamlandı.
- Linked-account/manual-sync review dialogları ve Brand-link detail dialogu tamamlandı.
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

## Çıkış kapısı kararı

Ürün parity checklist'i ve accessibility testleri yeşildir. Faz 8 kapanmıştır. Sıradaki izinli
iş **Faz 9 — Offline release rehearsal** kapsamıdır.
