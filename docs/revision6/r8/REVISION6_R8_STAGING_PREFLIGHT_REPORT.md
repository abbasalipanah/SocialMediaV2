# Revision 6 / R8 Staging Readiness Ön-Kontrol Raporu

Tarih: `2026-08-07`

Durum: `LOCAL_STAGING_SSO_VERIFIED / WAITING_FOR_PUBLIC_ORIGIN_AND_PROVIDER_INPUT`

Bu çalışma yalnız `/home/api/colab_scripts/SocialMediadownstream` repository'sinde ve V2'ye
ait host yüzeylerinde yapılmıştır. V2 service user'ı, ayrı PostgreSQL DB/role, systemd
unit'leri ve loopback web/API runtime'ı oluşturulmuştur. SocialMedia, Accumulate,
performance_marketing, bunların veritabanları/servisleri ve shared canlı Nginx route'u
değiştirilmemiştir.

## Sonuç

R7 release candidate mevcut hostta V2-owned, loopback-only staging runtime olarak kurulmuştur.
V2-only sentetik issuer ile SSO session mutation'ı ayrı staging DB'de açılmış ve browser E2E
geçmiştir. Provider account/collection ve schedule kapıları kapalıdır. Public HTTPS origin,
onaylı Accumulate staging issuer'ı ve provider canary girdileri henüz yoktur.

| Kontrol | Sonuç |
|---|---|
| `/opt/social-media-v2` | V2 release + backend/frontend symlink hazır |
| `/etc/social-media-v2/production.env` | root-owned, secret değerleri rapor dışında |
| `/var/lib/social-media-v2/media` | V2 service user-owned, hazır |
| V2 migrate/API/web/collector systemd unit'leri | kurulu |
| `127.0.0.1:8026` V2 staging API | active/enabled |
| `127.0.0.1:3026` V2 staging web | active/enabled; same-origin API proxy |
| V2 staging PostgreSQL DB/role | `social_media_v2_staging`, ayrı ve migration uygulanmış |
| Collection service/timer | disabled/inactive |
| Local signed SSO login/logout + Brand scope | pass |
| Secure cookie + JTI replay rejection | pass |
| SSO/API access log suppression | pass |
| R6 runtime/deploy statik gate | pass |
| Source-write guard | pass |
| Backend local hedef suite | `122 passed`, PostgreSQL girdisi gerektiren `16 skipped` |
| Frontend Vitest | `23 passed` |
| R7 disposable PostgreSQL tam sertifikasyonu | `138 passed`, `0 skipped` — önceki canonical tur |
| R8 disposable staging deploy/rollback | pass |

PostgreSQL skip'leri ürün eksikliği değildir; bu preflight turunda gerçek staging veya disposable
DB hedefi verilmediği için beklenen koşullu skip'lerdir. R7'de aynı testlerin PostgreSQL'li tam
turu geçmiştir.

## Disposable staging deploy/rollback kanıtı

`scripts/quality/revision6_r8_disposable_staging_rehearsal.sh` yalnız geçici V2 kaynaklarıyla
başarıyla çalıştırıldı:

1. PostgreSQL 16 container'ı oluşturuldu.
2. `0001` ve `0002` migration'ları uygulandı; ikinci migration turu idempotent geçti.
3. Backend temiz repository kopyasından wheel olarak paketlendi ve geçici install root'una
   kuruldu.
4. API `standalone_ready`, writes/provider/schedule kapalı olarak `127.0.0.1:8026` üzerinde
   başlatıldı.
5. Health `status=ok`, readiness `runtime_mode=standalone_ready` ve `writes_enabled=false`
   doğrulandı.
6. Scheduled collector DB/provider egress öncesinde `Scheduled collection is disabled` ile
   fail-closed kaldı.
7. Rollback API'yi kapattı; `8026` listener'ın kapandığı doğrulandı.
8. Geçici PostgreSQL container'ı ve çalışma dizini temizlendi; source-write guard başlangıç ve
   bitişte geçti.

Bu kanıt actual staging kurulumu değildir ve `STANDALONE_RUNTIME_COMPLETE` üretmez.

## Mevcut host local staging kurulumu

