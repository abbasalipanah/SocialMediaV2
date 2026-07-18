# Faz 6 — Dashboard ve Operasyon API'leri Kapanış Raporu

Tarih: `2026-07-14`

Durum: **KAPALI — ÇIKIŞ KAPISI YEŞİL**

## Teslimatlar

- Overview, Facebook, Instagram ve TikTok typed dashboard query servisleri.
- Catalog-aware snapshot/flow/cumulative/ratio ve previous-period aggregation.
- Backend-only Parent Brand rollup, account scope kontrolü ve resolved-scope meta.
- Content, stories, audience breakdown, community ve freshness response'ları.
- Facebook/Instagram/TikTok account, Settings, connection, sync-job ve readiness query'leri.
- Stored insight query'si; GET üzerinde generation yok.
- Root-confined, size + SHA-256 doğrulamalı local Instagram media proxy.
- Same-origin ve merkezi write-policy arkasında fail-closed sync/backfill/disconnect commands.
- Typed OpenAPI component schema seti.
- Normatif contract: `docs/contracts/social-media-v2-dashboard-operations.md`.
- Live feature matrix: `docs/fase6/live_feature_matrix.json`.

## Güvenlik kararı

- Query route'ları provider egress, token refresh, filesystem write, DB mutation veya job enqueue
  yapmaz.
- Credential/token/source URL response DTO'larına girmez.
- Settings role string'iyle değil signed capability ile açılır.
- Audit store yokken sahte satır üretilmez; `honest_unavailable` feature durumu korunur.
- Production DB/provider/traffic/schedule kullanılmadı; Git push yapılmadı.

## Certification

Canonical komut:

```text
./scripts/quality/fase6_dashboard_operations_check.sh
```

`2026-07-14` canonical tur sonucu:

```text
Ruff: clean
tam disposable PostgreSQL suite: 115 passed, 0 skipped
hedefli Faz 6 + boundary/architecture/security suite: 19 passed, 0 skipped
secret leak guard: clean
canonical vocabulary guard: clean
source write guard: clean
sonuç: OK: Faz 6 dashboard and operations API certification passed.
```

DB yapılandırılmadan çalışan ilk katmanda `98 passed, 17 skipped` sonucu alınmıştır. Bu skip'ler
yalnız disposable PostgreSQL ve ayrı parity database isteyen testlerdir; final turda tamamı
çalışmış ve `115/115` geçmiştir.

Faz 6 kapanmıştır. Sıradaki çalışma Faz 7 responsive frontend shell'dir.
