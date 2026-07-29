# Social Media V2 — Backend Independence Contract

Tarih: `2026-07-29`

## Sahiplik sınırı

- Runtime kodu, database migration, session, provider credential, media dosyası ve worker yalnız
  bu projeye aittir.
- `SocialMedia`, `Accumulate` ve `performance_marketing` yolu import/fallback olarak kullanılamaz.
- Canlı kaynak projelerin DB’sine bağlanılamaz; `socialmedia_adv` açıkça engellenir.
- Active production yalnız adı `social_media_v2` ile başlayan ayrı DB, secure cookie, güçlü SSO
  secretı ve explicit writes ayarıyla başlar.

## Provider ve veri

- Canonical platform seti `facebook|instagram|tiktok`.
- Meta ve TikTok OAuth tokenları V2 DB’de AES-256-GCM ile şifrelenir.
- Meta Graph ve TikTok Business API çağrıları yalnız ilgili collector açıkken yapılır.
- Collector bağlı hesapları yalnız V2 tablolarından seçer; metric/content/comment/media yazımları
  idempotenttir.
- TikTok pending connection normal schedule’a girmez. İlk doğrulama
  `python -m app.workers verify-tiktok --connection-id <ID>` ile tek bağlantıya uygulanır.
- Normal collection `python -m app.workers collect --platform all --scheduled` komutudur;
  PostgreSQL advisory lock çakışan çalışmayı engeller.
- Schedule ve her provider collector varsayılan olarak kapalıdır.

## Dağıtım sınırı

- API loopback `127.0.0.1:8026` üzerinde çalışır.
- Nginx V2 frontend build’ini servis eder ve yalnız V2 API’ye proxy yapar.
- V2 systemd unit/timer adları `social-media-v2-*` namespace’indedir.
- Kurulum veya rollback başka proje service/timer/process’ini durdurmaz veya yeniden başlatmaz.
