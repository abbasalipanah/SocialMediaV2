# Social Media V2 — SSO-Only Contract v1

Tarih: `2026-07-29`

Durum: **NORMATİF**

Social Media V2 ile Accumulate arasındaki tek çalışma zamanı bağlantısı imzalı SSO tokenıdır.
Webhook, provisioning endpoint’i, outbox, ortak veritabanı, ortak dosya alanı veya kaynak kod
importu yoktur.

## Launch ve consume

Accumulate, kullanıcı Social Media menüsüne bastığında kısa ömürlü bir `HS256` JWT üretir ve
browser’ı aşağıdaki adrese yönlendirir:

```text
https://social.theaccumulate.com/sso/consume?token=<JWT>
```

Token üst alanları:

- `aud=social_media`
- `token_type=app_sso`
- `iss=accumulate`
- `sub=<user_id>`
- `exp`, tek kullanımlık `jti`
- `sso_contract`
- isteğe bağlı `launch_target=tiktok_owner_activation`; başka target kabul edilmez

`sso_contract` zorunlu alanları:

- `version=v1`, `issued_at`, `user_id`, `email`, `brand_id`
- `brand_status=active|suspended|archived`
- aynı değeri taşıyan `role`, `platform_role`, `effective_role`
- canonical role: `super_admin|agency_admin|agency_operator|viewer`
- `app_id=social_media`, `allowed_apps` içinde `social_media`
- `entitlement_status=enabled`
- `access_mode=read|write`
- nullable ISO-8601 `access_start_at`, `access_expires_at`
- boolean `is_internal_staff`, `settings_visible`
- `platform_branch_scope_mode=all`, string-list `platform_branches`

## Brand kapsamı

Tek Brand launch için yukarıdaki alanlar yeterlidir. Parent/child seçimi gereken kullanıcılar için
aynı imzalı contract içine şu optional alan eklenir:

```json
{
  "brand_scope": {
    "version": "v1",
    "default_brand_id": "10",
    "brands": [
      {
        "brand_id": "10",
        "name": "Main Brand",
        "parent_brand_id": null,
        "role": "agency_admin",
        "access_mode": "write"
      },
      {
        "brand_id": "11",
        "name": "Child Brand",
        "parent_brand_id": "10",
        "role": "viewer",
        "access_mode": "read"
      }
    ]
  }
}
```

Yalnız hiyerarşiyi göstermek için gerekli, doğrudan erişimi olmayan parent satırı `role:null` ve
`access_mode:null` taşır. Default Brand, üst contract’taki Brand/role/access değerleriyle aynı
olmalıdır. Tekrar eden ID, bilinmeyen parent veya cycle reddedilir.

## V2 local session

- SSO tokenı doğrulandıktan sonra V2 kendi `HttpOnly`, `SameSite=Lax`, production’da `Secure`
  session cookie’sini üretir.
- Raw cookie ve raw JTI veritabanına yazılmaz; yalnız SHA-256 hash saklanır.
- JTI tek kullanımlıdır. Replay reddedilir.
- Session ömrü JWT/access expiry ile en fazla 12 saatin minimumudur.
- Brand kapsamı imzalı SSO’dan V2 sessionına snapshot olarak alınır; sonrasında Accumulate API’sine
  authority sorgusu yapılmaz.
- Logout yalnız V2 sessionını iptal eder.

## Güvenlik ve operasyon

- Ortak `SOCIAL_SSO_HS256_SECRET` en az 32 byte olmalı ve Git dışında iki ortamın secret
  yönetiminden verilmelidir.
- `/sso/consume` response’u `303`, `Cache-Control:no-store` ve
  `Referrer-Policy:no-referrer` kullanır.
- Reverse proxy bu endpoint’in query stringini access log’a yazmamalıdır.
- Social Media V2’nin `/internal/provisioning/events` endpoint’i yoktur ve `404` döner.
- Accumulate yalnız link/token üretir; V2 DB migration, provider bağlantısı, worker veya deploy
  sorumluluğu taşımaz.
