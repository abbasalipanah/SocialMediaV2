# Accumulate Ekibine Verilecek SSO Handoff

Durum: **DRAFT — GÖNDERİLMEDİ — READY GATE BEKLENİYOR**

Bu handoff yalnız `READY_FOR_ACCUMULATE_SSO_HANDOFF=true` olduktan sonra Accumulate/Operations
ekibine iletilir. Şu an dış sisteme mesaj gönderme veya değişiklik talep etme yetkisi vermez.

Mevcut açık kapılar:

- 24 saat V2 soak `2026-08-14T11:16:36Z` öncesinde tamamlanamaz;
- TikTok credential/provider ownership transferi final koordineli pencerede yapılmalıdır;
- V1 collection pause sonrasında final freshness/parity yeniden koşmalıdır.

Social Media V2 frontend ve backend bağımsız runtime'da doğrulandıktan sonra Accumulate tarafında
yapılması gereken işlem yalnız şudur:

1. Mevcut `social_media` product launch profile'ını `embedded_shell` yerine şu değerlere alın:

   ```text
   launch_surface=downstream_sso
   launch_status=ready
   launch_app_id=social_media
   shell_owner=downstream
   runtime_owner=socialmedia_v2
   login_mode=accumulate_contract_only
   ```

2. Sidebar ve Home kartını mevcut generic downstream launcher'a bağlayın; embedded Overview,
   Facebook, Instagram ve TikTok child navigation'ını downstream flag açıkken göstermeyin.
3. Kullanıcı linke bastığında mevcut app SSO sözleşmenizle `aud=social_media`,
   `app_id=social_media`, seçili Brand, rol ve erişim kapsamını içeren kısa ömürlü token üretin.
4. Kullanıcıyı
   `https://social.theaccumulate.com/sso/consume?token=<JWT>` adresine yönlendirin.
5. Parent/child Brand seçimi kullanılacaksa imzalı token içindeki optional `brand_scope` alanını
   [`contracts/social-media-v2-sso-only.md`](contracts/social-media-v2-sso-only.md)
   sözleşmesine göre gönderin.
6. Social Media Integrations erişimi verilecek bir read-only kullanıcı için workspace
   `role=viewer` değerini koruyun ve signed contract'a Brand üyeliğinden türetilmiş
   `app_role=admin|operator` ekleyin. Bu alan yoksa veya başka değerdeyse Integrations kapalıdır.
   Settings için app role kullanılmaz; yalnız `super_admin|agency_admin` workspace rolleri kabul
   edilir.
7. Final target'ı `https://social.theaccumulate.com` olarak tutun; geçici domain kullanmayın.
8. Değişikliği feature flag/internal cohort ile açın ve embedded V1 davranışına dönen rollback
   flag'ini aynı change içinde koruyun.
9. Ortak SSO secretını iki tarafta secret yönetimiyle doğrulayın ve gerçek sidebar login/logout,
   Brand scope ve re-login testi yapın.

Accumulate tarafında Social Media frontend’i gömülmeyecek; Meta/TikTok bağlantısı, dashboard,
DB, media, worker veya deploy kodu eklenmeyecek. V2 yalnız SSO’dan sonra kendi adresinde bağımsız
çalışacak.

## Runtime gate sonrasında kullanılacak kısa mesaj taslağı

> Social Media V2 bağımsız runtime, DB, media ve credential vault üzerinde hazırlandı. Onaylı
> change window'da `social_media` launch profile'ını mevcut generic `downstream_sso` launcher'a
> geçirmeni, target olarak `https://social.theaccumulate.com` kullanmanı ve embedded Social Media
> child navigation'ını flag açıkken kapatmanı rica ediyoruz. Provider/data ownership V2'de kalacak;
> Accumulate'a Social Media runtime kodu eklenmeyecek. Önce internal cohort ile birlikte gerçek
> sidebar SSO, Brand scope, logout/re-login ve rollback testi yapacağız.
