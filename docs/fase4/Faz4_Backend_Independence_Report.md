# Faz 4 — Backend Bağımsızlaştırma Kapanış Raporu

Tarih: `2026-07-14`

Durum: **KAPALI — ÇIKIŞ KAPISI YEŞİL**

## Tamamlanan teslimatlar

- Küçük Profile, Content, Comments ve Audience platform portları.
- Facebook/Instagram/TikTok exact capability registry; bootstrap'ta sahte `available` yok.
- TikTok Business Accounts v1.3 exact account-holder wire mapper; App ID/endpoint/scope
  doğrulaması ve disabled advertiser sınırı.
- Versioned metric semantic catalog; snapshot/flow/cumulative/ratio, derived operator,
  first-sample/reset ve zero-denominator kuralları.
- Catalog zorunlu metric query ve persistence girişi.
- Local explicit SQLAlchemy model registry; source-project dynamic model yükleme yok.
- Schema-compatible metric/content/comment/media PostgreSQL store'ları; idempotent upsert,
  query side-effect yasağı ve account–Brand–platform scope doğrulaması.
- Consume-only legacy platform normalization; raw değer output/log'a çıkmaz.
- `TokenVault` ve `CredentialStore` portları ile AES-256-GCM projection-state adapterı.
- 96-bit random nonce, transaction-bound atomic nonce claim, canonical length-prefixed AAD,
  revoke, expiry, key rotation dry-run/real update ve rollback davranışı.
- Typed `CheckpointStore`; optimistic version ve concurrent TTL idempotency claim.
- Default-off Meta transport, bounded retry ve 70/85/92 usage pressure rate guard.
- Dormant-by-default worker runtime; automated production schedule yok.
- Repository secret leak guard ve genişletilmiş source/built-artifact vocabulary guard.
- Normatif contract:
  `docs/contracts/social-media-v2-backend-independence.md`.

## Bağımlılık kararı

Custom crypto yazılmadı. Standard AEAD implementasyonu için `cryptography>=45,<47` runtime
dependency'si manifest ve hash'li runtime/development lock dosyalarına eklendi. İlk adapter
doğrudan AES-256-GCM kullanır; KMS/envelope veya dedicated credential tablosu eklenmedi.

## Certification

Canonical komut:

```text
./scripts/quality/fase4_backend_independence_check.sh
```

Sonuç:

```text
Source guard: pass (zincir başlangıcı, faz geçişleri ve final)
Faz 1 certification: pass
Faz 2 disposable PostgreSQL full suite: 83 passed
Faz 3 target suite: 20 passed
Faz 4 disposable PostgreSQL full suite: 83 passed
Faz 4 target architecture/security/persistence suite: 44 passed
Ruff: clean
Python wheel: built
Frontend production build: pass
Canonical vocabulary source/wheel/frontend artifact scan: clean
Repository secret leak guard: clean
OK: Faz 4 backend independence certification passed.
```

Test PostgreSQL containerları random localhost portlarında oluşturuldu ve her sertifikasyon
turunun sonunda silindi. Meta transport testleri injected fake transport kullandı. Production
DB, gerçek provider, gerçek token, traffic, worker veya schedule kullanılmadı.

## Çıkış kapısı

- Runtime source-project import/path bağımlılığı yok.
- Provider adapter dosyaları küçük ve capability-specific kaldı.
- Catalog dışı metric literal/query/persistence build'i durdurur.
- Query package mutation çağrısı içermez.
- Schema identifier'lar yalnız compatibility adapter sınırındadır.
- Dormant runtime provider egress veya automated schedule başlatamaz.

Faz 4 çıkış kapısı kapanmıştır. Sıradaki çalışma Faz 5 collector parity: fake Meta server,
golden fixture'lar, V1-vs-V2 differential suite ve TikTok fixture sözleşmeleridir.
