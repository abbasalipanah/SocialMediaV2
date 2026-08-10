# Revision 6 · R27 — Interactive pie/donut parity

Tarih: `2026-08-10`

Durum: `COMPLETE — V2 frontend loopback certified; protected-source baseline approval pending`

Kod commit: `7714920`

Frontend release: `/opt/social-media-v2/releases/20260810T150721Z-r27piehover/frontend`

## Sonuç

Facebook, Instagram ve TikTok platform yüzeylerinin ortak `PulsePieCard` bileşeni V1'in aktif
dilim davranışına geçirildi. Hover/focus/touch ile yalnız seçili pozitif dilim dışarı taşınır ve
label, formatlanmış değer ile toplam yüzdesini içeren tooltip açılır. Legend aynı durumu kontrol
eder; dilimler klavye ile erişilebilir ve zero/unavailable veri dürüst empty state olarak kalır.

Backend typed pie row'ları değişmeden kullanılır. Frontend yeni aggregation, demo değer veya
metrik tahmini üretmez.

## Doğrulama

| Kontrol | Sonuç |
|---|---|
| Frontend unit/component | `37 passed` |
| Pie hover/focus/touch/single-segment | pass |
| Typecheck/build | pass; `2.537` modül |
| Desktop/mobile Playwright | `17 passed`, `5` bilinçli project-applicability skip |
| Canonical snapshots | Facebook, Instagram, TikTok desktop/mobile pass |
| Pine Beach signed runtime | üç platform Cover/Content active slice + yüzde tooltip pass |
| Browser/API errors | console `0`, request failure `0`, API 5xx `0` |
| Secret/vocabulary guards | pass |

Build ve deployed frontend ağaç SHA-256 değeri
`28c6f19bdd394d5242969ea8b3c9e8a4273cd292fbd4968da8fa715ae4827c3c` olarak eşleşti.

## Release ve sınır

Yalnız V2 frontend symlink'i atomik değiştirildi. R26 rollback ve R27 forward probe'u geçti;
V2 web/API loopback sağlık kontrolleri başarılı kaldı. Backend
`/opt/social-media-v2/releases/20260810T140721Z-r24audit/backend` üzerinde kaldı. V2 DB, XLSX,
provider, collection, SocialMedia, Accumulate, Performance Marketing, DNS, TLS, shared Nginx ve
public route değiştirilmedi.

Protected `SocialMedia` kaynak ağacında R26 sonrasında dışarıdan oluşan yeni drift source guard
tarafından yakalandı. Bu çalışma o ağaca yazmadı ve baseline'ı yenilemedi. Final GitHub baseline
kapanışı kullanıcı kararını bekler.
