# Social Media V2 — Güncel Handoff

Tarih: `2026-08-09`

## Değişmez kural

Yalnız `/home/api/colab_scripts/SocialMediadownstream` üzerinde çalışılır. Canlı
`SocialMedia`, `Accumulate` ve `performance_marketing` projelerine değişiklik, deploy, restart,
DB write veya timer müdahalesi yapılmaz.

## Güncel durum

- Accumulate webhook/authority-sync bağımlılığı yoktur; tek entegrasyon imzalı SSO’dur.
- SSO Brand kapsamı local session içinde doğrulanır ve V2’nin kendi DB’sine alınır.
- V2’ye ait ilk PostgreSQL migration ve idempotent migration komutu hazırdır.
- Facebook, Instagram ve TikTok dashboard/API/frontend yüzeyleri mevcuttur.
- `/` Home ve gizli `/overview` deep-link aynı executive Overview'u açar; sidebar'da ayrı
  Overview bağlantısı yoktur. Overview altı KPI, What Changed, Channel Health, dört modlu
  Performance Trend, Content Snapshot, Top Performing Content, AI Summary
  ve üç platform summary kartını gerçek V2 verisiyle gösterir.
- Pine Beach Belek V2-local snapshot'ı 80.519 metric, 395 content, 611 comment, 389 doğrulanmış
  media ve bir completed AI Summary içerir. Bu kaydın yalnız non-secret structured output alanları
  V2-local DB'ye alınmıştır; raw metric snapshot/provider configuration/secret kopyalanmamış ve
  kaynak PostgreSQL read-only kalmıştır.
- Önceki AI Summary'ler Brand kapsamında okunur. Yeni üretim yalnız Accumulate exact `viewer` +
  signed `app_role=operator`, exact session Brand ve non-rollup scope için açıktır. Brand başına
  rolling 7x24 saatte bir başarılı özet hakkı backend transaction lock ile uygulanır; failed
  deneme hakkı tüketmez.
- V2 AI provider ayarı bağımsızdır ve default kapalıdır. V2'ye ait ayrı provider anahtarı
  verilmeden yeni üretim unavailable kalır; korunan projelerden secret alınmaz.
- Meta ve TikTok self-service OAuth credential’ları V2 vault’unda şifreli tutulur.
- V2’ye ait Meta/TikTok collector, media persistence, sync health ve schedule komutu hazırdır.
- TikTok ilk bağlantı doğrulaması normal schedule’dan ayrıdır.
- Güvenli `standalone_ready` production env, ayrı migration/API/collector/timer ve Nginx
  şablonları repository artifact'i olarak hazırdır; kurulmamış veya etkinleştirilmemiştir.
- Kaynak canlı projelerde hiçbir servis işlemi yapılmamıştır.
- Son Overview/AI Summary kararı ve test kanıtları `docs/revision6/r14/` ve
  `docs/revision6/r15/` altındadır; bağlayıcı yapı
  `docs/revision6/overrides/overview_surface_2026-08-09.json` içindedir.

## Henüz yapılmayan dış işler

- V2 production DB/user/secret ve TLS sertifikasının operasyon ekibince oluşturulması.
- Meta/TikTok provider panelinde exact callback ve rotated secret doğrulaması.
- V2 deploy provası ve gerçek provider sandbox/canary testi.
- Accumulate ekibinin yalnız Social Media menü linki + SSO token üretimini bağlaması.
- Bu işlemlerden sonra browser E2E ve kontrollü worker schedule aktivasyonu.

Bu dış işler tamamlanmadan “canlı ve tamamlandı” denmez; kodun varsayılan provider/schedule
kapıları kapalı kalır.
