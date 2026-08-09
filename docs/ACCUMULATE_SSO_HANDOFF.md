# Accumulate Ekibine Verilecek SSO Handoff

Durum: **DRAFT — GÖNDERİLMEDİ**

Bu handoff yalnız `STANDALONE_RUNTIME_COMPLETE` sonrasında Accumulate/Operations ekibine
iletilir. Şu an dış sisteme mesaj gönderme veya değişiklik talep etme yetkisi vermez.

Social Media V2 frontend ve backend bağımsız runtime'da doğrulandıktan sonra Accumulate tarafında
yapılması gereken işlem yalnız şudur:

1. Sidebar’a `Social Media` linki ekleyin.
2. Kullanıcı linke bastığında mevcut app SSO sözleşmenizle `aud=social_media`,
   `app_id=social_media`, seçili Brand, rol ve erişim kapsamını içeren kısa ömürlü token üretin.
3. Kullanıcıyı
   `https://social.theaccumulate.com/sso/consume?token=<JWT>` adresine yönlendirin.
4. Parent/child Brand seçimi kullanılacaksa imzalı token içindeki optional `brand_scope` alanını
   [`contracts/social-media-v2-sso-only.md`](contracts/social-media-v2-sso-only.md)
   sözleşmesine göre gönderin.
5. Social Media Integrations erişimi verilecek bir read-only kullanıcı için workspace
   `role=viewer` değerini koruyun ve signed contract'a Brand üyeliğinden türetilmiş
   `app_role=admin|operator` ekleyin. Bu alan yoksa veya başka değerdeyse Integrations kapalıdır.
   Settings için app role kullanılmaz; yalnız `super_admin|agency_admin` workspace rolleri kabul
   edilir.
6. Ortak SSO secretını iki tarafta secret yönetimiyle tanımlayın ve gerçek browser login/logout
   testi yapın.

Accumulate tarafında Social Media frontend’i gömülmeyecek; Meta/TikTok bağlantısı, dashboard,
DB, media, worker veya deploy kodu eklenmeyecek. V2 yalnız SSO’dan sonra kendi adresinde bağımsız
çalışacak.

## Runtime gate sonrasında kullanılacak kısa mesaj taslağı

> Social Media V2’nin frontend ve backend tarafı bağımsız staging runtime'da doğrulandı. Senden beklenen,
> Accumulate sidebar’a Social Media linkini ekleyip mevcut SSO ile kullanıcıyı seçili Brand/rol
> bilgileriyle `https://social.theaccumulate.com/sso/consume` adresine yönlendirmen. Uygulama,
> provider bağlantıları ve veri toplama V2 tarafında çalışacak; Accumulate’a başka Social Media
> kodu veya servis eklenmeyecek. Bağlantı sonrası birlikte login/logout browser testi yapalım.