Kullanıcının mevcut makineyi staging hedefi olarak açıkça seçmesinden sonra yalnız V2-owned
alanlarda gerçek local staging kurulumu yapıldı:

- Linux service user/group: `social-media-v2`;
- immutable release: `/opt/social-media-v2/releases/20260807T152619Z`;
- ayrı PostgreSQL DB/role: `social_media_v2_staging`;
- root-owned config ve V2-owned media alanı;
- migration one-shot service'i;
- API `127.0.0.1:8026`;
- shared/live Nginx'e dokunmayan ayrı V2 nginx process'i ile web `127.0.0.1:3026`;
- collection service/timer kurulu fakat disabled/inactive;
- web+API tam stop/start rollback ve recovery: pass;
- browser unauthenticated entry: `/login`, console error yok;
- local signed SSO: `/sso/consume` → `/settings`, authority/Brand scope/capability pass;
- authenticated `/instagram?tab=stories`: dashboard API `200`, Stories tab selected, başlık doğru,
  browser error/alert yok;
- session cookie: `Secure`, `HttpOnly`, `SameSite=Lax`;
- aynı JTI ile ikinci consume: `401`; logout: `204`; logout sonrası `/api/auth/me`: `401`;
- test session/JTI kayıtları ve test Brand'i doğrulama sonunda V2 DB'den temizlendi;
- API ve izole web access log'ları kapalı; token/JWT log taraması temiz.

Loopback proxy'de same-origin logout kontrolünün portu da karşılaştırabilmesi için yalnız V2
config'inde upstream `Host` başlığı `$http_host` olarak korunmuştur. Shared Nginx config'i
değiştirilmemiş veya reload edilmemiştir.

Mevcut `social.theaccumulate.com` Nginx route'u canlı V1 `52120` hedefine bağlı kaldı ve
değiştirilmedi. Yerel demo `3010/8000` süreçleri de kesintisiz kaldı. Makine-okunur kanıt:
`r8_local_staging_runtime.json`.

## Operations tarafından sağlanması gereken girdiler

Secret değerleri chat'e, repository'ye veya bu rapora yazılmadan aşağıdaki girdiler gerekir:

1. Staging public origin, DNS/TLS owner'ı ve exact callback origin kararı.
2. Accumulate staging issuer/consumer koordinasyonu ve onaylı secret reference'ı. Yerel sentetik
   secret yalnız V2 root-owned config'tedir ve bu koordinasyonun yerine geçmez.
3. Meta/TikTok staging app owner'ları, exact callback kaydı ve rotated-secret reference'ları.
4. Canary için tek onaylı Brand/account scope'u.
5. Public-origin/SSO/provider değişiklik penceresi, on-call ve kanıt saklama hedefi.

Makine-okunur secretsız checklist: `r8_operations_input_checklist.json`.

## Yetki sınırı ve sonraki yürütme sırası

Kalan girdiler ve açık Operations yetkisi sağlandıktan sonra yalnız V2 staging hedefinde:

1. Public HTTPS origin ve onaylı Accumulate staging issuer'ı bağlanır.
2. Onaylı issuer ile login/logout, Brand scope ve platform dashboard browser E2E tekrarlanır;
   yerel sentetik turda Instagram Stories dashboard'u zaten geçmiştir.
3. Meta/TikTok canary yalnız onaylı tek scope'ta ve time-boxed activation gate ile yürütülür.
4. `STANDALONE_RUNTIME_COMPLETE` ancak bütün kanıtlar yeşilse değerlendirilebilir.
5. Accumulate handoff bundan sonra hazırlanır; Accumulate değişikliğini kendi ekibi uygular.

Bu girdiler sağlanmadan shared Nginx, DNS, provider veya Accumulate mutasyonu başlatılmaz.

## Durum bayrakları

- `STANDALONE_PRODUCT_COMPLETE`: **true**
- `STANDALONE_RUNTIME_COMPLETE`: **false**
- `READY_FOR_ACCUMULATE_SSO_HANDOFF`: **false**
- `SSO_LIVE_VERIFIED`: **false**
- `TIKTOK_CONNECTION_VERIFIED`: **false**
