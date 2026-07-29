# Social Media V2 Collector Parity Contract

Tarih: `2026-07-14`

Bu sözleşme collector davranışını tanımlar. Gerçek egress yalnız V2 provider/collection kapıları
açıldığında ve yalnız V2-owned DB/credential/media ile yapılır.

## Oracle ve izolasyon

- V1 oracle ve V2 candidate ayrı subprocess'lerde çalışır.
- HTTP parity oracle'ı, immutable `Accumulate` kaynağındaki gerçek `MetaGraphClient` modülünü
  read-only yükler. V2 candidate yalnız kendi `MetaTransport` implementasyonunu yükler.
- Persistence parity oracle'ı gerçek V1 `metrics_store` modülünü read-only yükler; V2 candidate
  yalnız yerel store ve collector servislerini kullanır.
- Oracle ve candidate aynı seed ile hazırlanmış iki ayrı disposable PostgreSQL database ve iki
  ayrı media root kullanır.
- Gerçek provider yerine localhost `ThreadingHTTPServer` tabanlı deterministic fake Meta server
  kullanılır. V2 canonical-host kontrolü gevşetilmez; test-only injected wire localhost fake'e
  forward eder.
- Clock ve timezone sabittir. Test tokenları yalnız disposable fixture değerleridir.

## Karşılaştırma kuralları

- Path, functional query parametreleri, cursor/pagination ve retry sırası exact karşılaştırılır.
- V1 query-token ile V2 Authorization-header tokenı secret material olarak comparison dışıdır;
  V2 tokenı URL'ye taşımaz. Bu güvenlik farkı request semantiği farkı sayılmaz.
- Metric ID/değer, collection status, summary JSON, content/comment/media satırları ve media
  SHA-256 çıktıları exact karşılaştırılır.
- Generated primary key ve created/updated timestamp karşılaştırmaya alınmaz.
- Missing veya unsupported metric `0` yapılmaz; persistence satırı üretilmez ve gerektiğinde
  `partial` status döner.
- Oracle source path'i hiçbir V2 runtime import graph'ına girmez; yalnız `backend/tests/parity`
  subprocess helper'larında bulunabilir.

## Facebook ve Instagram davranışı

- Facebook profil follower fallback sırası `followers_count`, sonra `fan_count` değeridir.
- Facebook daily insights metric başına deterministic sırada istenir ve V1 D+1 end-time
  alignment'ı korunur. Aynı canonical metric'e gelen ilk başarılı source kazanır.
- Instagram daily insights günlük `total_value` olarak normalize edilir.
- Profile, daily metrics, normal content, Instagram stories, comments ve audience breakdown'ları
  küçük capability reader'larına ayrıdır.
- Content sayfası tamamen idempotent yazılmadan checkpoint ilerlemez. Crash sonrası aynı sayfa
  replay edilir; duplicate satır oluşmaz.
- Media byte yazımı root-confined ve atomic'tir; rename failure destination veya partial file
  bırakmaz.
- 429/5xx retry bounded'dır; 70/85/92 pressure davranışı Faz 4 rate guard sözleşmesini korur.
- Token-invalid, object-inaccessible/story-expired, rate-limited ve generic failure statüleri
  secretsız canonical sınıflara çevrilir.

## Backfill, coverage ve runtime parity

- İlk backfill D-30..D-1 inclusive `30` gündür.
- Sonraki 90d aşaması D-90..D-31 inclusive kalan `60` gündür.
- Stale `running` iş `pending + worker_interrupted` olur; rate-limited iş bounded backoff ile
  `pending + rate_limited` olur.
- İlk follower snapshot sentetik düşüş üretmez; ilk change `0` olur ve history deterministik
  reconstruct edilir.
- D-1 coverage eksik account listesiyle non-zero, tam coverage ile zero exit üretir.
- Linked-account seçimi mevcutsa transition fallback kullanılmaz; geçiş tamamlandıktan sonra boş
  linked set eski listeye geri düşmez.
- Standalone collection 30 dakikalık timer için deklaratif systemd şablonu taşır; schedule env
  gate kapalıyken komut fail-closed olur. TikTok pending doğrulaması manual-only ayrı lock kullanır.
- Dirty-tree davranış eşlemesi
  `docs/fase5/v1_dirty_behavior_inventory.json` ile hash-bound tutulur.

## TikTok Business Accounts v1.3

TikTok net-new'dur; V1 parity kaynağı değildir.

- Request mapper yalnız canonical account-holder family, App ID, endpoint ve scope contract'ını
  kullanır; advertiser family disabled kalır.
- Ortak response envelope `code/message/request_id/data` şeklinde strict parse edilir.
- Token, refresh, revoke, token-info, profile ve public-video fixture'ları fail-closed'dur.
- Required scope eksikliği ve allowlist dışı scope bağlantıyı reddeder; optional scope explicit
  raporlanır.
- Callback URI byte-for-byte eşleşir; yalnız `auth_code + state` kabul edilir, `code` fallback'i
  yoktur.
- State signature, provider family, Brand, user, session ve expiry'ye bağlıdır. Consume,
  PostgreSQL atomic TTL claim ile tek kullanımlıdır.
- Unavailable metric `None` kalır; sahte KPI veya historical backfill üretilmez.

## Çıkış kapısı

Canonical fixture matrisi için:

- normalized request sequence farkı `0`;
- metric ID/değer farkı `0`;
- status/summary farkı `0`;
- DB content/comment/media farkı `0`;
- media file hash farkı `0`.

Bu gate production activation veya writer ownership cutover izni değildir.
