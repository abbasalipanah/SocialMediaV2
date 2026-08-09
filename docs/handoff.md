# Social Media V2 — Güncel Handoff

Tarih: `2026-07-29`

## Değişmez kural

Yalnız `/home/api/colab_scripts/SocialMediadownstream` üzerinde çalışılır. Canlı
`SocialMedia`, `Accumulate` ve `performance_marketing` projelerine değişiklik, deploy, restart,
DB write veya timer müdahalesi yapılmaz.

## Güncel durum

- Accumulate webhook/authority-sync bağımlılığı yoktur; tek entegrasyon imzalı SSO’dur.
- SSO Brand kapsamı local session içinde doğrulanır ve V2’nin kendi DB’sine alınır.
- V2’ye ait ilk PostgreSQL migration ve idempotent migration komutu hazırdır.
- Facebook, Instagram ve TikTok dashboard/API/frontend yüzeyleri mevcuttur.
- Meta ve TikTok self-service OAuth credential’ları V2 vault’unda şifreli tutulur.
- V2’ye ait Meta/TikTok collector, media persistence, sync health ve schedule komutu hazırdır.
- TikTok ilk bağlantı doğrulaması normal schedule’dan ayrıdır.
- Güvenli `standalone_ready` production env, ayrı migration/API/collector/timer ve Nginx
  şablonları repository artifact'i olarak hazırdır; kurulmamış veya etkinleştirilmemiştir.
- Kaynak canlı projelerde hiçbir servis işlemi yapılmamıştır.

## Henüz yapılmayan dış işler

- V2 production DB/user/secret ve TLS sertifikasının operasyon ekibince oluşturulması.
- Meta/TikTok provider panelinde exact callback ve rotated secret doğrulaması.
- V2 deploy provası ve gerçek provider sandbox/canary testi.
- Accumulate ekibinin yalnız Social Media menü linki + SSO token üretimini bağlaması.
- Bu işlemlerden sonra browser E2E ve kontrollü worker schedule aktivasyonu.

Bu dış işler tamamlanmadan “canlı ve tamamlandı” denmez; kodun varsayılan provider/schedule
kapıları kapalı kalır.
