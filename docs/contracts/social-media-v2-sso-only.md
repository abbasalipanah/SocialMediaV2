# Social Media V2 — SSO-Only Contract v1

Tarih: `2026-08-09`

Durum: **NORMATİF — HANDOFF İÇİN HENÜZ AKTİF DEĞİL**

Social Media V2 ile Accumulate arasındaki tek runtime bağlantısı imzalı SSO launch tokenıdır.
Webhook, provisioning endpoint'i, HMAC event ingress'i, inbox/outbox, ortak veritabanı, ortak
dosya alanı, process, proxy veya kaynak kod importu yoktur.

## Launch ve consume

Accumulate, kullanıcı Social Media menüsüne bastığında kısa ömürlü bir `HS256` JWT üretir ve
browser'ı aşağıdaki adrese yönlendirir:

```text
https://social.theaccumulate.com/sso/consume?token=<JWT>
```

Token üst alanları:

- `aud=social_media`
- `token_type=app_sso`
- `iss=accumulate`; mevcut SSO v1 issuer üretmiyorsa absence geçici olarak kabul edilir
- `sub=<user_id>`
- `exp`, tek kullanımlık `jti`
- `sso_contract`
- isteğe bağlı `launch_target=tiktok_owner_activation`; başka target kabul edilmez

Normal launch `/settings`, owner launch `/settings/tiktok/connect` allowlisted yoluna 303 ile
çözülür. Arbitrary path, absolute URL ve browser-provided `return_to` kabul edilmez.

`sso_contract` zorunlu alanları:

- `version=v1`, `issued_at`, `user_id`, `email`, `brand_id`
- `brand_status=active|suspended|archived`
- aynı workspace değerini taşıyan `role`, `platform_role`; `effective_role` workspace rolü veya
  varsa app-specific rol olabilir
- canonical role: `super_admin|agency_admin|agency_operator|viewer`
- optional normalized `app_role`; Integrations için kullanılan değerler `admin|operator`
- `app_id=social_media`, `allowed_apps` içinde `social_media`
- `entitlement_status=enabled`
- `access_mode=read|write`
- nullable ISO-8601 `access_start_at`, `access_expires_at`
- boolean `is_internal_staff`, `settings_visible`
- `platform_branch_scope_mode=all`, string-list `platform_branches`

## Brand kapsamı

Tek Brand launch için üst contract yeterlidir. Parent/child deneyimi gereken kullanıcılar aynı
imzalı contract içinde optional `brand_scope` taşır:

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
`access_mode:null` taşır. Default Brand üst contract'taki Brand/role/access değerleriyle aynı
olmalıdır. Tekrar eden ID, bilinmeyen parent, cycle ve claim dışı Brand seçimi reddedilir. Claim
yoksa V2 tek-Brand modunda çalışır; Accumulate API'sine veya başka authority kaynağına fallback
yapmaz.

## V2 local session

- SSO tokenı doğrulandıktan sonra V2 kendi `HttpOnly`, `SameSite=Lax`, production/staging'de
  `Secure` session cookie'sini üretir.
- Raw SSO tokenı, raw cookie ve raw JTI kalıcı saklanmaz; yalnız SHA-256 hash kullanılır.
- JTI tek kullanımlıdır; replay atomik olarak reddedilir.
- Session ömrü JWT expiry, access expiry ve 12 saatin minimumudur.
- Brand kapsamı local session'a immutable signed-claim snapshot'ı olarak alınır.
- Settings authority signed `settings_visible` boolean'ından türetilmez: yalnız canonical
  `super_admin|agency_admin` workspace rolleri Settings açabilir. Legacy boolean biçimsel olarak
  doğrulanır, fakat rol kararını genişletemez.
- Integrations authority `super_admin|agency_admin` için doğrudan; yalnız Accumulate kaynaklı
  `viewer` + signed `app_role=admin|operator` için exact session Brand kapsamında verilir.
- Viewer/Operator Integrations erişimi `/api/settings/*` erişimi kazandırmaz.
- Logout same-origin kontrolüyle yalnız V2 sessionını revoke eder ve cookie'yi siler.
- Session expiry veya revocation sonrası fresh Accumulate SSO zorunludur.

## Güvenlik ve operasyon

- `SOCIAL_SSO_HS256_SECRET` en az 32 byte olmalı ve Git dışında iki ortamın secret yönetiminden
  verilmelidir.
- `/sso/consume` response'u `303`, `Cache-Control:no-store` ve
  `Referrer-Policy:no-referrer` kullanır.
- Reverse proxy consume query stringini access log'a yazmamalıdır.
- `/internal/provisioning/events` veya başka authority mutation endpoint'i yoktur ve `404` döner.
- Accumulate yalnız link/token üretir; V2 DB migration, provider bağlantısı, worker, media veya
  deploy sorumluluğu taşımaz.
- V2 `STANDALONE_RUNTIME_COMPLETE` olmadan bu sözleşme Accumulate'a uygulama talebi olarak
  gönderilmez. Canlı browser testi geçmeden `SSO_LIVE_VERIFIED` verilmez.
