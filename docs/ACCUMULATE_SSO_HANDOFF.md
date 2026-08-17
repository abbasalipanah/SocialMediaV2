# Accumulate Ekibine Verilecek SSO Handoff

Durum: **DRAFT — GÖNDERİLMEDİ — READY GATE BEKLENİYOR**

Son güncelleme: `2026-08-17`

Bu handoff yalnız `READY_FOR_ACCUMULATE_SSO_HANDOFF=true` olduktan sonra Accumulate/Operations
ekibine iletilir. Şu an dış sisteme mesaj gönderme veya değişiklik talep etme yetkisi vermez.

Kapanan kapılar:

- V2 soak tamamlandı: `2026-08-13T11:16:36Z`–`2026-08-17T14:21:23Z` arasında `1.188` ardışık
  health/readiness/web turu, sıfır failed invocation;
- kabul testlerini geçen release'in kaynağı Git'e alındı ve commit edilmiş ağaç üzerinde
  `ruff`, `158 passed / 18 skipped`, frontend `47/47`, TypeScript ve production build yeniden geçti;
- Accumulate tarafında yapılacak değişiklik hazırlanmış ve flag kapalı olarak
  `feature/social-media-downstream-launch` branch'ine konmuştur. Aşağıdaki 1–3 numaralı maddeler
  bu branch'te uygulanmış durumdadır; Accumulate ekibinin işi branch'i gözden geçirip kendi change
  kaydıyla deploy etmek ve flag'i açmaktır.

Hâlâ açık olan kapılar:

- TikTok credential/provider ownership transferi final koordineli pencerede yapılmalıdır; mevcut
  iki TikTok access tokenı V2'nin refresh üretmeyen token-info preflight'ında reddedilmektedir;
- V1 collection pause sonrasında final freshness/parity yeniden koşmalıdır — `2026-08-13` parity
  kanıtı V1 toplamaya devam ettiği için bayattır;
- Operations'ın yetkili pencerede yapacağı V2-only restart ve gerçek-browser preflight'ı.

Kapsam kararı: bu cutover'da Accumulate `brand_scope` claim'i üretmeyecektir. V2 tek-Brand modunda
çalışacak; parent rollup ve hidden-parent deneyimi ayrı bir değişikliğe bırakılmıştır.

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
5. Bu cutover'da `brand_scope` göndermeyin. V2 tek-Brand modunda çalışacak ve kullanıcı Accumulate'ta
   seçili olan Brand kapsamına düşecektir. Parent/child rollup deneyimi istendiğinde imzalı token'a
   optional `brand_scope` alanı
   [`contracts/social-media-v2-sso-only.md`](contracts/social-media-v2-sso-only.md)
   sözleşmesine göre eklenir; V2 tüketen tarafı hazırdır.
6. Social Media Integrations erişimi verilecek bir read-only kullanıcı için workspace
   `role=viewer` değerini koruyun ve signed contract'a Brand üyeliğinden türetilmiş
   `app_role=admin|operator` ekleyin. Bu alan yoksa veya başka değerdeyse Integrations kapalıdır.
   Settings için app role kullanılmaz; yalnız `super_admin|agency_admin` workspace rolleri kabul
   edilir.
7. Final target'ı `https://social.theaccumulate.com` olarak tutun; geçici domain kullanmayın.
8. Değişikliği feature flag/internal cohort ile açın ve embedded V1 davranışına dönen rollback
   flag'ini aynı change içinde koruyun. Hazırlanan branch'te bu flag
   `SOCIAL_MEDIA_LAUNCH_SURFACE`'tır; `embedded_shell` varsayılanıyla deploy edilir, açmak ve geri
   almak yalnız backend restart gerektirir, frontend yeniden deploy edilmez.
9. Ortak SSO secretını iki tarafta secret yönetimiyle doğrulayın ve gerçek sidebar login/logout,
   Brand scope ve re-login testi yapın.

## Hazırlanan Accumulate branch'i

Yukarıdaki 1, 2 ve 8 numaralı maddeler `feature/social-media-downstream-launch` branch'inde
uygulanmıştır. Branch `main` (`a8f6e9d`) üzerine kuruludur, flag kapalı gelir ve çalışan Accumulate
ortamına dokunmaz. Ayrıntı, ön koşullar, doğrulama komutları ve rollback prosedürü branch içindeki
`docs/social-media-v2-downstream-cutover.md` dosyasındadır.

Branch ayrıca V1 emekliye ayrıldıktan sonra donmuş veri göstermemesi için Accumulate Home'daki
Social Media runtime KPI panellerini flag açıkken kaldırır ve embedded `analytics-*` route'ları ile
Social Media app settings workspace'ini bookmark/geçmiş erişimine karşı downstream launch paneline
düşürür.

Branch'i gözden geçirmek, kendi change kaydıyla deploy etmek ve flag'i açmak Accumulate ekibinin
kararıdır. V2 ekibi Accumulate'ın çalışan kod ağacına, servisine, env'ine veya DB'sine hiçbir
değişiklik yapmamıştır.

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
