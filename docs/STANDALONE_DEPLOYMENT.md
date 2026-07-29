# Social Media V2 — Bağımsız Canlıya Alma

Tarih: `2026-07-29`

Bu işlem yalnız V2 kaynaklarını kurar. Mevcut Social Media veya Accumulate service/timer’ları
durdurulmaz, restart edilmez ve onların veritabanı kullanılmaz.

## Kurulacak V2 parçaları

- uygulama: `/opt/social-media-v2`
- ayar: `/etc/social-media-v2/production.env`
- media: `/var/lib/social-media-v2/media`
- ayrı PostgreSQL DB: `social_media_v2`
- API: `127.0.0.1:8026`
- systemd: `social-media-v2-api.service`
- collector: `social-media-v2-collection.service/.timer`
- public adres: `https://social.theaccumulate.com`

## Sıra

1. Ayrı Linux user/group, klasör ve ayrı PostgreSQL DB/user oluşturulur.
2. Backend venv kurulur; frontend production build alınır.
3. `deploy/env/social-media-v2.production.env.example`, Git dışında
   `/etc/social-media-v2/production.env` olarak doldurulur. SSO/provider/vault/DB secretları
   chat, log veya repository’ye yazılmaz.
4. `backend/scripts/apply_migrations.py` çalıştırılır. Komut yalnız V2 DB’ye bağlanmalıdır.
5. API unit ve Nginx config kurulur; önce `/api/health` ve `/api/operations/readiness` kontrol
   edilir.
6. Fake veya onaylı staging SSO ile login, Brand seçimi, dashboard ve logout browser E2E yapılır.
7. Meta/TikTok callback değerleri provider panellerinde exact doğrulanır. Provider kapıları bu
   kontrol tamamlanana kadar kapalı kalır.
8. Meta bağlantısı sandbox/canary ile kurulur ve tek hesapta manual collection doğrulanır.
9. TikTok owner bağlantısından sonra yalnız dönen pending connection için
   `python -m app.workers verify-tiktok --connection-id <ID>` çalıştırılır.
10. Sonuçlar doğrulanınca ilgili collection flag’leri ve en son
    `SOCIAL_WORKER_SCHEDULE_ENABLED=true` açılır; collection timer enable edilir.
11. Accumulate SSO menü bağlantısı en son bağlanır ve gerçek browser E2E yapılır.

## Health ve gözlem

- API health `status=ok` olmalı.
- readiness yalnız V2 DB’deki hesap/job/sync durumunu göstermeli.
- `linked_social_accounts.last_synced_at` ilerlemeli; hata halinde `health_status=error` ve
  secretsız error code görünmeli.
- Provider tokenı URL, response, stdout veya journald içinde görünmemeli.
- V2 media dosyaları yalnız `/var/lib/social-media-v2/media` altında oluşmalı.

## Rollback

1. Yalnız `social-media-v2-collection.timer` durdurulur ve disable edilir.
2. Yalnız `social-media-v2-api.service` durdurulur.
3. Yalnız V2 Nginx site yönlendirmesi geri alınır.
4. Accumulate menü linki operasyon ekibince önceki duruma döndürülür.
5. V2 DB/media hemen silinmez; hata incelemesi ve geri dönüş için korunur.

Rollback sırasında başka Social Media/Accumulate service, timer, DB veya dosyaya dokunulmaz.
