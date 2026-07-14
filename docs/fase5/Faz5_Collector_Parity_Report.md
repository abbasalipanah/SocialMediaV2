# Faz 5 — Collector Parity Kapanış Raporu

Tarih: `2026-07-14`

Durum: **KAPALI — ÇIKIŞ KAPISI YEŞİL**

## Tamamlanan teslimatlar

- Deterministic localhost fake Meta HTTP server ve golden fixture matrisi.
- Gerçek V1 HTTP transport ve persistence modüllerini read-only yükleyen ayrı oracle
  subprocess'leri; ayrı V2 candidate subprocess'leri.
- Aynı seed'li ayrı oracle/candidate PostgreSQL database ve media root differential suite.
- Facebook/Instagram profile, daily metrics, content, comments ve audience reader'ları;
  Instagram story dilimi.
- Exact pagination ve `500 → 429 → 200` retry sequence parity.
- Metric/content/comment/media satırları, summary JSON ve media SHA-256 exact differential.
- Catalog'a eklenen V1 daily metric ID/semantikleri ve missing-is-not-zero kuralı.
- Page-at-a-time durable checkpoint, crash/replay ve atomic media failure testleri.
- D-1 coverage, rolling refresh, 30d + kalan 60d backfill, stale job, rate defer,
  linked-account geçişi ve ilk follower history reconstruction sözleşmeleri.
- Dirty-tree hash + davranış karşılık envanteri.
- TikTok Business Accounts v1.3 token/refresh/revoke/token-info/profile/video fixture paketi.
- TikTok required/optional/forbidden scope, exact callback, no-code-fallback,
  provider-family mismatch ve durable PostgreSQL state replay testleri.
- Normatif contract: `docs/contracts/social-media-v2-collector-parity.md`.

## Differential sonucu

Canonical fixture matrisi için:

```text
normalized request sequence difference: 0
metric ID/value difference: 0
status/summary difference: 0
content/comment/media row difference: 0
media SHA-256 difference: 0
```

Yalnız generated primary key/created timestamp ve secret taşıma biçimi comparison dışıdır.
V1 query-token davranışı V2'ye taşınmadı; V2 tokenı Authorization header'ında tutar ve URL'ye
yazmaz.

## Dirty behavior kararı

SocialMedia source state'i değiştirilmedi. Baseline'daki `10` dirty dosya ve
`ec9c8c6c...72f6` tracked-diff kaydı raw patch olarak kopyalanmadı. Davranışlar V2 saf domain,
collector ve persistence sınırlarına taşındı; tam kayıt
`docs/fase5/v1_dirty_behavior_inventory.json` içindedir.

## Certification

Canonical komut:

```text
./scripts/quality/fase5_collector_parity_check.sh
```

`2026-07-14` canonical tur sonucu:

```text
Ruff: clean
tam disposable PostgreSQL suite: 108 passed, 0 skipped
hedefli Faz 5 + architecture/security suite: 35 passed, 0 skipped
secret leak guard: clean
canonical vocabulary guard: clean
source write guard: clean
sonuç: OK: Faz 5 collector parity certification passed.
```

Sertifikasyonun iç içe çağırdığı önceki faz kapıları da yeniden yeşil geçti. PostgreSQL URL'leri
verilmeden çalışan ilk bootstrap katmanındaki `15 skipped`, yalnız sonraki disposable PostgreSQL
katmanında çalıştırılan testlerdir; final turda Faz 5 differential dahil `108/108` test
çalışmıştır.

## Güvenlik ve aktivasyon durumu

- Production DB, gerçek Meta/TikTok provider, gerçek token, traffic veya production data
  kullanılmadı.
- V2 automated schedule hâlâ yoktur; dormant/write/egress gate'leri değişmedi.
- Source project'ler read-only kaldı ve final source guard ile doğrulanacaktır.
- Git push yapılmadı.

Faz 5 kapanmıştır. Sıradaki çalışma Faz 6 dashboard ve operasyon API'leridir.
