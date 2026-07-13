# Social Media V2 — SSO + Webhook Sözleşmesi (V1 Faz 2 Taslak)

**Amaç:** Accumulate tarafındaki brand yetkilendirme ve oturum/kimlik akışını SocialMediaV2'de standartlaştırmak.

Bu belge yalnızca taslak sözleşme niteliğindedir; Faz 2 testleriyle birlikte güncellenecektir.

## 1) SSO callback (kurulum)

- HTTP method: `POST`
- Endpoint: `POST /auth/callback`
- Content-Type: `application/json`
- Gerekli alanlar:
  - `provider`: `"accumulate"` (string)
  - `event`: `"authorize"` (string)
  - `state`: tek seferlik nonce/korumalı token (string)
  - `session_token` veya eşdeğeri (string)
  - `account_bundle`: array/object brand projection için
    - `brand_id` (uuid/string)
    - `parent_brand_id` (uuid/string, opsiyonel)
    - `hidden_parent_brand_id` (uuid/string, opsiyonel)
    - `platform_accounts`: platform bilgisi listesi
      - `platform`: `facebook|instagram|tiktok`
      - `account_id`, `display_name`

## 2) Replay ve idempotency

- `state` değeri:
  - Tekrar kullanımda (`JTI`) yalnızca ilk işleme izin verir.
  - Aynı payload ile tekrar geldiğinde yanıt `200`/`ok` ve aynı projection anahtarı döndürülür.
- Başarısız doğrulamalarda:
  - `401` => kimlik doğrulama hatası (hatalı imza/nonce)
  - `409` => `state` collision / duplicate ama farklı içerik

## 3) Webhook doğrulama

- Header:
  - `X-Signature` veya karşılığı (şimdilik proje parametreleriyle belirlenir)
- Payload doğrulama:
  - Canonical JSON karşılaştırması
  - Zaman penceresi ve nonce kontrolü
- Event tipi beklenen minimal set:
  - `brand_connected`
  - `brand_revoked`
  - `brand_updated`

## 4) Provisioning projection

- Hedef domain:
  - `Brand`
  - `PlatformAccount`
  - `AuthorityProjection`
- Davranış:
  - `child_brand` -> `parent_brand_id` ile erişim zinciri çözümlenir.
  - `hidden_parent_brand_id` ile gizli yetkilendirme davranışı desteklenir (okuma için).
- Sadece `brand` terminolojisi kullanılır; `client`/`ars`/`media planner` kullanılmamalıdır.

## 5) Test hedefleri

- İmza doğrulama testi
- `state` replay testi
- İmzalı/eksik alan testleri
- Parent-child projection idempotency testi
