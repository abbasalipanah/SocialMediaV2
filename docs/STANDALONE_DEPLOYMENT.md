# Social Media V2 — Bağımsız Runtime Runbook

Tarih: `2026-08-07`

Durum: **REPOSITORY ARTIFACT — UYGULANMADI**

Bu runbook yalnız Social Media V2 kaynaklarını kapsar. Mevcut Social Media, Accumulate veya başka
bir service/timer durdurulmaz, restart edilmez ve onların veritabanı, media alanı, process'i veya
routing'i kullanılmaz. Bu dosyanın varlığı staging/production işlem yetkisi vermez.

## V2-owned parçalar

- uygulama: `/opt/social-media-v2`
- ayar: `/etc/social-media-v2/production.env`
- media: `/var/lib/social-media-v2/media`
- ayrı PostgreSQL DB/role: `social_media_v2*`
- API: `127.0.0.1:8026`
- migration: `social-media-v2-migrate.service`, explicit one-shot
- API: `social-media-v2-api.service`
- collector: `social-media-v2-collection.service/.timer`
- public adres: `https://social.theaccumulate.com`

Repository'deki hiçbir service, timer veya Nginx dosyası otomatik kurulmaz ya da etkinleşmez.

## Güvenli ilk başlangıç

`deploy/env/social-media-v2.production.env.example` doğrudan aktif writer başlatmaz:

```text
APP_ENV=production
SOCIAL_RUNTIME_MODE=standalone_ready
SOCIAL_WRITES_ENABLED=false
SOCIAL_META_ACCOUNT_ENABLED=false
SOCIAL_META_COLLECTION_ENABLED=false
SOCIAL_TIKTOK_ACCOUNT_ENABLED=false
SOCIAL_TIKTOK_COLLECTION_ENABLED=false
SOCIAL_WORKER_SCHEDULE_ENABLED=false
```

Bu durumda SSO consume dahil bütün local mutation'lar, provider activation/egress ve automated
schedule fail-closed kalır. Production `active` moda geçiş R7/R8 kapıları, ayrı kullanıcı/on-call
onayı, V2-owned credential ve staging kanıtı olmadan yapılamaz.

## Operations tarafından uygulanacak sıra

Aşağıdaki adımlar bu repository çalışması sırasında uygulanmaz; yetkili Operations ekibi ayrı
change kaydıyla yürütür:

1. Ayrı Linux user/group, klasör ve V2-owned PostgreSQL DB/role oluşturulur.
2. Immutable backend/frontend artifact'i kurulur. Secretlar chat, log, image veya Git'e yazılmaz.
3. Env önce `standalone_ready`, writes/provider/schedule off olarak yüklenir.
4. Migration checksum ve hedef DB adı incelenir; migration yalnız explicit
   `social-media-v2-migrate.service` one-shot ile çalıştırılır. API start otomatik migration yapmaz.
5. API unit'i kurulur; yalnız `/api/health` ve `/api/operations/readiness` doğrulanır.
6. V2-owned staging'de `APP_ENV=staging`, `SOCIAL_RUNTIME_MODE=staging`, explicit writes ve secure
   SSO secret/cookie ile fake/approved staging SSO launch, logout ve Brand scope E2E yapılır.
7. Meta/TikTok callback ve rotated secret değerleri sahiplerce exact doğrulanır. Provider gate'leri
   bu kontrol ve time-boxed activation sentinel'i tamamlanana kadar kapalı kalır.
8. Sandbox/canary yalnız izinli tek Brand/account scope'unda çalıştırılır; sonuç ve rollback kanıtı
   kaydedilir.
9. `STANDALONE_RUNTIME_COMPLETE` sonrasında Accumulate ekibine yalnız
   `docs/ACCUMULATE_SSO_HANDOFF.md` taslağı gönderilir. Accumulate değişikliğini kendi ekibi yapar.
10. Canlı browser SSO doğrulandıktan sonra `SSO_LIVE_VERIFIED` değerlendirilebilir. Provider
    collection ve worker timer platform bazlı ayrı onayla en son açılır.

## Health, readiness ve log

- API liveness `/api/health` üzerinde `status=ok` döndürmelidir.
- `/api/operations/readiness` yalnız V2 runtime mode, V2 DB ve seçili V2 Brand/account/job
  durumunu raporlamalıdır.
- Provider tokenı URL, response, stdout veya journald içinde görünmemelidir.
- V2 media yalnız `/var/lib/social-media-v2/media` altında oluşmalıdır.
- API ve collector stdout/stderr V2 systemd unit journal'ına gider; source project log'una yazmaz.
- Schedule flag kapalıyken scheduled worker DB bağlantısından ve provider egress'ten önce reddedilir.

## Rollback

Rollback yalnız V2-owned yüzeyleri hedefler:

1. Yeni Accumulate SSO launch'ları Operations ekibince durdurulur veya link kendi tarafında geri
   alınır.
2. Yalnız `social-media-v2-collection.timer` disable/stop edilir.
3. Yalnız `social-media-v2-api.service` durdurulur.
4. Yalnız V2 Nginx site yönlendirmesi geri alınır.
5. V2 DB/media hemen silinmez; inceleme ve kontrollü restore için korunur.

Rollback sırasında başka Social Media/Accumulate service, timer, DB, media veya dosyasına
dokunulmaz. V1 writer sahipliği değişmediği için V1/V2 writer cutover veya ortak DB rollback adımı
yoktur.
