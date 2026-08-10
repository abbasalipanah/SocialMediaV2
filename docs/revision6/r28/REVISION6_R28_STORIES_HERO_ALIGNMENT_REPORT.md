# Revision 6 · R28 — Stories hero KPI and gallery alignment

Tarih: `2026-08-10`

Durum: `COMPLETE — V2 frontend loopback certified; protected-source baseline approval pending`

Kod commit: `db13a84`

Frontend release: `/opt/social-media-v2/releases/20260810T153903Z-r28storieshero/frontend`

## Sonuç

Instagram Stories hero kartındaki Story Views, Reach, Completion Rate ve Interactions KPI'larının
`vs previous story` comparison satırları kaldırıldı. Completion Rate'in kendi provider yüzdesi
korundu. Selected story actions ve altı aksiyon metriği değişmedi.

Story gallery sağ detay kolonundan çıkarılıp hero grid'in `grid-column: 1 / -1` tam-genişlik
satırına taşındı. Gallery artık kartın sol içerik hizasından başlar; yatay scroll, story seçimi,
outline, sıra numarası ve mobil akış korunur.

## Doğrulama

| Kontrol | Sonuç |
|---|---|
| Frontend unit/component | `37 passed` |
| Comparison text | DOM count `0` |
| Completion Rate | gerçek yüzde değeri görünür |
| Gallery layout | doğrudan hero child; grid start `1`, end `-1` |
| Typecheck/build | pass; `2.537` modül |
| Stories snapshots | desktop/mobile güncellendi ve geçti |
| Instagram Cover snapshots | desktop/mobile güncellendi ve geçti |
| Tam Playwright | `17 passed`, `5` bilinçli project-applicability skip |
| Pine Beach signed runtime | comparison/gallery/completion contract pass |
| Browser/API errors | console `0`, request failure `0`, API 5xx `0` |
| Runtime test cleanup | `5` session + `5` replay JTI silindi; kalan `0` |

Build ve deployed frontend ağaç SHA-256 değeri
`dd7efa3287ca7732d60629108dea3ae56b2fbf0ad5e6b702c9cca7f8fe57e164` olarak eşleşti.

## Release ve sınır

Yalnız V2 frontend symlink'i atomik değiştirildi. R27 rollback ve R28 forward probe'u geçti;
V2 web/API loopback sağlık kontrolleri başarılı kaldı. Backend
`/opt/social-media-v2/releases/20260810T140721Z-r24audit/backend` üzerinde kaldı. V2 DB, XLSX,
provider, collection, SocialMedia, Accumulate, Performance Marketing, DNS, TLS, shared Nginx ve
public route değiştirilmedi.

Protected `SocialMedia` kaynak ağacındaki dış drift değişmeden duruyor. Bu çalışma baseline'ı
yenilemedi; final GitHub baseline kapanışı kullanıcı kararını bekler.
