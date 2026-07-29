# Accumulate Ekibine Verilecek SSO Handoff

Social Media V2 frontend ve backend bağımsız sunucuda hazırlandı. Accumulate tarafında yapılması
gereken işlem yalnız şudur:

1. Sidebar’a `Social Media` linki ekleyin.
2. Kullanıcı linke bastığında mevcut app SSO sözleşmenizle `aud=social_media`,
   `app_id=social_media`, seçili Brand, rol ve erişim kapsamını içeren kısa ömürlü token üretin.
3. Kullanıcıyı
   `https://social.theaccumulate.com/sso/consume?token=<JWT>` adresine yönlendirin.
4. Parent/child Brand seçimi kullanılacaksa imzalı token içindeki optional `brand_scope` alanını
   [`contracts/social-media-v2-sso-provisioning.md`](contracts/social-media-v2-sso-provisioning.md)
   sözleşmesine göre gönderin.
5. Ortak SSO secretını iki tarafta secret yönetimiyle tanımlayın ve gerçek browser login/logout
   testi yapın.

Accumulate tarafında Social Media frontend’i gömülmeyecek; Meta/TikTok bağlantısı, dashboard,
DB, media, worker veya deploy kodu eklenmeyecek. V2 yalnız SSO’dan sonra kendi adresinde bağımsız
çalışacak.

## Kısa mesaj

> Social Media V2’nin frontend ve backend tarafı bağımsız sunucuda hazır. Senden beklenen,
> Accumulate sidebar’a Social Media linkini ekleyip mevcut SSO ile kullanıcıyı seçili Brand/rol
> bilgileriyle `https://social.theaccumulate.com/sso/consume` adresine yönlendirmen. Uygulama,
> provider bağlantıları ve veri toplama V2 tarafında çalışacak; Accumulate’a başka Social Media
> kodu veya servis eklenmeyecek. Bağlantı sonrası birlikte login/logout browser testi yapalım.
