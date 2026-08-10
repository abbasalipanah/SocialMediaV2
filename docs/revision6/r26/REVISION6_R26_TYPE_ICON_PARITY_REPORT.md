# Revision 6 · R26 — All Performing Content Type icon parity

Tarih: `2026-08-10`

Durum: `COMPLETE — V2 frontend loopback certified`

Kod commit: `e05c482`

Frontend release: `/opt/social-media-v2/releases/20260810T145042Z-r26typeicons/frontend`

## Sonuç

R25 All Performing Content Type pill'leri V1'deki ikon diline taşındı:

- `reel` ve `video`: pembe video-camera ikonu;
- `post`, `image` ve diğer non-video content türleri: mavi-gri activity/post ikonu.

Mapping yalnız backend'in typed `DashboardContent.content_type` değerini kullanır. Caption, URL
veya demo veriden tür tahmin edilmez. İkon `aria-hidden=true` dekoratiftir; görünür Type label
erişilebilir ad olarak korunur. Neutral rounded pill, V1 boşluk ve renk yoğunluğuna yaklaştırıldı.

R25'in sütun sırası, sorting, engagement formülü, ayrı Cover/Caption linkleri, sticky header ve
internal scroll davranışları değişmedi.

## Doğrulama

| Kontrol | Sonuç |
|---|---|
| Frontend unit/component | `35 passed` |
| Post/Image icon variant | pass; `is-post` + SVG |
| Reel/Video icon variant | pass; `is-video` + SVG |
| Icon accessibility | pass; decorative SVG, text label retained |
| Typecheck/build | pass; `2.537` modül |
| Desktop/mobile Playwright | `17 passed`, `5` bilinçli project-applicability skip |
| Canonical visual snapshots | Facebook, Instagram, TikTok desktop güncellendi ve geçti |
| Pine Beach signed runtime | üç platform Cover/Content Type pill icon count exact match |
| Browser/API errors | console `0`, request failure `0`, API 5xx `0` |
| Secret/vocabulary/source guards | pass |

Build ve deployed frontend ağaç SHA-256 değeri
`3bfba24d892bb5869262984eb97057db9aed443bd7aa64a1dfa47048931c3dda` olarak eşleşti.

## Release ve sınır

Yalnız V2 frontend symlink'i atomik değiştirildi ve Nginx reload edildi. R25 frontend
`/opt/social-media-v2/releases/20260810T143909Z-r25table/frontend` rollback probe'u ve R26
forward probe'u geçti. Son durumda V2 web/API 200 ve yalnız loopback'tedir.

Backend `/opt/social-media-v2/releases/20260810T140721Z-r24audit/backend` üzerinde kaldı. V2 DB,
XLSX, provider, collection service/timer, SocialMedia, Accumulate, Performance Marketing, DNS,
TLS, shared Nginx ve public route değiştirilmedi. Collection service/timer inactive/disabled'dır.
