# Social Media V2 — SSO ve Provisioning Contract v1

Tarih: `2026-07-13`

Durum: **NORMATİF — Faz 2**

## SSO consume

Canonical endpoint `GET /sso/consume?token=<JWT>` dış protokol nedeniyle
`protocol-command GET` olarak kayıtlıdır; normal query değildir. Başarı response'u query
tokenını temizleyen allowlist edilmiş bir path'e `303` döner. Bütün auth response'larında
`Cache-Control: no-store` ve `Referrer-Policy: no-referrer` uygulanır.

JWT yalnız `HS256` kabul eder. Top-level zorunlu claim'ler:

- `aud=social_media`, `token_type=app_sso`, `sub`, `exp`, `jti`;
- `iss` yok olabilir; varsa yalnız `accumulate`;
- optional signed `launch_target`: yoksa `/overview`, exact
  `tiktok_owner_activation` ise `/settings/tiktok/connect`; başka değer reddedilir;
- `sso_contract` object.

`sso_contract` exact v1 authority alanları:

- `version=v1`, `issued_at`, `user_id`, `email`, `brand_id`;
- `brand_status=active|suspended|archived`;
- `role`, `platform_role`, `effective_role`; üçü de aynı canonical role olmalıdır:
  `super_admin|agency_admin|agency_operator|viewer`;
- `app_id=social_media`, `allowed_apps` içinde `social_media`,
  `entitlement_status=enabled`;
- `access_mode`: active Brand ve write-capable role için `write`, diğer geçerli durumlarda
  `read`;
- nullable ISO-8601 `access_start_at` ve `access_expires_at`; geçerli zaman penceresinin
  dışında consume reddedilir;
- strict boolean `is_internal_staff` ve `settings_visible`; değerleri eşit olmalıdır;
- `platform_branch_scope_mode=all` ve string-list `platform_branches`.

`sub`, stringe çevrilmiş `sso_contract.user_id` ile aynı olmak zorundadır. Missing veya
unknown alan değeri sessiz normalize edilmez. `app_role` authorization kaynağı değildir.

Local session opaque 256-bit token kullanır. Browser yalnız raw cookie'yi görür;
PostgreSQL'de yalnız SHA-256 hash'i `v2:session:<hash>` key'iyle saklanır. Cookie `HttpOnly`,
`SameSite=Lax`, path `/`; production'da `Secure` zorunludur. TTL en fazla 12 saat, JWT expiry
ve access expiry değerlerinin minimumudur. JTI ve session aynı transaction içinde atomik
oluşturulur; `v2:sso-jti:<sha256>` tekrar kullanılamaz.

Session query `GET /api/auth/me`, same-origin revoke command `POST /api/auth/logout`
yüzeyindedir. User, membership, entitlement, Brand veya app access iptali ilgili session'ları
hemen revoke eder.

## Provisioning receiver

Canonical endpoint `POST /internal/provisioning/events`.

Zorunlu header'lar:

- `X-Accumulate-Timestamp`
- `X-Accumulate-Nonce`
- `X-Accumulate-Signature`

İmza girdisi UTF-8 olarak:

```text
METHOD
/canonical/path?sorted=query
unix_timestamp
nonce
sha256(raw_body)
```

HMAC-SHA256 64-character hex digest constant-time karşılaştırılır. Timestamp toleransı 300
saniye, nonce TTL 600 saniyedir. İmza raw body üzerinde JSON parse edilmeden önce doğrulanır.
Nonce `v2:hmac-nonce:<sha256>` key'iyle atomik claim edilir. TTL içindeki nonce replay
`409 nonce_replayed` olur.

Event envelope:

```json
{
  "event_id": "opaque-id",
  "event_type": "brand.upserted",
  "app_id": "social_media",
  "entity_id": "authority-id",
  "version": 1,
  "payload": {"status": "active"}
}
```

`app_id` transition süresince yok olabilir; varsa yalnız `social_media` kabul edilir.
`event_id`, `entity_id`, non-negative integer `version` ve object `payload` zorunludur.

Desteklenen exact event seti ve parser davranışı:

| Event | Normalized projection/revoke davranışı |
|---|---|
| `brand.upserted` | `status`, `brand_status`, `after.status` veya `brand.status`; active/inactive projection |
| `brand.deleted` | inactive Brand projection; Brand session revoke |
| `entitlement.updated` | `status`, `after.status` veya `entitlement.status`; inactive ise Brand session revoke |
| `brand.app_access.changed` | `active`, `projection_status` veya `status`; inactive ise Brand session revoke |
| `membership.upserted` | canonical role, `user_id`, `brand_id`, `is_active/status`; inactive ise exact user+Brand session revoke |
| `brand_access.sync` | canonical `user`, zorunlu `brands` listesi; boş liste geçerli full snapshot ve user session revoke |
| `user.deleted` | inactive user projection; bütün user session'larını revoke |

Status parser yalnız açık şekilleri okur. Membership ve snapshot user role'ları canonical exact
set ile doğrulanır; legacy role alias'ı kabul edilmez. Snapshot Brand entry'sinde role varsa aynı
set uygulanır. Boş `brands` listesi eski erişimleri kapatan geçerli snapshot'tır; tam family
projection uygulaması Faz 3'e aittir.

Event ID `v2:event:<event_id>` ile atomik claim edilir. Aynı event yeni nonce ile tekrar gelirse
`200 duplicate_ignored`; daha düşük/eşit entity version `200 stale_ignored`; yeni version
`200 applied` döner. Unknown event `422` ile reddedilir ve processed sayılmaz.

## Persistence ve güvenlik sınırı

İlk adapter yalnız disposable PostgreSQL'deki schema-compatible `social_projection_state`
tablosunu kullanır. `create_all`, Alembic veya production schema inspection çalıştırmaz. Typed
payload mevcut `payload_json` kolonuna yazılır; session/JTI/nonce expiry değeri yeni kolon veya
DDL eklenmeden payload içindeki ISO-8601 `expires_at` alanında tutulur. `projection_key`
`varchar(255)` sınırı event ve entity key'leri persistence çağrısından önce fail-closed doğrulanır.
Unique key claim'i ve projection update tek transaction içindedir. Session ve replay
anahtarlarında raw token/JTI/nonce değil SHA-256 digest tutulur.

Secretlar yalnız `SOCIAL_SSO_HS256_SECRET` ve `SOCIAL_PROVISIONING_HMAC_SECRET` environment
injection ile gelir. `.env.example` değerleri boştur. Production-benzeri bootstrap bu secretları
ve DB bağlantısını Faz 2'de reddeder. Log, response, fixture veya repository içinde raw JWT,
cookie veya HMAC secretı bulunmaz.

Mevcut Accumulate SSO v1'in nested `sso_contract` yapısı bu belgenin doğruladığı upstream
şekildir. Signed `launch_target` ile provisioning envelope `entity_id/version` alanlarının
üretimi, master plandaki ayrı final Accumulate cutover paketinin parçasıdır; kaynak repository
bu fazda değiştirilmez.
