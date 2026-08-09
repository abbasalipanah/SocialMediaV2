# Revision 6 — R3 Dashboard API ve Veri Sözleşmesi Raporu

**Durum:** PASS

**Tarih:** 2026-08-07

**Yazılabilir tek proje:** `/home/api/colab_scripts/SocialMediadownstream`

**Canonical kaynak:** `/home/api/colab_scripts/SocialMedia` — salt okunur

## Sonuç

R1 canonical frontend'in ihtiyaç duyduğu dashboard alanları mevcut
`PlatformDashboard` response'una eklendi. Paralel legacy response, `/api/v2` veya
runtime source import'u oluşturulmadı. Backend domain modeli, aggregation, FastAPI
OpenAPI, generated TypeScript, runtime Zod ve frontend Stories tüketimi aynı tek
sözleşmeye bağlıdır.

Makine-okunur alan ve semantik mapping:
[`r3_dashboard_contract_mapping.json`](./r3_dashboard_contract_mapping.json)

## Eklenen typed sözleşmeler

- structured Instagram Stories: summary, previous summary, trend, navigation,
  actions ve item-level metrikler;
- `source_breakdown` ve `paid_available`;
- platform bazlı `audience_capabilities`;
- `content_summary` ve `top_hashtags`;
- content-level views, reach, media candidates ve video watch alanları;
- metric ve series başına açık methodology;
- metric/content/story/source alanlarında honest availability metadata;
- community için top commenters ve top liked comments.

Bütün yeni `PlatformDashboard` alanları OpenAPI'de required'dır. Gerçekte
toplanmamış provider değeri sayı `0` yapılmaz; alan `null` olur ve ilgili
`data_status`/availability alanı nedeni taşır. `stories` sözleşmesi hiç yoksa
`null` olur.

## Metric semantiği

Metric catalog snapshot, flow, cumulative ve ratio ayrımını backendde uygular.
Frontend artık follower/source/engagement serisi uydurmaz.

- Facebook ve TikTok `new_followers`, follower snapshot'larından yalnız catalog'un
  `cumulative_delta:v1:utc_day` metodolojisiyle backendde türetilir.
- TikTok video view change aynı reset-aware cumulative delta sözleşmesini kullanır.
- TikTok total engagements, likes/comments/shares bileşenlerinden
  `sum_components:v1:same_sample` ile üretilir.
- TikTok engagement rate backendde total engagements / video views olarak yeniden
  hesaplanır; zero denominator sonucu unavailable kalır.
- Derived KPI'ların günlük serileri de aynı catalog metodolojisiyle backendde
  üretilir.

## Structured Stories

Instagram Stories frontend'i artık generic `DashboardContent` ve aggregate
breakdown tahminlerini kullanmıyor; yalnız `PlatformDashboard.stories` alanını
tüketiyor. Story contract yoksa canonical R1 davranışı gereği Stories paneli boş
kalıyor.

Provider item-level alanları varsa summary, previous summary, daily trend,
navigation/actions ve story item'ları `available` olabilir. Yalnız aggregate veya
eksik alan varsa gerçek alanlar korunur, diğerleri `null` ve sözleşme `partial`
olur. Local demo bu ikinci durumu özellikle doğrular.

R1 ortak fixture'daki `instagram_full_with_stories` vakası aynı fixture üzerinden
Zod ile parse edilmekte ve V2 Stories render'ında altı canonical bölümün tamamını
doğrulamaktadır.

## Content, source ve audience dürüstlüğü

- Content tablosu typed views/reach/interactions alanlarını kullanır; eksikler `—`
  kalır.
- Content Type, Content Type Reach ve Top Hashtags backend summary alanlarından
  beslenir; caption veya breakdown frontend fallback'i kaldırıldı.
- Organic/paid pie verisi yalnız `source_breakdown` alanından gelir. Paid öğesi
  yalnız `paid_available=true` olduğunda gösterilir.
- Facebook age/gender ve activity capability'leri daima
  `provider_unavailable` durumundadır. Local demo'daki sentetik Facebook heatmap
  kaldırıldı; görünür kart honest empty state üretir.
- Facebook geo, Instagram ve TikTok audience durumları typed availability enum'u
  taşır; Audience tab'inin kendisi gizlenmez.

## Contract zinciri

| Katman | Kanıt |
|---|---|
| Backend domain | `backend/app/domain/reporting/models.py` |
| Metric catalog | `backend/app/domain/metrics/__init__.py` |
| Aggregation/query | `dashboard_aggregation.py`, `dashboards.py` |
| OpenAPI | `docs/contracts/social-media-v2-openapi.json` |
| Generated TypeScript | `frontend/src/api/openapi.generated.ts` |
| Runtime validation | `frontend/src/api/contracts.ts` |
| Shared fixture render | `Revision6CanonicalFixture.test.tsx` |
| Deterministic validator | `scripts/quality/revision6_r3_contract.py` |

## Doğrulamalar

| Kontrol | Sonuç |
|---|---|
| Backend full pytest | PASS — 104 passed, 15 PostgreSQL environment-gated skipped |
| Frontend full Vitest | PASS — 4 dosya, 22 test |
| Structured story provider-field testi | PASS |
| R1 shared fixture + Zod + Stories render | PASS |
| OpenAPI export | PASS |
| Generated TypeScript | PASS |
| TypeScript typecheck | PASS |
| Fresh production build | PASS — 2543 module |
| R3 deterministic contract validator | PASS |
| Architecture/vocabulary guards | PASS |
| Revision 6 source write guard | PASS |

PostgreSQL testlerinin 15'i canlı DB kullanılmaması ve disposable
`TEST_POSTGRES_URL`/parity DB'lerinin bu aşamada verilmemesi nedeniyle skip oldu.
Tam persistence çalışması R4, disposable PostgreSQL sertifikasyonu R7 kapsamındadır.

Build başarılıdır. `PlatformPage` chunk'ı 608.64 kB ile Vite'ın 500 kB bilgi amaçlı
uyarısını sürdürmektedir; R5/R7 bundle incelemesine devredildi.

## R4'e devredilen işler

R3 veri yolunu typed ve fail-honest hale getirdi; provider ve persistence'ın bütün
alanları doldurması R4 kapsamındadır:

- content/story item metriklerinin V2-owned DB'de saklanması ve hydrate edilmesi;
- Meta/TikTok pagination, retry, checkpoint, refresh ve partial response parity'si;
- durable cover/thumbnail/media candidate zinciri;
- persisted previous-period Stories ve daily history;
- capability durumlarının collector state'inden projeksiyonu.

Bu alanlar tamamlanana kadar API bunları `null`/`partial`/`unavailable` olarak
gösterecek; fixture verisi provider gerçeği sayılmayacaktır.

## Güvenlik ve kapsam

SocialMedia, Accumulate ve performance_marketing üzerinde yazma, test/build, DB,
media, servis, process, port veya routing işlemi yapılmadı. Kaynak projeler yalnız
salt-okunur incelendi ve kapanış source write guard aynı baseline ile geçti.

## R3 çıkış kararı

R3 çıkış kapısı sağlandı: R1 envanterindeki veri-bağımlı yüzeyler typed alana veya
açık availability durumuna sahiptir; frontend placeholder ile gerçek veri taklidi
yapmaz. Commit veya push kullanıcı istemediği için yapılmadı.
