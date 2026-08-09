# Revision 6 — R2 V2 WIP Doğrulama Raporu

**Durum:** PASS

**Tarih:** 2026-08-07

**Yazılabilir tek proje:** `/home/api/colab_scripts/SocialMediadownstream`

**Canonical kaynak:** `/home/api/colab_scripts/SocialMedia` — salt okunur

## Sonuç

R0'da dondurulan gerçek WIP kapsamı olan 13 tracked + 1 untracked dosyanın tamamı,
R1 canonical frontend envanterine karşı incelendi. Hiçbir WIP dosyası silinmedi ve
unrelated refactor yapılmadı. Dört kritik risk yalnız V2 içinde minimal patch ile
düzeltildi:

1. Facebook'un reachable audience ağacından canonical olmayan Age & Gender çıkarıldı;
   `Page Like Types (Organic vs Paid)` geri getirildi.
2. Local demo artık Meta'nın sağlamadığı `page_fans_gender_age` verisini üretmiyor.
3. Instagram Stories, canonical davranışa uygun biçimde Cover'dan çıkarıldı ve yalnız
   Stories tab'inde kaldı.
4. Facebook/Instagram/TikTok frontendinde metodolojisi ve typed availability bilgisi
   olmayan follower, source-split ve engagement türetmeleri kaldırıldı. Eksik veri
   `null`, boş grafik veya `—` olarak dürüstçe kalıyor.

Dosya bazlı kararların tamamı
[`r2_wip_review.json`](./r2_wip_review.json) içinde makine-okunur olarak kayıtlıdır.

## WIP diff review özeti

| Sonuç | Dosya sayısı | Açıklama |
|---|---:|---|
| PASS | 7 | R1 yönü doğru; WIP korundu |
| PARTIAL_FIXED | 5 | Yanlış varsayım küçük patch ile düzeltildi, kalan sözleşme işi R3/R5'e ayrıldı |
| PARTIAL_DEFERRED | 2 | CSS ve test kapsamının exact parity kapanışı R5/R7'de yapılacak |
| Silinen WIP | 0 | R0 koruma şartı sağlandı |

R2 sırasında master plandaki “13 dosya” ifadesi, R0 kanıtıyla uyumlu olacak şekilde
“13 tracked + 1 untracked” olarak yalnızca sayısal açıdan düzeltildi.

## R1 ortak fixture tüketimi

R1 fixture'ı kopyalanmadı veya V2 için ayrılaştırılmadı. Yeni
`frontend/src/test/Revision6CanonicalFixture.test.tsx`, doğrudan
`docs/revision6/r1/canonical_dashboard_fixture.json` dosyasını materialize ederek şu
kritik sözleşmeleri V2 render'ında doğruluyor:

- Facebook, Instagram ve TikTok tab listeleri;
- Facebook'ta Page Like Types ve Age & Gender'ın görünmemesi;
- Instagram Cover'ın Stories'i dışlaması;
- TikTok follower snapshot'larından Follower Growth KPI'sı uydurulmaması.

Structured Stories ve bütün kartların aynı fixture üzerinden exact render assertion'ı,
gerekli typed API alanları R3'te tamamlandıktan sonra R5'te genişletilecek.

## Doğrulama sonuçları

| Kontrol | Sonuç |
|---|---|
| `npm ci --ignore-scripts --no-audit --no-fund` | PASS — dependency lock tutarlı |
| `npm run typecheck` | PASS |
| `npm test -- --run` | PASS — 4 dosya, 21 test |
| R1 shared fixture V2 render testi | PASS — 2 test |
| Backend `pytest -p no:cacheprovider` | PASS — 103 passed, 15 environment-gated skipped |
| Local demo contract | PASS — 2 test; full backend sonucuna dahil |
| `npm run build` | PASS — fresh Vite production build, 2543 module |
| R1 inventory validator | PASS |
| Revision 6 source write guard | PASS |

PostgreSQL testlerinin 15'i `TEST_POSTGRES_URL` ve ayrı parity DB'leri bilinçli olarak
verilmediği için skip oldu. Canlı DB kullanılmadı. Disposable PostgreSQL ile tam
persistence sertifikasyonu R7 standalone gate'inin parçasıdır.

Build fresh üretildi; eski `dist` artifact'i kanıt sayılmadı. Build başarılıdır,
ancak `PlatformPage` chunk'ı 608.25 kB ile Vite'ın 500 kB bilgi amaçlı uyarısını
üretmektedir. Bu uyarı R2 gate'ini düşürmez; R5/R7 bundle incelemesinde ele alınacaktır.

## R3 ve R5'e devredilen açık işler

R3 veri sözleşmesi:

- structured Stories ve story-level views/reach/navigation/actions;
- `source_breakdown`, `paid_available`, `audience_capabilities`;
- `content_summary`, `top_hashtags`, content-level metric/media alanları;
- explicit metric methodology ve availability metadata.

R5 exact frontend parity:

- canonical route/sidebar ve canonical olmayan görünür shell öğelerinin kaldırılması;
- `Last 7/30/90/365 Days` etiketleri ve `?tab=`/popstate senkronizasyonu;
- Content Winners ve comment queue gibi canonical olmayan kartların kaldırılması;
- bütün kart/metin/kolon/sıra/state ve desktop/mobile görsel eşitliği.

## Güvenlik ve kapsam kanıtı

SocialMedia, Accumulate ve performance_marketing üzerinde hiçbir dosya, Git state,
DB, media, build, test/cache, servis, process, port veya routing değişikliği yapılmadı.
Kaynak projelerde test/build çalıştırılmadı. Revision 6 source write guard başlangıç,
tam regresyon ve kapanış kontrollerinde aynı baseline ile geçti.

## R2 çıkış kararı

R2 çıkış kapısı sağlandı: mevcut WIP korunmuş, yanlış WIP varsayımları düzeltilmiş,
aynı R1 fixture V2 render testine bağlanmış ve V2-only statik/test/build kontrolleri
yeşildir. Ayrı bir R2 commit'i önerilir; kullanıcı açıkça istemediği için commit veya
push yapılmamıştır.
