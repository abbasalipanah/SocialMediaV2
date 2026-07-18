# Faz 3 — Parent/Child Authority Projection Kapanış Raporu

Tarih: `2026-07-14`

Durum: **KAPALI — ÇIKIŞ KAPISI YEŞİL**

## Teslimatlar

- `brand.upserted`, delete, entitlement, app-access, membership, snapshot ve user-delete
  event'leri canonical projection namespace'ine bağlandı.
- Full `brand_access.sync` snapshot; event/version gate, Brand shell upsert, access replacement ve
  eksilen access satırlarının inactive yapılmasını tek PostgreSQL transaction'ında uygular.
- Snapshot'taki user–Brand access `full_snapshot`, incremental membership access'i `membership`
  authority source'u ile ayrılır.
- Membership tek başına erişim açamaz; exact entitlement ve app-access projection'ları active
  değilse fail-closed olur.
- Erişimli child için eksik parent insert-only hidden shell olarak oluşturulur; mevcut gerçek
  parent shell placeholder veriyle overwrite edilemez.
- Backend family resolver unrelated Brand/sibling verisini scope'a almaz ve hierarchy cycle'ı
  fail-closed reddeder.
- Hidden parent doğrudan Brand data veya mutation erişimi taşımaz; yalnız izinli descendant'lar
  için `rollup=true` shell'idir.
- Concrete mutation scope'u write access ister; read-only Brand ve rollup mutation reddedilir.
- `GET /api/workspace/brands` Brand listesi, family, visibility ve backend-resolved scope döndürür.
- `GET /api/auth/me` mevcut session user/Brand'ini güncel projection'a karşı side-effect
  üretmeden doğrular.
- Access/app/entitlement/Brand/user revoke event'leri ilgili session'ları anında düşürür; full
  snapshot apply edildiğinde user session'ları rotate edilmek üzere revoke edilir.
- Normatif contract:
  `docs/contracts/social-media-v2-authority-projection.md`.

## Persistence sözleşmesi

Yeni tablo veya DDL eklenmedi. Bütün satırlar mevcut
`social_projection_state.payload_json` ve `projection_key varchar(255)` sözleşmesini kullanır.
Atomic replacement stale/equal snapshot'ın güncel access satırlarını geri almasına izin vermez.

## Certification

Canonical komut:

```text
./scripts/quality/fase3_authority_check.sh
```

Sonuç:

```text
Source guard: pass (başlangıç/final)
Faz 1 certification: pass
Faz 2 certification: pass
Ruff: clean
Backend + disposable PostgreSQL: 44 passed
Authority/cross-brand/PostgreSQL target suite: 20 passed
Python wheel: built
Frontend clean production build: pass
Canonical vocabulary source/artifact scan: clean
OK: Faz 3 authority projection certification passed.
```

Production DB, provider, secret, worker, schedule veya source-project write işlemi yapılmadı.

## Çıkış kapısı

- Parent rollup yalnız kullanıcının izinli active child Brand'lerini içerir.
- Arbitrary cross-brand query ve mutation scope'u reddedilir.
- Access revoke session'ı anında düşürür.
- Empty/full snapshot ve stale version davranışları disposable PostgreSQL üzerinde doğrulandı.

Faz 3 çıkış kapısı kapanmıştır. Faz 4 backend bağımsızlaştırma çalışması başlatılabilir.
