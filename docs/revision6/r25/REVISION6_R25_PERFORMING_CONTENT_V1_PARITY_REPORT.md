# Revision 6 · R25 — All Performing Content V1 parity

Tarih: `2026-08-10`

Durum: `COMPLETE — V2 frontend loopback certified`

Kod commit: `dcadc5a`

Frontend release: `/opt/social-media-v2/releases/20260810T143909Z-r25table/frontend`

## Sonuç

Facebook, Instagram ve TikTok'un shared All Performing Content tablosu V1'in daha okunaklı
tasarımına taşındı. Başlık alanındaki ikincil açıklama ve item badge kaldırıldı; tablo aşağıdaki
sütunları tam sırayla kullanıyor:

`# · Cover · Caption · Date · Type · Post Views · Post Reach · Likes · Comments · Shares · Engagement`

Cover ve Caption ayrı hücrelerdir. Geçerli credential-free HTTP(S) permalink varsa ikisi de aynı
gerçek provider içeriğini yeni sekmede `noopener noreferrer` ile açar. Link eksik veya geçersizse
URL tahmin edilmez ve hücreler tıklanabilir yapılmaz.

## Veri ve etkileşim sözleşmesi

Date başlangıçta descending sıralanır. Caption, Date, Type, Post Views, Post Reach, Likes,
Comments, Shares ve Engagement başlıklarının tümü gerçek client-side sıralama yapar. Aktif yön
görsel ok ve `aria-sort` ile birlikte değişir; sıralama yalnız mevcut typed satırları yeniden
düzenler, backend aggregation'ını değiştirmez.

Engagement değeri yalnız `DashboardContent.interactions / DashboardContent.reach × 100`
formülüyle bir ondalık yüzdeye çevrilir. `interactions`, provider'dan taşınan tüm etkileşim
sayısını korur; görünür Likes/Comments/Shares toplamıyla yeniden tahmin edilmez. Reach null veya
sıfırsa `—` gösterilir.

V1 satır yoğunluğu, geniş Caption alanı ve yeşil yüzde pill'i; V2'nin maksimum `520px` tablo
yüksekliği, sticky header, iç dikey/yatay scroll, hover ve klavye focus görünürlüğüyle birleştirildi.

## Doğrulama

| Kontrol | Sonuç |
|---|---|
| Frontend unit/component | `35 passed` |
| Canonical sütun sırası | pass; 11 exact header |
| Default Date sort | pass; descending + `aria-sort` |
| Caption sorting | pass; iki gerçek fixture satırı yeniden sıralandı |
| Engagement hesabı | pass; `12.3%`, `11.2%`, `10.2%` pozitif örnekler |
| Reach unavailable | pass; `—` |
| Cover ve Caption permalink | pass; exact href |
| Geçersiz/boş permalink | pass; link yok |
| Frontend typecheck/build | pass; `2.537` modül |
| Desktop/mobile Playwright | `17 passed`, `5` bilinçli project-applicability skip |
| Canonical visual snapshots | 3 platform × desktop/mobile güncellendi ve geçti |
| Pine Beach signed runtime | üç platform Cover/Content header, sort, engagement ve link pass |
| Runtime browser errors | console `0`, request failure `0`, API 5xx `0` |
| Secret/vocabulary/source guards | pass |

Build ve deployed frontend ağaç SHA-256 değeri
`15e4862df2daaa0688a4958299f959898c1e90c77ea29b41860b6b65bc095867` olarak eşleşti.
Makine-okunur contract: `docs/revision6/r25/r25_performing_content_contract.json`.

## Release ve rollback

Yalnız V2 frontend symlink'i atomik değiştirildi ve Nginx kesintisiz reload edildi. R24 frontend
`/opt/social-media-v2/releases/20260810T140721Z-r24audit/frontend` üzerine rollback probe'u,
ardından R25 forward probe'u geçti. Son durumda web 200, API health 200 ve operations readiness
`ready/staging` durumundadır.

Backend `/opt/social-media-v2/releases/20260810T140721Z-r24audit/backend` üzerinde kaldı. DB,
XLSX, provider, collection service/timer, SocialMedia, Accumulate, Performance Marketing, DNS,
TLS, shared Nginx ve public route değiştirilmedi. Collection service/timer inactive/disabled,
API ve web yalnız loopback'tedir.
