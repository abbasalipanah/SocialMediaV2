# Revision 6 · R29 — Story Navigation Split interactive donut

Tarih: `2026-08-10`

Durum: `COMPLETE — V2 frontend loopback certified; protected-source baseline approval pending`

Kod commit: `31fc167`

Frontend release: `/opt/social-media-v2/releases/20260810T160812Z-r29navigationdonut/frontend`

## Sonuç

Instagram Stories Behaviour kartındaki düz Navigation Split stacked bar kaldırıldı. Tap Forward,
Swipe Forward, Tap Back ve Exits provider toplamları artık ortalanmış bir donut üzerinde
gösteriliyor. Dört legend label/yüzdesi donut'ın altında dar kartta da okunur kalıyor.

Stories ayrı bir pie implementasyonu oluşturmaz; R27 ortak `PulsePieVisualization` renderer'ını
kullanır. Hover/focus/touch ile aktif dilim dışarı taşınır ve tooltip label, gerçek değer ile
toplam yüzdesini gösterir. Null provider metriği sıfır olarak tahmin edilmez. Period Action Totals
ve backend verileri değişmedi.

## Doğrulama

| Kontrol | Sonuç |
|---|---|
| Frontend unit/component | `37 passed` |
| Eski navigation bar | DOM count `0` |
| Navigation donut | dört fixture segmenti, ortak SVG renderer |
| Active slice + tooltip | desktop/mobile Playwright pass |
| Typecheck/build | pass; `2.537` modül |
| Stories snapshots | desktop/mobile güncellendi ve geçti |
| Instagram Cover snapshots | desktop/mobile güncellendi ve geçti |
| Tam Playwright | `17 passed`, `5` bilinçli project-applicability skip |
| Pine Beach signed runtime | pie/active transform/yüzde tooltip pass |
| Browser/API errors | console `0`, request failure `0`, API 5xx `0` |
| Runtime test cleanup | `5` session + `5` replay JTI silindi; kalan `0` |

Build ve deployed frontend ağaç SHA-256 değeri
`7a8216a0a3e8189c53b82cb561ee9195dadf5bf9a13469783678815ff77a6ea2` olarak eşleşti.

## Release ve sınır

Yalnız V2 frontend symlink'i atomik değiştirildi. R28 rollback ve R29 forward probe'u geçti;
V2 web/API loopback sağlık kontrolleri başarılı kaldı. Backend
`/opt/social-media-v2/releases/20260810T140721Z-r24audit/backend` üzerinde kaldı. V2 DB, XLSX,
provider, collection, SocialMedia, Accumulate, Performance Marketing, DNS, TLS, shared Nginx ve
public route değiştirilmedi.

Protected `SocialMedia` kaynak ağacındaki dış drift değişmeden duruyor. Bu çalışma baseline'ı
yenilemedi; final GitHub baseline kapanışı kullanıcı kararını bekler.
