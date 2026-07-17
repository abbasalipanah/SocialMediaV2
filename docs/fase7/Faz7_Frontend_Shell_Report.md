# Faz 7 — Frontend Shell Kapanış Raporu

Tarih: `2026-07-14`

Düzeltme tarihi: `2026-07-17`

Durum: **2026-07-14 KAPANIŞ KARARI GEÇERSİZ KILINDI — parity düzeltmesi uygulandı**

## 2026-07-17 düzeltme notu

Bu raporun ilk sürümündeki “desktop/mobile shell reference ile eşleşmektedir” sonucu kaynak
render zinciriyle doğrulanmıyordu. Uygulamadaki koyu, özel sidebar; Performance Marketing
referansındaki beyaz/blur sidebar, Analytics ağacı, connector çizgileri ve alt aksiyon düzeniyle
aynı değildi. Bu nedenle ilk kapanış kanıtı release/parity kanıtı olarak kullanılamaz.

2026-07-17 çalışma ağacı düzeltmesinde shell tekrar kaynak koda göre kuruldu:

- `performance_marketing/frontend/src/layout/AppSidebar.tsx` ve `AppTopbar.tsx` davranışsal/görsel
  referans olarak yeniden okundu;
- beyaz/blur sabit sidebar, Overview + açılır Analytics ağacı, connector/locked state, Settings,
  Support, Back to Accumulate ve Sign out hiyerarşisi uygulandı;
- topbar Brand family, child Brand, platform account ve profile seçicileri korunup referansın açık
  surface ve yoğunluğuna hizalandı;
- `<1024px` drawer ve 390 px mobil yerleşim gerçek tarayıcı screenshot smoke ile doğrulandı.

Güncel local doğrulama: frontend production build yeşil, Vitest `17 passed`; 1440×1000 desktop
ve 390×844 mobile browser smoke'larında yatay taşma veya session bağlantı hatası görülmedi.
Bu düzeltme, production aktivasyonu veya `RELEASE_CANDIDATE_COMPLETE` kararı değildir.

## Sonuç

Performance Marketing yalnız görsel/davranış referansı olarak okunarak Social Media V2 için
bağımsız React 19 shell'i uygulandı. Reference source projelerine write yapılmadı; paid-media,
Google Analytics, campaign, currency/spend veya sahte notification davranışı downstream'e
taşınmadı.

## Teslimatlar

- React Router ile gerçek ve reload-safe route'lar:
  `/overview`, `/facebook`, `/instagram`, `/tiktok`, `/settings`, nested TikTok connect/audit,
  `/sso/consume` ve `/login`.
- Desktop fixed sidebar; `<1024px` drawer/backdrop; active, locked ve backend capability-driven
  channel state; route değişiminde drawer close.
- Mobile full-width selector grid; parent/child/all-child backend rollup ve platform-account
  selector'ları.
- Kullanıcı bazlı `social-media-v2:selected-brand:<user>` storage; Brand değişiminde account
  reset; platform bazlı account memory ve invalid-account → `all` davranışı.
- `AuthProvider` ve `BrandScopeProvider`; SSO session checking, SSO-first login, logout, profile
  user/email/role/source görünümü.
- TanStack Query scope-aware query key'leri ve abort-signal cancellation.
- Backend linked-account + capability bilgisinden `navigation_available`; frontend role string'i
  veya label'dan permission türetmez.
- Accessible popover primitive: focus trap, Escape, focus return, outside-click ve karşılıklı
  kapanma.
- Route-level lazy loading, global Error Boundary ve explicit loading/error state'leri.
- Vite `3010` strict port ve same-origin local API proxy; PWA/service worker yok.
- Deterministik backend OpenAPI export'u, `openapi-typescript` üretimi ve API boundary'de Zod
  runtime validation.

## Backend sözleşme tamamlamaları

- SSO contract'ında zaten doğrulanan e-posta ve `source_system=accumulate`, hash-only local
  session payload'ına ve typed `/api/auth/me` response'una taşındı.
- Workspace capability platform kaydı `linked_account_count` ve `navigation_available` alanlarıyla
  genişletildi. Stored linked account, collector bootstrap registry'sini sahte `available`
  yapmadan dashboard navigation'ını açabilir.

## Canonical doğrulama

Komut:

```text
./scripts/quality/fase7_frontend_shell_check.sh
```

Tek başarılı koşudaki sonuçlar:

- Faz 6 disposable PostgreSQL full regression: `115 passed`.
- Faz 6 hedefli API/regression: `19 passed`.
- Frontend Vitest + React Testing Library: `9 passed`.
- Playwright Chromium: `4 passed`; `2 skipped` yalnız karşı viewport'a ait intentional project
  ayrımıdır (desktop testi mobile project'te, mobile testi desktop project'te).
- Desktop route reload, capability navigation ve profile shell doğrulandı.
- Mobile drawer/backdrop, selector grid ve horizontal-overflow sentinel doğrulandı.
- SSO-first signed-out ekranı desktop ve mobile projelerinde doğrulandı.
- TypeScript strict typecheck ve Vite production build geçti (`1866 modules transformed`).
- `npm audit --audit-level=high`: `0 vulnerabilities`.
- Ruff, secret scan, canonical vocabulary, built artifact ve source-write guard: temiz.

## Güvenlik ve kapsam sonucu

- Production DB/provider/traffic/schedule erişimi veya aktivasyonu yapılmadı.
- V2 dormant ve product write gate'leri kapalı kaldı.
- TikTok connect nested shell route'u GET üzerinde intent, state, provider redirect veya durable
  mutation üretmez; owner/fresh-SSO activation ayrıntısı Faz 8 kapsamındadır.
- Social dashboard detayları ve Settings tabloları bilinçli olarak Faz 8'e bırakıldı; Faz 7
  placeholder'ları sahte KPI/data üretmez.

## Tarihsel çıkış kapısı kararı — superseded

Desktop/mobile shell davranışı reference sözleşmesi ve browser smoke'larıyla eşleşmektedir.
Faz 7 kapanmıştır. Sıradaki izinli iş **Faz 8 — Social sayfalar ve Settings** kapsamıdır.

Yukarıdaki 2026-07-14 kararı 2026-07-17 düzeltme notuyla supersede edilmiştir.
