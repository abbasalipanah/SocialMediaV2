# Social Media V2 — Paralel Pre-production ve Kesintisiz Geçiş Planı

Tarih: `2026-08-13`

Durum: **PUBLIC V2/ACCUMULATE GEÇİŞİ KISMİ — COLLECTION KAPALI — COLLECTOR TARGET DÜZELTMESİ GEREKİYOR**

Son güncelleme: `2026-08-18`

> Bu belgenin Faz A–G sırası ilk güvenli cutover planını korur. `2026-08-18` tarihinde public
> routing ve Accumulate downstream deploy'u bazı final provider/collection kapılarından önce
> uygulanmıştır. Gerçek post-deploy durum, sapmalar ve bundan sonraki bağlayıcı sıra §21–§22'de
> kayıt altındadır.

## 1. Amaç

Social Media V2, mevcut Social Media V1 ve Accumulate çalışmaya devam ederken tamamen bağımsız
bir ortamda hazırlanacak, güncel üretim verisiyle doğrulanacak ve gerçek provider toplama
işlerini yapabilir duruma getirilecektir. V2 bütün çıkış kapılarını geçmeden:

- Accumulate repository'si, servisi, sidebar davranışı veya app target ayarı değiştirilmez;
- canlı V1 Nginx route'u, API servisi, DB'si, media alanı veya timer'ları değiştirilmez;
- `social.theaccumulate.com` V2'ye yönlendirilmez;
- V1 kullanıcı trafiği veya veri toplama işleri durdurulmaz.

V2 hazır olduktan sonra Accumulate ekibine ayrı bir handoff verilecek; son bağlantı iki ekibin
kontrollü aktivasyonuyla yapılacaktır.

## 2. Bağlayıcı kararlar

1. Geçici public domain kullanılmayacaktır.
2. V2 pre-production web erişimi `127.0.0.1:3026`, API erişimi `127.0.0.1:8026` üzerinde kalır.
3. Portlar yalnız loopback'e bind edilir; doğrudan `0.0.0.0` veya public firewall açılımı yapılmaz.
4. İnsan tarafından browser testi gerekiyorsa SSH port forwarding kullanılır:

   ```bash
   ssh -L 3026:127.0.0.1:3026 <server>
   ```

   Ardından yerel browser'da `http://127.0.0.1:3026` açılır.
5. Nihai public origin yalnız `https://social.theaccumulate.com` olacaktır.
6. V1, V2 hazırlığı ve kabul testleri boyunca canlı kalır.
7. Accumulate değişikliği yalnız `READY_FOR_ACCUMULATE_SSO_HANDOFF=true` sonrasında kendi ekibi
   tarafından yapılır.
8. V2 runtime hiçbir zaman V1 DB'yi kendi canlı persistence alanı olarak kullanmaz.
9. V1'den V2'ye veri alma işlemleri yalnız repeatable-read, transaction-read-only migration
   komutlarıdır; kalıcı runtime bağımlılığı değildir.
10. Secret, token, DB URL veya cookie terminal, doküman, Git, test artifact'i ya da access log'a
    yazılmaz.
11. Yeni Meta veya TikTok developer app oluşturulmayacaktır. Mevcut onaylı provider app
    kimlikleri, scope'ları, callback'leri ve secret'ları kontrollü cutover ile V2 operasyonel
    sahipliğine geçirilecektir.
12. Aynı provider token ailesini kullanan V1 ve V2 collector'ları uzun süre paralel schedule
    edilmez. V1 kullanıcı yüzeyi canlı kalırken V2 yalnız refresh üretmeyeceği doğrulanmış bounded
    canary veya fake/sandbox provider provası çalıştırır.
13. V1 kullanıcı trafiği, Accumulate V2'ye yönlenip gerçek browser smoke testi geçene kadar devam
    eder. Başarılı aktivasyondan sonra V1 trafik ve collection sahipliği kaldırılır; DB/media/release
    rollback ve audit için korunur.

## 3. `shadow` / candidate DB açıklaması

`shadow` bir trafik modu veya V1 ile ortak çalışan DB anlamına gelmez. Import aracındaki güvenlik
sınırıdır:

- kaynak DB'nin exact `socialmedia_adv` olduğu doğrulanır;
- kaynak transaction `REPEATABLE READ` ve `READ ONLY` olmadan devam edilmez;
- hedef DB'nin V2'ye ait, farklı ve tamamen boş olması zorunludur;
- migration seti exact doğrulanır;
- V1'e DDL, DML, migration, cleanup veya credential write yapılamaz.

Operasyonel adı **V2 candidate/pre-production DB** olacaktır. Teknik adın
`social_media_v2_shadow_<timestamp>` olması güvenlik guard'ını korur. Doğrulanan candidate aynı
DB olarak V2 runtime'a promote edilebilir; sırf adında `shadow` bulunduğu için tekrar kopya almak
zorunlu değildir.

## 4. Başlangıç durumu

`2026-08-13` salt-okunur envanteri:

- V1: `68` Brand, `366` asset, `72` platform connection, `99` linked social account;
- V1: `1.566.933` metric, `6.621` content, `3.608` comment, `6.521` media row;
- mevcut V2 candidate: `67` Brand, `71` platform connection, `97` linked social account;
- mevcut V2 candidate: `1.493.502` metric, `6.234` content, `3.362` comment,
  `6.101` media row;
- V2 API ve web loopback servisleri active;
- V2 Meta/TikTok account, collection ve worker schedule gate'leri disabled;
- V1 ve V2 SSO contract'ı uyumlu, fakat V2 runtime secret'ı mevcut Accumulate imza secret'ıyla
  henüz eşleşmiyor;
- Faz başlangıcında `main`, `origin/main` referansından `5` commit ilerideydi; bu plan ve cutover
  kanıtları artık bilinçli çalışma ağacı değişiklikleridir.

Bu sayılar yalnız başlangıç snapshot'ıdır. Her migration/cutover provasında exact güncel sayılar
yeniden alınır; hard-coded kabul değeri olarak kullanılmaz.

## 5. Kapsam ve sahiplik

### V2 ekibi

- V2 release, DB, media, vault, API, frontend, worker ve testler;
- V1'den read-only candidate import ve parity doğrulaması;
- migrated credential doğrulaması ve provider canary'leri;
- loopback browser/runtime kabul testleri;
- canonical Nginx config taslağı ve V2 rollback artifact'i;
- Accumulate ekibine secretsız SSO/sidebar handoff paketi.

### Accumulate ekibi — yalnız final handoff sonrasında

- Social Media ürününü `embedded_shell` davranışından `downstream_sso` launch davranışına alma;
- sidebar ve Home kartının V2 launch akışını kullanması;
- mevcut `app_sso` token üretimi ve signed Brand scope'un V2'ye gönderilmesi;
- final browser SSO testi ve gerektiğinde kendi değişikliğinin rollback'i.

### Operations/provider sahipleri

- final `social.theaccumulate.com` Nginx/TLS aktivasyonu;
- mevcut Meta/TikTok developer app'lerinin yeni app oluşturmadan V2 operasyonel sahipliğine
  geçirilmesi;
- mevcut canonical callback ve provider app ayarlarının exact doğrulanması;
- secret rotation/injection;
- change window ve gözlem/rollback koordinasyonu.

## 6. Faz A — Değişiklik öncesi salt-okunur baseline

Uygulama başlamadan şu envanter kaydedilir:

1. V1, V2 ve Accumulate branch/HEAD/working-tree durumu;
2. V1/V2 servisleri, timer'ları, portları ve process sahipleri;
3. shared Nginx aktif config hash'i ve V1 upstream'i;
4. V1/V2 DB adları, migration head ve secretsız row-count matrisi;
5. V1/V2 media dosya sayısı, toplam boyut ve kontrollü checksum manifest'i;
6. V2 release/backend/frontend symlinkleri;
7. provider/account/collection/schedule gate'lerinin secretsız değerleri.

Çıkış kapısı: V1 ve Accumulate'ta hiçbir write yapılmadığı gösterilmeden Faz B başlamaz.

## 7. Faz B — Güncel V2 candidate hazırlanması

1. Yeni, boş `social_media_v2_shadow_<timestamp>` DB ve ayrı target media root oluşturulur.
2. V2 migration `0001`–`0004` explicit one-shot olarak uygulanır.
3. Güncel V1 Brand sayısı read-only sorguyla sabitlenir.
4. `backend/scripts/import_legacy_all_brands.py` ile full snapshot alınır.
5. Media dosyaları boyut ve SHA-256 doğrulamasıyla V2-owned dizine kopyalanır.
6. `backend/scripts/verify_legacy_full_import.py` ile tablo, scope ve media parity doğrulanır.
7. Provider ve schedule gate'leri kapalıyken
   `backend/scripts/migrate_legacy_credentials_to_v2.py` çalıştırılır.
8. Credential plaintext eşitliği yalnız process memory içinde doğrulanır; hedefte yalnız
   AES-256-GCM ciphertext ve nonce claim'leri bulunur.
9. Connection/link/credential sayıları kaynakla karşılaştırılır.
10. Candidate env atomik hazırlanır; mevcut çalışan V2 env backup'ı korunur.

Çıkış kapısı:

- kaynak V1 DB read-only kanıtı;
- hedef V2 DB dışında write bulunmaması;
- Brand/account/metric/content/comment/media parity;
- credential ve nonce parity;
- provider/account/collection/schedule gate'lerinin hâlâ disabled olması.

## 8. Faz C — Candidate release ve loopback kabulü

1. Repository'deki güncel V2 backend/frontend immutable release olarak build edilir.
2. Ruff, mypy, backend testleri, frontend testleri, typecheck, production build ve Playwright
   matrisi geçer.
3. Backend/frontend symlinkleri yalnız V2 release alanında atomik değiştirilir.
4. V2 API yalnız `127.0.0.1:8026`, web yalnız `127.0.0.1:3026` üzerinde çalışır.
5. Candidate DB/media env'e atomik promote edilir ve yalnız V2 servisleri restart edilir.
6. `/api/health`, `/api/operations/readiness`, `/`, frontend asset ve media probe'ları geçer.
7. Rollback env/release'e dönülür, probe yapılır ve candidate'a forward dönüş tekrar doğrulanır.

Çıkış kapısı: V1 public root, API, timer ve DB baseline'ı değişmeden kalır.

## 9. Faz D — SSO ve yetki kabulü, Accumulate değişikliği olmadan

1. V2'nin `SOCIAL_SSO_HS256_SECRET` değeri, secret değerini loglamadan mevcut Accumulate imza
   secret'ıyla V2 env tarafında eşitlenir.
2. Accumulate repository/config'i değiştirilmez.
3. Canonical `aud=social_media`, `app_id=social_media`, `token_type=app_sso` tokenı kontrollü test
   harness'iyle V2 loopback consume endpoint'ine verilir.
4. Raw JWT URL, log, screenshot veya test artifact'inde tutulmaz.
5. Aşağıdaki rol matrisi test edilir:

   - `super_admin`;
   - `agency_admin`;
   - `agency_operator`;
   - `viewer`;
   - `viewer + app_role=operator`.

6. Tek Brand, child Brand, hidden parent ve parent rollup scope'ları test edilir.
7. Session cookie, JTI replay, expiry, logout ve scope revoke davranışları doğrulanır.
8. Test session/JTI kayıtları kontrollü olarak yalnız V2 DB'den temizlenir.

Not: Gerçek Accumulate sidebar tıklaması bu fazın parçası değildir. Bu test, Accumulate'ın mevcut
imza contract'ıyla V2 consume/session sınırının hazır olduğunu kanıtlar.

## 10. Faz E — Ürün ve veri kabul matrisi

Her yetkili test scope'unda şu yüzeyler doğrulanır:

- Home/Overview;
- Facebook Cover, Content ve Audience;
- Instagram Cover, Content, Stories ve Audience;
- TikTok Cover, Content ve Audience;
- tarih aralıkları, account filter ve parent rollup;
- loading, empty, partial, unavailable ve error durumları;
- media erişimi ve permalink davranışı;
- XLSX create/status/download akışı;
- Settings ve Integrations rol ayrımı;
- AI Summary history, provider config ve haftalık limit;
- desktop/mobile responsive görünüm;
- browser console error, failed request, API 5xx ve yatay overflow sayıları.

Çıkış kapısı: açık kritik/yüksek bulgu sıfırdır; sahte/demo fallback veya unavailable→`0`
dönüşümü yoktur.

## 11. Faz F — Provider ve worker doğrulaması

Mevcut onaylı Meta/TikTok developer app'leri kullanılacaktır. Yeni provider app veya ikinci
production token ailesi oluşturulmaz. V1 kullanıcı yüzeyi canlı kalırken şu sıra uygulanır:

1. V1 ile kullanılan exact Meta/TikTok app ID, endpoint, callback, scope ve secret-rotation
   metadata'sı secretsız doğrulanır.
2. Aynı app kimlikleri ve secret'lar yalnız V2 root-owned env/vault alanına güvenli olarak inject
   edilir; V1 env veya provider paneli bu aşamada değiştirilmez.
3. Migrated access/refresh tokenların V2 vault parity'si doğrulanır.
4. V2 account/activation gate'leri gerektiğinde time-boxed açılır; automated live schedule kapalı
   kalır.
5. Fake/sandbox provider ile timer, retry, refresh, persistence ve failure-recovery provası tam
   çalıştırılır.
6. Gerçek provider canary öncesi token expiry kontrol edilir. V1'in kullandığı refresh tokenı
   rotate etme ihtimali varsa gerçek canary pre-production'da çalıştırılmaz ve final change
   window'a bırakılır.
7. Refresh gerektirmediği doğrulanan tek Facebook ve Instagram account üzerinde bounded real-read
   canary yapılabilir.
8. TikTok token-info/manual collection canary yalnız access token yeterince geçerliyse ve refresh
   üretmeyecekse yapılır; aksi durumda final provider ownership transfer gate'ine bırakılır.
9. Canary sonuçları V1/provider gerçeği ve V2 persistence ile karşılaştırılır.
10. V2 collection service/timer install, start, lock, stop ve restart davranışı fake/sandbox
    provider ile sertifikalanır; canlı all-account schedule henüz açılmaz.

Uzun süreli çift collection yasaktır. Özellikle refresh-token rotation davranışı olan provider'da
V1 ve V2'nin aynı credential ailesini paralel yenilemesine izin verilmez.

### Origin-bound OAuth istisnası

Geçici public domain kullanılmadığı için gerçek provider OAuth callback'i loopback origin üzerinde
final olarak sertifikalanamaz. Pre-production'da fake/sandbox callback contract'ı ve migrated
credential collection'ı doğrulanır. Gerçek self-service OAuth callback canary'si, canonical
`https://social.theaccumulate.com` V2'ye yönlendirildiği final change window'da yapılır.

Bu istisna açıkça raporlanır; callback canary geçmeden `META_OAUTH_LIVE_VERIFIED` veya
`TIKTOK_CONNECTION_VERIFIED` verilmez.

## 12. Faz G — V1 çalışırken veri güncelliği

İlk full snapshot kalıcı cutover snapshot'ı sayılmaz. Hazırlık uzarsa:

1. V1 canlı veri toplamaya devam eder; pre-production boyunca ana freshness kaynağı V1'dir.
2. V2 gerçek provider collector'ı yalnız refresh üretmeyen bounded canary kapsamında çalışır;
   long-running live schedule final provider ownership transfer'ine kadar kapalıdır.
3. V1'de yeni Brand/account/connection ve veri değişimi read-only reconciliation ile izlenir.
4. Runtime'a kalıcı V1→V2 DB bağımlılığı eklenmez.
5. Accumulate handoff'undan hemen önce yeni bir final candidate veya doğrulanmış bounded delta
   reconciliation hazırlanır.
6. Final candidate tekrar full parity ve credential parity kapılarından geçer.
7. Candidate V2 env'e atomik promote edilir. V2 collector catch-up, V1 provider timer'ları final
   window'da pause edildikten sonra çalıştırılır.
8. Handoff gecikirse reconciliation yeniden çalıştırılır; eski sayımlar kabul edilmez.

V1 hiçbir aşamada pause, read-only veya maintenance moduna alınmaz.

## 13. `READY_FOR_ACCUMULATE_SSO_HANDOFF` çıkış kapısı

Aşağıdakilerin tamamı zorunludur:

- güncel V1→V2 Brand/account/data/media parity;
- credential migration ve decrypt-in-memory parity;
- gerçek Accumulate contract'ıyla loopback SSO/session testi;
- rol ve Brand scope matrisi;
- tüm dashboard, XLSX, AI ve media kabul testleri;
- refresh üretmeyen güvenli Meta/Instagram/TikTok preflight veya manual provider canary'leri;
- final window'a bırakılan provider canary'ler için exact komut, account allowlist ve rollback;
- V2 collection service/timer'ın fake/sandbox provider ile tam operasyon provası;
- `2026-08-13` kullanıcı kararıyla pre-cutover `24` saat bekleme kapısı yerine hızlandırılmış kabul:
  `120/120` ardışık loopback health/readiness/web turu, sıfır error-priority API/web logu, backend
  `152 passed`, frontend `37 passed`, TypeScript kontrolü ve daha önce geçmiş gerçek-browser/rollback
  matrisi; yetkili final pencerede V2 restart recovery tekrar doğrulanır;
- açık kritik ve yüksek bulgu sayısı `0`;
- V2 deploy/rollback/forward provası;
- V1 ve Accumulate başlangıç/bitiş baseline'larının değişmemesi;
- canonical Nginx ve Accumulate handoff paketinin secretsız hazır olması.

Bu kapı geçmeden Accumulate ekibinden değişiklik istenmez.

## 14. Accumulate ekibine final handoff

Accumulate ekibinin kendi repository/config'inde yapacağı işler:

1. `social_media` product launch profile'ını aşağıdaki semantiğe geçirmek:

   ```text
   launch_surface=downstream_sso
   launch_status=ready
   launch_app_id=social_media
   shell_owner=downstream
   runtime_owner=socialmedia_v2
   login_mode=accumulate_contract_only
   ```

2. Sidebar ve Home kartında embedded Social Media route'u açmak yerine mevcut generic downstream
   SSO launcher'ını kullanmak.
3. Final target URL'yi `https://social.theaccumulate.com` olarak tanımlamak.
4. Tıklamada mevcut `/api/apps/sso/social_media/token` endpoint'iyle token üretmek.
5. Browser'ı dönen `/sso/consume?token=...` redirect URL'sine yönlendirmek.
6. Seçili Brand'i exact signed claim olarak göndermek.
7. Parent/child deneyimi için erişilebilir Brand ailesini versioned signed `brand_scope` olarak
   göndermek; browser/local-storage değerini authority kabul etmemek.
8. Integrations kullanıcıları için `app_role=admin|operator` üretmek; Settings authority'sini
   workspace rolünden genişletmemek.
9. Social Media embedded Overview/Facebook/Instagram/TikTok child navigasyonunu downstream
   launch aktifken göstermemek.
10. Değişikliği feature flag/canary cohort ile açmak ve kendi rollback'ini hazırlamak.

V2 ekibi Accumulate koduna, env'ine, servisine veya DB'sine değişiklik yapmaz.

## 15. Final canonical origin aktivasyonu

Final change window sırası:

1. V1 ve V2 health/readiness yeşil doğrulanır.
2. Final candidate freshness/parity yeniden kontrol edilir.
3. V2 API/web/worker zaten çalışır durumda tutulur; bu aşamada build veya migration yapılmaz.
4. Mevcut `social.theaccumulate.com` Nginx config'i ve cert path'i backup/hash ile kaydedilir.
5. Hazır canonical V2 Nginx config'i `nginx -t` ile doğrulanır.
6. Accumulate ekibi downstream launch değişikliğini feature flag kapalı olarak deploy eder.
7. Yalnız V1 provider collector timer'ları kontrollü olarak pause edilir; V1 API/UI ve kullanıcı
   trafiği çalışmaya devam eder. Bu kısa provider ownership penceresi kullanıcı kesintisi değildir.
8. V2 migrated credential ile allowlist'li gerçek Meta/TikTok provider canary'leri çalıştırılır;
   gerekiyorsa token refresh ilk kez V2 vault'a yazılır.
9. Canary başarısızsa V2 provider gate'leri kapatılır, V1 timer'ları yeniden açılır ve public
   routing değiştirilmeden pencere sonlandırılır.
10. Canary başarılıysa Operations canonical origin'i V2 frontend/API'ye graceful Nginx reload ile
    geçirir. Aynı canonical callback path'leri artık V2 handler'larına ulaşır; yeni provider app
    oluşturulmaz.
11. `/api/health`, `/api/operations/readiness`, `/`, `/sso/consume` logging policy ve static asset
    probe'ları çalıştırılır.
12. Accumulate ekibi internal canary cohort için downstream launch flag'ini açar.
13. Birlikte gerçek browser SSO, Brand scope, dashboard, logout ve re-login testi yapılır.
14. Meta/TikTok canonical callback canary'leri çalıştırılır.
15. Canary yeşilse cohort kademeli genişletilir ve V2 live collection schedule açılır.
16. Bütün cohort doğrulandıktan sonra V1 public/embedded Social Media trafik sahipliği kaldırılır;
    V1 backend/timer'ları inactive yapılır. V1 DB/media/release silinmez.

Planlı servis kesintisi yoktur. Nginx reload graceful yapılır; V1 backend process'i ve rollback
artifact'i çalışır durumda tutulur.

## 16. Rollback

Aşağıdakilerden biri olursa cohort genişletilmez ve rollback başlatılır:

- SSO consume/session veya Brand scope hatası;
- dashboard/media/API kritik hata;
- provider credential/token refresh kaybı;
- beklenmeyen veri farkı;
- browser request failure/API 5xx eşiğinin aşılması;
- rate limit veya worker queue kontrol kaybı.

Rollback sırası:

1. Accumulate ekibi downstream launch flag'ini kapatır ve embedded V1 davranışını geri açar.
2. Operations yalnız `social.theaccumulate.com` Nginx config'ini önceki V1 upstream'ine geri alır,
   `nginx -t` çalıştırır ve graceful reload yapar.
3. V2 live collection schedule kapatılır; V1 provider timer'ları önceki doğrulanmış state'iyle
   yeniden açılır.
4. V1 health ve Accumulate embedded Social Media browser akışı doğrulanır.
5. V2 API/web/DB/media silinmez; inceleme için izole şekilde çalışır veya yalnız V2 servisleri
   kontrollü durdurulur.
6. V1 DB/media'ya rollback write veya restore uygulanmaz; çünkü veri alanları başlangıçtan beri
   değiştirilmemişlerdir.

Hedef geri dönüş süresi: `5 dakika` altında. Bu hedef gerçek provayla kanıtlanmadan public cohort
açılmaz.

## 17. Soak ve V1 emekliliği

Public aktivasyondan sonra:

1. İlk `24` saat sık health/readiness/browser/worker gözlemi yapılır.
2. En az `7` gün V2 veri freshness, provider, SSO, report ve hata oranları izlenir.
3. Bu sürede V1 DB, media, release ve config rollback artifact'i olarak korunur; V1 trafik ve
   collection inactive kalır.
4. V1 ve V2 live provider schedule'ı birlikte açık tutulmaz; public aktivasyon sonrasında V2 tek
   collection sahibidir.
5. V1 servis/timer/DB/media kaldırma veya arşivleme bu planın otomatik sonucu değildir; ayrıca
   kullanıcı ve Operations onayı gerektirir.
6. V1 DB ve media hemen silinmez; belirlenen retention süresi boyunca read-only recovery kaynağı
   olarak korunur.

## 18. Güvenlik işi

`2026-08-13` salt-okunur tanı sırasında başarısız bir `psql` çağrısının hata çıktısı kaynak DB
bağlantı URL'sini araç çıktısına yazmıştır. Secret bu dokümana veya Git'e alınmamıştır. İlgili V1
DB credential'ı, bağımlı servis/env envanteri çıkarıldıktan sonra kontrollü olarak rotate
edilmelidir. Rotation Accumulate değişikliği gerektiriyorsa Accumulate ekibinin kendi change
kaydında yapılır; V2 ekibi Accumulate secret/config'ine müdahale etmez.

## 19. Tahmini takvim

Provider credential'ları geçerliyse ve beklenmeyen parity sorunu çıkmazsa:

- baseline + yeni candidate import/verification: aynı iş günü;
- release, SSO, ürün ve manual provider canary: aynı iş günü veya takip eden iş günü;
- pre-cutover minimum soak: kullanıcı kararıyla hızlandırılmış kabul kapısına çevrildi ve aynı iş
  günü geçti; beş dakikalık gözlem timer'ı final pencereye kadar çalışmaya devam eder;
- Accumulate handoff ve public canary: ayrı kontrollü change window.

Takvim baskısı hiçbir güvenlik/parity/rollback kapısını kaldırmaz. Kullanıcıya yansıyan kesinti
hedefi `0`; final routing değişimi önceden çalışan V2 runtime'a graceful reload ile yapılır.

## 20. Durum bayrakları

Plan başlangıcında:

```text
STANDALONE_PRODUCT_COMPLETE=true
STANDALONE_RUNTIME_COMPLETE=true
PARALLEL_PREPROD_FRESH=false
PROVIDER_COLLECTION_LIVE_VERIFIED=false
EXISTING_PROVIDER_APPS_TRANSFERRED_TO_V2=false
READY_FOR_ACCUMULATE_SSO_HANDOFF=false
SSO_LIVE_VERIFIED=false
META_OAUTH_LIVE_VERIFIED=false
TIKTOK_CONNECTION_VERIFIED=false
PUBLIC_V2_ACTIVE=false
V1_TRAFFIC_ACTIVE=true
V1_COLLECTION_ACTIVE=true
V1_RETIRED=false
```

Her faz raporu bu bayrakları açıkça günceller; bir bayrak diğerini otomatik olarak ima etmez.

`2026-08-13T11:17:34Z` çalışma durumu:

```text
STANDALONE_PRODUCT_COMPLETE=true
STANDALONE_RUNTIME_COMPLETE=true
PARALLEL_PREPROD_FRESH=true
EXISTING_PROVIDER_APPS_CONFIGURED_IN_V2=true
EXISTING_PROVIDER_APPS_TRANSFERRED_TO_V2=false
META_REFRESH_FREE_READ_VERIFIED=true
TIKTOK_REFRESH_FREE_READ_VERIFIED=false
PROVIDER_COLLECTION_LIVE_VERIFIED=false
SOAK_24H_COMPLETE=false
SOAK_24H_GATE_WAIVED=true
ACCELERATED_ACCEPTANCE_COMPLETE=true
READY_FOR_ACCUMULATE_SSO_HANDOFF=false
SSO_LIVE_VERIFIED=false
META_OAUTH_LIVE_VERIFIED=false
TIKTOK_CONNECTION_VERIFIED=false
PUBLIC_V2_ACTIVE=false
V1_TRAFFIC_ACTIVE=true
V1_COLLECTION_ACTIVE=true
V1_RETIRED=false
```

`2026-08-17T14:21:23Z` çalışma durumu:

```text
STANDALONE_PRODUCT_COMPLETE=true
STANDALONE_RUNTIME_COMPLETE=true
V2_RELEASE_SOURCE_COMMITTED=true
SOAK_24H_COMPLETE=true
ACCUMULATE_BRANCH_PREPARED=true
ACCUMULATE_BRAND_SCOPE_CLAIM_IN_SCOPE=false
PARALLEL_PREPROD_FRESH=true
PARALLEL_PREPROD_FRESH_AS_OF=2026-08-17T14:41Z
EXISTING_PROVIDER_APPS_TRANSFERRED_TO_V2=false
TIKTOK_REFRESH_FREE_READ_VERIFIED=true
META_REFRESH_FREE_READ_VERIFIED=true
PROVIDER_COLLECTION_LIVE_VERIFIED=false
READY_FOR_ACCUMULATE_SSO_HANDOFF=false
SSO_LIVE_VERIFIED=false
PUBLIC_V2_ACTIVE=false
V1_TRAFFIC_ACTIVE=true
V1_COLLECTION_ACTIVE=true
V1_RETIRED=false
```

Değişen bayrakların gerekçesi:

- `SOAK_24H_COMPLETE=true`: `social-media-v2-soak-probe.timer` `2026-08-13T11:16:36Z` ile
  `2026-08-17T14:21:23Z` arasında `1.188` ardışık health/readiness/web turunu sıfır failed
  invocation ile tamamladı. Waiver'la geçilen kapı artık gerçek süreyle de doludur.
- `V2_RELEASE_SOURCE_COMMITTED=true`: kabul testlerini geçen release'in kaynağı commit edilmemiş
  çalışma ağacındaydı. `2026-08-17` tarihinde dört commit'e bölünerek Git'e alındı; ağaç temiz ve
  `ruff`, `158 passed / 18 skipped`, frontend `47/47`, TypeScript ve production build commit
  edilmiş ağaç üzerinde yeniden doğrulandı.
- `PARALLEL_PREPROD_FRESH=true`: `2026-08-13` candidate'ı bayatlamıştı; V1 o tarihten sonra
  `1` Brand, `1` connection ve `4` linked account daha kazandı. `2026-08-17T14:41Z` itibarıyla yeni
  candidate `social_media_v2_shadow_20260817_1441` alındı ve
  `legacy_full_import_parity=verified` ile doğrulandı: `69` Brand, `73` connection,
  `103` linked account, `1.654.009` metric, `7.233` content, `3.960` comment,
  `7.133` media dosyası, `175` credential satırı ve `175` nonce. Kaynak V1
  `REPEATABLE READ / READ ONLY` kaldı, hedef ayrı ve boş bir DB'ydi. Bu da kalıcı bir söz değil
  kanıttır; V1 toplamaya devam ettiği için final pencerede tekrar koşmalıdır.
- `TIKTOK_REFRESH_FREE_READ_VERIFIED=true`: `2026-08-13`'teki "provider her iki TikTok tokenını da
  reddetti" tespiti yanlıştı. Credential'lar hiçbir zaman geçersiz değildi; V2'nin TikTok
  istemcisindeki dört hata her token doğrulamasını düşürüyordu ve dördü de yalnız canlı API'ye
  karşı görünüyordu. Düzeltmeler sonrası taze credential'larla iki TikTok ve iki Meta hesabı da
  refresh üretmeyen canary'yi geçti; V1 credential ailesi rotate edilmedi. Ayrıntı
  [`cutover/PHASE_F_G_PROVIDER_FRESHNESS_REPORT.md`](cutover/PHASE_F_G_PROVIDER_FRESHNESS_REPORT.md)
  içindedir.
- `ACCUMULATE_BRANCH_PREPARED=true`: Accumulate tarafındaki değişiklik
  `feature/social-media-downstream-launch` branch'inde flag kapalı olarak hazırlanmıştır. V2 ekibi
  Accumulate'ın çalışan ortamına, servisine, env'ine veya DB'sine dokunmamıştır; branch'i deploy
  edip etmemek Accumulate ekibinin kararıdır.
- `ACCUMULATE_BRAND_SCOPE_CLAIM_IN_SCOPE=false`: Accumulate imzalı contract'ta `brand_scope`
  claim'i üretmiyor ve bu cutover kapsamına alınmadı. V2 ilk sürümde tek-Brand modunda çalışacak;
  parent rollup ve hidden-parent deneyimi ayrı bir değişikliğe bırakıldı.

## 21. `2026-08-18` post-deploy gerçek durum

Bu bölüm `2026-08-18T13:03Z` itibarıyla yalnız V2 repository, V2 runtime, public Social hostname ve
V2-owned DB üzerinde yapılan salt-okunur denetimi kaydeder. Accumulate, V1 SocialMedia veya başka
bir kaynak projede write, deploy, restart, DB mutation ya da timer müdahalesi yapılmamıştır.

### 21.1 Public runtime ve SSO

- `https://social.theaccumulate.com` frontend ve `/api/` trafiği V2'ye yönlenmektedir;
- public root, `/api/health` ve `/api/operations/readiness` başarılıdır;
- V2 API ve web service'leri active/enabled, soak timer active/enabled ve ardışık probe'lar
  başarılıdır;
- aktif release `20260818T124522Z-back-to-accumulate` kaynağını kullanmaktadır;
- Nginx config testi başarılı ve yayınlanan static tree `www-data` tarafından okunabilirdir;
- Accumulate downstream değişikliği kullanıcı beyanına göre deploy edilmiştir;
- gerçek public session ile Brand `18` için auth, workspace, capabilities, Overview ve Insights
  istekleri `200` dönmüştür;
- başka bir Brand için gerçek public SSO/browser kanıtı henüz yoktur. Bu nedenle global
  `SSO_LIVE_VERIFIED` tamamlanmış sayılmaz; kanıt yalnız tek Brand kapsamındadır.

Public route açık olmasına rağmen runtime hâlâ `APP_ENV=staging`,
`SOCIAL_RUNTIME_MODE=staging` ve writes enabled durumundadır. Meta/TikTok account, activation ve
collection gate'leri ile automated worker schedule kapalıdır. Collection service/timer
inactive/disabled kalmaktadır. Public dashboard bu nedenle mevcut V2 snapshot'ını okur; V2 henüz
canlı veri toplama sahibi değildir.

### 21.2 Brand, hesap ve veri kapsamı

Aktif V2 DB `social_media_v2_shadow_20260818_1200` üzerinde salt-okunur ölçüm:

| Ölçüm | Değer |
|---|---:|
| Brand | `69` |
| Active Brand | `69` |
| Platform connection | `73` |
| Linked social account | `103` |
| Linked hesabı olan Brand | `53` |
| Linked hesabı olmayan Brand | `16` |
| Metric'i olan Brand | `52` |
| Metric'i olmayan Brand | `17` |
| Metric | `1.720.816` |
| Content | `7.642` |
| Comment | `4.351` |
| Media | `7.396` |

Linked hesapların `87` tanesi `active`, `16` tanesi `disabled` durumundadır. Aktif hesapların
`10` tanesi `permission_restricted` veya `object_inaccessible` health durumundadır. Brand
freshness dağılımında `40` Brand'in son metric günü `2026-08-18`, `12` Brand'in verisi daha eski,
`17` Brand'in metric'i yoktur. Hesapsız veya metricsiz Brand otomatik olarak “kapalı Brand”
anlamına gelmez; test/demo kayıtları, bağlantısı kaldırılmış Brand'ler ve henüz provider hesabı
bağlanmamış gerçek Brand'ler ayrı ayrı sınıflandırılmalıdır.

Bütün `69` Brand V2 DB'de active'dir. Görünür Brand kapsamı DB'deki active bayrağından değil,
imzalı SSO claim'inden çözülür. Bu cutover'da `brand_scope` üretilmediği için V2 bilinçli olarak
tek-Brand modundadır: kullanıcı Accumulate'ta seçili Brand ile launch edilir. V2'nin claim dışı
Brand'leri topluca göstermesi veya local olarak yetki genişletmesi yasaktır. Aynı oturumda
parent/child ve çoklu Brand seçimi istenirse bu, Accumulate'ın optional signed `brand_scope`
claim'ini üretmesini gerektiren ayrı kapsamdır.

### 21.3 Yeni kritik collector bulgusu

Full import kaynak statülerini birebir korur: kullanılabilir legacy linked hesaplar `active`,
disabled hesaplar `disabled` durumundadır. V2-native self-service akışı ise kullanılabilir yeni
linked hesapları `connected` olarak oluşturur.

Mevcut collector target sorgusu yalnız `la.status='connected'` kabul etmektedir. Aktif DB ölçümü:

```text
collector_targets_current_query=0
legacy_active_targets_with_projection=87
legacy_active_targets_missing_projection=0
```

Sonuç olarak mevcut env'de collection gate ve timer açılsa bile worker import edilmiş `87` aktif
hesabın hiçbirini seçmez. Bu durum provider veya credential hatası değildir; legacy/V2 status
vocabulary uyumsuzluğudur. `COLLECTOR_TARGET_SELECTION_VERIFIED=false` ve bu bulgu kapanmadan
provider collection veya timer açılamaz.

Mevcut genel kalite paketi yeşildir: backend `162 passed / 18 skipped`, frontend `47/47`,
TypeScript ve production build başarılıdır. `18` skipped test PostgreSQL bağlantısı gerektirir;
mevcut suite legacy `active` target seçimini kapsamadığı için yeşil sonuç collector bulgusunu
kapatmaz.

### 21.4 Geçici V1 media köprüsü

Public Nginx'te Accumulate'ın eski embedded yüzeyi için `/media/` isteklerini V1'e ileten geçici
bridge hâlâ vardır. Son gözlenen bridge isteği `2026-08-18T12:46:25Z` tarihinde `200` dönmüştür.
Accumulate downstream flag'inin açık olduğu ve embedded Social Media'nın artık istek üretmediği
kanıtlanınca bu block kaldırılmalıdır. Bu işlem provider/collection sahipliğiyle aynı şey değildir;
bridge kaldırılmadan V1 media yüzeyi tamamen emekliye ayrılmış sayılmaz.

### 21.5 Güncel bayraklar

```text
STANDALONE_PRODUCT_COMPLETE=true
STANDALONE_RUNTIME_COMPLETE=true
V2_RELEASE_SOURCE_COMMITTED=true
ACCUMULATE_DOWNSTREAM_DEPLOYED=true
ACCUMULATE_BRAND_SCOPE_CLAIM_IN_SCOPE=false
PUBLIC_V2_ACTIVE=true
SSO_LIVE_SINGLE_BRAND_VERIFIED=true
SSO_LIVE_ALL_BRANDS_VERIFIED=false
BRANDS_IMPORTED=69
BRANDS_ACTIVE=69
BRANDS_WITH_LINKED_ACCOUNTS=53
BRANDS_WITH_METRICS=52
COLLECTOR_TARGET_SELECTION_VERIFIED=true

### 2026-08-18 - Collector status uyumlulugu uygulama kaydi

- `SocialCollectionTargetStore.list_connected()` hedef sorgusu, legacy importlardan kalan
  `linked_social_accounts.status='active'` kayitlari ile canonical `connected` kayitlarini birlikte
  kabul edecek sekilde dar kapsamli olarak guncellendi.
- `platform_connections.status='connected'`, `asset_id IS NOT NULL` ve platform filtreleri aynen
  korundu; disabled/pending baglantilar collector kapsamina alinmadi.
- `backend/tests/test_collection_targets.py` regresyon testi eklendi. Test, iki hesap statusunun
  kabul edildigini, connection gate'inin `connected` kaldigini ve hedef donusumunu dogrular;
  `1 passed in 0.26s` sonucu alindi.
- Degisiklik immutable `/opt/social-media-v2/releases/20260818T132044Z` release'i olarak deploy
  edildi. Rollback hedefi
  `/opt/social-media-v2/releases/20260818T124522Z-back-to-accumulate` olarak korundu.
- Deploy oncesi ve sonrasi Meta collection, TikTok collection ve worker schedule env gate'leri
  `false`; collection service `inactive`, timer `disabled` olarak dogrulandi. V1 ve Nginx'e
  dokunulmadi.
- Deploy edilmis store aktif V2 DB uzerinde provider egress olmadan salt-okunur calistirildi ve
  toplam 87 hedefi hatasiz secti: 44 Facebook, 41 Instagram, 2 TikTok.
- Bu kanitlarla `COLLECTOR_TARGET_SELECTION_VERIFIED=true` olarak kapatildi.

### 2026-08-18 - 69 Brand dashboard ve 53 hesapli Brand veri/media kaydi

- Ilk dashboard coverage calismasi fail-closed olarak `shadow_metric_inventory_changed` verdi.
  Fark, 2026-08-17 tarihli tek bir TikTok profil snapshot'i olan `lifetime_likes` metriğiydi;
  onceki 2026-08-10 envanterinde bulunmuyordu.
- `lifetime_likes`, content-like toplami olmadigi aggregate DB kanitiyla dogrulandiktan sonra
  canonical `video_likes_total` icin profile alias olarak tanimlandi. Oncelik sirasi
  native canonical > profile alias > content-derived total olarak korundu.
- Collector ve legacy metric projection odakli testler `8 passed in 0.35s` sonucu verdi.
- Duzeltme immutable `/opt/social-media-v2/releases/20260818T132537Z` release'i olarak deploy
  edildi; rollback hedefi `/opt/social-media-v2/releases/20260818T132044Z` olarak korundu.
- Aktif `social_media_v2_shadow_20260818_1200` DB uzerinde 69 Brand icin 207 platform dashboard'u
  ve 69 overview read-only uretildi. 169 platform/metric cifti, 125 metric ID ve 15 breakdown
  dimension dogrulandi; scope genislemesi veya KPI/serialization hatasi bulunmadi.
- 69 Brand'in 44'unde secili son-30-gun dashboard araliginda metric degeri, 36'sinda story vardir.
- Hesap kaydi olan 53 Brand'in 50'sinde metrics, content ve media birlikte vardir. Brand `26`,
  `34` ve `51` hesapli olmakla birlikte uc veri yuzeyinde de bostur; sonraki account-health
  siniflandirmasinda ele alinacaktir.
- V2 media root'undaki 7.396 dosyanin tamami (`1.865.919.886` byte) DB size ve SHA-256 degerleriyle
  dogrulandi; eksik, fazla veya checksum hatali dosya yoktur.

DASHBOARD_SCOPE_69_BRANDS_VERIFIED=true
ACCOUNT_BRAND_DATA_MEDIA_AUDIT_COMPLETE=true
ACCOUNT_BRANDS_WITHOUT_DATA=3

### 2026-08-18 - Hesapsiz Brand ve account-health siniflandirma kaydi

- Hesapsiz 16 Brand read-only olarak parent/child, veri ve aktiflik acisindan incelendi.
- Brand `19` (`Hilton`) dogrudan hesapsizdir fakat 3 child ve 3 descendant account tasiyan gercek
  rollup parent'tir; dogrudan hesap baglama adayi degildir.
- Brand `21` (`Turk Eximbank`) dogrudan hesapsiz olmakla birlikte tarihsel metrics/content tasir;
  gercek musteri reconnect adayi olarak ayrildi.
- Acik test/demo bos-durum grubu: `27 Test Sub Brand`, `31 testetets`, `65401 Test 88`,
  `286112 Test3`, `286115 Test2`, `286164 Test Brand`, `286221 testttt`,
  `286284 Musteri Demo`.
- Is sahibi karari olmadan otomatik siniflandirilmayacak grup: `32 Cherry Shop`, `52 Nike`,
  `53 Adidas`, `286173 Digital Exchange`, `286213 Delphin Hotels & Resorts`,
  `286227 Semih Company`.
- Account-health sayimi LEFT JOIN ile tekrarlandiginda plan notundaki sayi dogrulandi:
  16 disabled ve 10 active/unhealthy hesap vardir. Ilk INNER JOIN olcumu, connection kaydi olmayan
  disabled `link_id=92` kaydini gizledigi icin 15 gostermisti.
- `link_id=92`, `Belconti TikTok (demo)` kaydidir; disabled, nightly off, `connection_id=NULL` ve
  projection/reference'siz orphan demo olarak tutulur.
- Kalan 25 cleanup adayinin V2 connection projection'i ve encrypted access credential'i provider
  egress olmadan yerel olarak acildi; 25/25 mevcut, revoke/expiry engeli gorulmedi. Token degeri
  log veya dokumana yazilmadi.
- Aktif ama sagliksiz 10 hesap: 3 `object_inaccessible`, 7 `permission_restricted`. Bunlar collector
  acilmadan once Meta object ownership/role ve OAuth izinleri acisindan hesap sahiplerince
  duzeltilmeli, ardindan bounded provider-read ile dogrulanmalidir.
- Disabled gercek-musteri karar grubu: Belconti (`8`, `14`), Wainer (`9`, `12`), Thalure (`10`,
  `17`) ve Limak International Hotels & Resorts (`72`, `73`). Bunlar is sahibi onayi olmadan
  re-enable edilmez.
- Disabled acik demo/mismatch/invalid grup: `1`, `21`, `22`, `24`, `25`, `26`, `27`, `92`.
  Bu kayitlar collector disinda kalmaya devam eder; reauthorization uygulanmaz.
- Bu audit DB status mutation'i, token refresh/revoke veya provider istegi yapmamistir.

ACCOUNTLESS_BRAND_AUDIT_COMPLETE=true
ACCOUNTLESS_BRAND_OWNER_DECISION_REQUIRED=0
ACCOUNTLESS_BRANDS_WAIT_FOR_LINK=true
DISABLED_ACCOUNT_COUNT=16
UNHEALTHY_ACTIVE_ACCOUNT_COUNT=10
OFFLINE_CREDENTIAL_AVAILABILITY_VERIFIED=true
LIVE_PROVIDER_ACCESS_VERIFIED=false

### 2026-08-18 - V1 writer quiescence ve final parity kaydi

- Runbook'taki exact 23 V1 provider timer salt-okunur kontrol edildi; tamami `inactive`, unit-file
  durumu `enabled` olarak goruldu. `ars-social-backend.service` aktif birakilmistir. V1 unit/env/DB
  uzerinde mutation yapilmadi.
- V2 API/web aktif, collection service inactive, collection timer disabled; Meta collection,
  TikTok collection ve worker schedule env gate'leri `false` olarak tekrar dogrulandi.
- Final full-import verifier iki DB'yi `REPEATABLE READ + READ ONLY` kullanarak karsilastirdi.
  Brand/platform scope ve satir parity sonucu: 69 Brand, 358 meta account, 97 asset,
  103 linked account, 73 platform connection, 97 sync state, 1.720.816 metric,
  7.642 content, 4.351 comment, 7.396 media row ve 6 AI insight eslesti.
- Kaynak ve V2 media koklerindeki 7.396 dosyanin size/SHA-256 degerleri ve exact dosya seti
  eslesti. 69 legacy Brand projection'i ve 97 completed legacy snapshot job dogrulandi.
- Credential verifier iki DB'yi read-only kullandi; 175 encrypted credential plaintext parity,
  175 unique nonce claim, 73 connection projection, 173 access ve 2 refresh credential eslesti.
  Dört cross-Brand link ve bir unbound link semantigi korundu; secret yazdirilmadi.
- TikTok ownership transferi uygulanmadi. Provider owner refresh-token rotation ve rollback
  prosedurunu onaylamadan ilk V2 refresh calistirilmayacaktir.

V1_PROVIDER_TIMERS_INACTIVE=true
FINAL_DATA_MEDIA_PARITY_VERIFIED=true
FINAL_CREDENTIAL_PARITY_VERIFIED=true
TIKTOK_OWNERSHIP_TRANSFERRED=true
V2_COLLECTION_ACTIVE=false

### 2026-08-18 - Is sahibi kararlari ve TikTok ownership transfer kaydi

- Hesapsiz Brand'ler mevcut empty-state durumunda kalacaktir. Yeni account link edilmeden import,
  backfill veya collection akisi baslatilmayacaktir.
- Belconti, Wainer ve Thalure icin artik provider erisimi yoktur; mevcut account linkleri disabled
  ve nightly off kalacak, reauthorization uygulanmayacaktir.
- Limak International Hotels & Resorts parent seviyesindeki legacy linkler acilmayacaktir. Aktif
  hesaplar child Brand'lerde sahiplenildigi icin parent kayitlar disabled kalir.
- TikTok ownership onayi alindiktan sonra collector refresh yolunun access ve refresh credential'i
  iki ayri transaction'da yazdigi tespit edildi. `ProjectionCredentialStore.put_many()` eklendi;
  access+refresh artik tek DB transaction'inda persist edilir. Collector bu atomic yolu kullanir.
- Ownership araci exact link allowlist (`99`, `100`), 23 V1 timer-inactive kontrolu, tum V2
  account/provider/schedule gate'lerinin closed olmasi, encrypted recovery staging, identity/scope
  token-info kontrolu ve atomic canonical promote kosullariyla eklendi.
- Odakli testler 19 passed; izole gecici PostgreSQL testleri 7 passed; resmi TikTok refresh response
  field testi dahil TikTok provider testleri 12 passed sonucunu verdi.
- Link `99` ilk refresh response'u provider'in resmi `refresh_token_expires_in` alanini tasirken
  eski parser `refresh_expires_in` bekledigi icin staging oncesi fail-closed durdu. Resmi TikTok
  Business API contract'i dogrulandi, parser canonical alan + legacy fixture uyumluluguyla
  duzeltildi. Recovery refresh'i basarili oldu; yeni token cifti encrypted staging, token-info ve
  atomic promote adimlarini gecti.
- Link `100` ownership transferi ilk kontrollu denemede basarili oldu. Her iki connection (`72`,
  `74`) icin audit state `promoted`, staging credential sayisi sifir ve canonical access/refresh
  tokenlari local vault acisindan available olarak dogrulandi.
- Her iki transfer sonrasinda refresh-free real provider canary gecti. Canary refresh/revoke veya
  credential mutation yapmadi; identity/scope dogrulandi ve fingerprint degismedi.
- Son runtime release `/opt/social-media-v2/releases/20260818T134624Z`, rollback release
  `/opt/social-media-v2/releases/20260818T134340Z` oldu. Meta/TikTok collection ve worker schedule
  gate'leri false; V2 collection service inactive ve timer disabled kaldi.

DISABLED_ACCOUNT_OWNER_CLASSIFICATION_COMPLETE=true
DISABLED_ACCOUNT_REAUTH_REQUIRED=0
TIKTOK_OWNERSHIP_CONNECTION_72_PROMOTED=true
TIKTOK_OWNERSHIP_CONNECTION_74_PROMOTED=true
TIKTOK_POST_TRANSFER_READ_CANARY_VERIFIED=true
TIKTOK_OWNERSHIP_TRANSFERRED=true
V2_COLLECTION_ACTIVE=false
COLLECTOR_TARGETS_CURRENT_QUERY=0
SOCIAL_RUNTIME_MODE=staging
META_COLLECTION_ENABLED=false
TIKTOK_COLLECTION_ENABLED=false
WORKER_SCHEDULE_ENABLED=false
EXISTING_PROVIDER_APPS_TRANSFERRED_TO_V2=false
PROVIDER_COLLECTION_LIVE_VERIFIED=false
FINAL_QUIESCED_PARITY_VERIFIED=false
READY_FOR_ACCUMULATE_SSO_HANDOFF=false
V1_RETIRED=false
```

`PUBLIC_V2_ACTIVE=true`, provider ownership veya collection'ın tamamlandığını ima etmez. Public
read path, provider writer ownership ve SSO Brand kapsamı birbirinden bağımsız kapılardır.

## 22. Bundan sonraki bağlayıcı tamamlama sırası

### 22.1 V2 repository düzeltmesi — ilk iş

1. Collector target eligibility tek bir açık sözleşmede birleştirilir:
   - V2-native `connected` hesap seçilir;
   - legacy import `active` hesap yalnız scheduled collection için geçerli legacy enablement
     koşulunu taşıyorsa seçilir;
   - `disabled`, eksik asset, bağlantısı connected olmayan veya credential projection'ı eksik
     hesap her durumda dışarıda kalır.
2. PostgreSQL regression testi en az `connected`, legacy `active`, legacy `disabled`, eksik
   projection ve yanlış platform/Brand scope örneklerini kapsar.
3. Test DB üzerinde target count beklenen allowlist ile exact karşılaştırılır; yalnız row count
   kontrolü yeterli değildir.
4. Backend, frontend, secret-leak ve production build doğrulamaları tekrar çalıştırılır.

### 22.2 Provider gate'leri kapalı V2 deploy

1. Düzeltme immutable V2 release olarak deploy edilir.
2. Runtime henüz staging/write-capable kalabilir; Meta/TikTok account, activation, collection ve
   worker schedule gate'leri kapalı tutulur.
3. V2-only controlled restart sonrasında loopback ve public health/readiness/root/static probe'ları
   tekrar geçer.
4. Salt-okunur target preflight, `87` legacy active hesabı ve varsa V2-native connected hesapları
   exact allowlist olarak raporlar; provider egress veya DB mutation üretmez.

### 22.3 Brand kabul matrisi

1. `69` Brand için exact dashboard scope ve cross-Brand denial testi çalıştırılır.
2. Linked hesabı olan `53` Brand için hesap/platform/data/media görünürlüğü doğrulanır.
3. En az bir gerçek dolu Brand, bir empty Brand, bir disabled-account Brand ve bir health sorunu
   bulunan Brand gerçek browser canary kapsamına alınır.
4. Gerçek Accumulate SSO her canary'de yalnız seçili Brand'i açmalıdır. Tek oturumda bütün
   Brand'leri göstermek bu planın hedefi değildir.
5. Hesapsız `16`, metricsiz `17`, disabled `16` hesap ve aktif fakat sağlıksız `10` hesap için
   `expected_empty`, `reauthorize`, `relink`, `retire_test_data` veya `investigate_provider`
   sınıflandırması üretilir.

### 22.4 Dış bağımlı final ownership penceresi

Bu adım V2 repository ekibinin V1'e doğrudan müdahale yetkisi değildir. V1 Operations/provider
sahibi, [`cutover/FINAL_CHANGE_WINDOW_RUNBOOK.md`](cutover/FINAL_CHANGE_WINDOW_RUNBOOK.md)
sırasıyla:

1. V1 provider writer/timer durumunu kaydeder ve kontrollü olarak quiesce eder;
2. final read-only V1→V2 data/media/credential parity'yi tekrar çalıştırır;
3. TikTok refresh-token ownership transferi ve rollback prosedürünü uygular;
4. Meta/TikTok bounded read ve tek hesaplık collection canary'lerini birlikte doğrular.

Bu dış kapılar tamamlanmadan V2 schedule açılmaz. V2 ekibi Accumulate veya V1 kaynak ağacında,
servisinde, DB'sinde ya da timer'ında değişiklik yapmaz.

### 22.5 V2 production aktivasyonu

Yalnız §22.1–§22.4 yeşil olduktan sonra:

1. production runtime `APP_ENV=production`, `SOCIAL_RUNTIME_MODE=active` ve explicit V2 writes
   durumuna alınır;
2. önce tek allowlisted hesapla gerçek collection canary çalıştırılır;
3. canary DB/media diff'i, provider request bütçesi, credential fingerprint/rotation sonucu ve
   rollback kanıtı incelenir;
4. Meta/TikTok collection gate'leri yalnız doğrulanmış platform/account kapsamı için açılır;
5. V2 collection timer etkinleştirilir ve en az iki ardışık schedule turu gözlenir;
6. `40 current / 12 stale / 17 none` freshness dağılımı yeni collection sonuçlarıyla yeniden
   ölçülür; beklenen empty/disabled kayıtlar ayrı raporlanır.

### 22.6 Kapanış

1. Accumulate embedded Social Media trafiğinin bittiği kanıtlanınca geçici `/media/` V1 bridge'i
   kaldırılır ve Nginx graceful reload sonrası media/public smoke tekrarlanır.
2. `docs/ACCUMULATE_SSO_HANDOFF.md` artık gerçekleşen deploy'u ve düzeltilmiş TikTok sonucunu
   yansıtacak şekilde post-deploy kayda çevrilir.
3. Faz F/G raporu final ownership, live collection ve freshness kanıtlarıyla kapatılır.
4. Yalnız bütün kapılar yeşilse aşağıdaki final bayraklar verilir:

```text
COLLECTOR_TARGET_SELECTION_VERIFIED=true
FINAL_QUIESCED_PARITY_VERIFIED=true
EXISTING_PROVIDER_APPS_TRANSFERRED_TO_V2=true
PROVIDER_COLLECTION_LIVE_VERIFIED=true
SSO_LIVE_ALL_REQUIRED_CANARIES_VERIFIED=true
SOCIAL_RUNTIME_MODE=active
PUBLIC_V2_ACTIVE=true
V1_RETIRED=true
```

`V1_RETIRED=true`, V1 DB/media/release'in silinmesi anlamına gelmez; rollback ve audit saklama
politikası ayrıca uygulanır.

## 2026-08-18 - Tek hesaplik gercek TikTok collector canary takibi

- Canary hedefi: `linked_social_accounts.id=99`, Pine Beach Belek, `asset_id=2862`, `brand_id=18`.
- Global production env degistirilmedi. V2 collection, provider schedule ve timer gate'leri kapali tutuldu; ilk deneme yalnizca tek CLI prosesi icin gecici TikTok account/activation/collection gate'leriyle calistirildi.
- Ilk gercek collector denemesi provider'in ilk `profile` asamasinda durdu: `/open_api/v1.3/business/get/` yaniti `provider_rejected:40002`; hic metric/content/comment/media yazilmadi.
- Token-info ve ownership kontrolleri basarili oldugundan sorun credential transferinden ayrildi ve profil istek sozlesmesine indirildi.
- Resmi TikTok API for Business v1.3 referansinin dogrudan dokuman API'si endpoint'in `GET`, `Access-Token`, `business_id` ve `fields` sozlesmesini dogruladi. `business_id` yalnizca zorunlu URL parametresidir ve `fields` listesine yazilamaz; lifetime begeni/video alanlari `total_likes` ve `videos_count` adlarini kullanir.
- Duzeltme: `TikTokAccountsWireMapper.profile_fields` listesinden `business_id` cikarildi; `likes`/`video_count` alanlari `total_likes`/`videos_count` olarak degistirildi. Onceki ara `likes_count` cikarimi canary calistirilmadan resmi dokuman API'siyle duzeltildi.
- Resmi alanlarla provider yaniti basarili geldi; ikinci engel yerel `TikTokProfileReader` parser'inin response icinde artik donmeyen `business_id` alanini zorunlu tutmasiydi. Profil kimligi, token-info ile `creator_id` uzerinden onceden dogrulanan `ProviderAccount.account_id` kaynagindan alinacak sekilde duzeltildi; wire ve identity-boundary regresyon testleri guncellendi.
- Profil asamasi gecildikten sonra gercek yanitta `comments=-1` goruldu. TikTok'un unavailable sentinel'i olan `-1`, gunluk metrik parser'inda `None`/skip olarak normalize edildi; `-2` ve daha dusuk negatifler gecersiz kaldi. Her iki sinir icin regresyon testi eklendi.
- Gunluk metrik asamasi sonrasinda content parser'i timezone bilgisi olmayan resmi `create_time` datetime degerini reddetti. TikTok Accounts API'nin UTC tabanli naive datetime degeri UTC olarak normalize edildi; timezone'lu ISO ve legacy epoch destegi korundu ve regresyon testi eklendi.
- Canli `create_time` degeri epoch saniyesini string (`'1785253164'`) olarak dondurdu. Timestamp parser'i numeric-string epoch'u UTC olarak kabul edecek sekilde genisletildi; naive ISO ve numeric-string epoch regresyonlari birlikte kilitlendi.
- Canli video pagination cevabi `has_more=true` ile integer cursor dondurdu. Opaque non-negative integer cursor decimal string'e normalize edilerek mevcut sonraki-sayfa kontratina uyarlandi; regresyon testi eklendi.
- Ilk yazimli canary `172` metric, `196` content ve `196` media uretti; yorumlar `comments_unavailable` nedeniyle sonucu `partial` birakti. Izole trace yetki reddi olmadigini, comment `create_time` alaninin numeric-string epoch (`'1785485291'`) oldugunu gosterdi. Comment timestamp ve integer cursor parser'lari content ile ayni canli uyumluluk kurallarina getirildi; test guncellendi.
- Durum: duzeltme deploy/canary asamasinda; canary basarili olmadan global collection veya V2 timer acilmayacak.

## 2026-08-24 - Timer ve dashboard freshness incident incelemesi

- TikTok ownership transferi/ilk canary tarihi `2026-08-18`; inceleme tarihi `2026-08-24`. Gecen sure 6 gun.
- `social-media-v2-collection.timer` enabled/active ve 30 dakikada bir tetikleniyor. `SOCIAL_WORKER_SCHEDULE_ENABLED`, Meta collection ve TikTok collection gate'leri production env'de acik. Sorun timer'in tetiklememesi degil.
- Collection service her tetikte provider cagrisindan once `ValueError: meta_connection_payload_invalid` ile exit `1` oluyor. Ilk kesin hata `2026-08-21T08:30:13Z`; inceleme anindaki son hata `2026-08-24T06:01:08Z`.
- Transferden inceleme anina kadar journal sonucu: `104` tamamlanmis collection service calismasi, `145` failed calisma. Hata basladiktan sonra yarim saatlik timer fail eden batch'i tekrarliyor.
- Kok veri anomalisi: ayni isimde iki aktif `Turk Eximbank` brand kaydi var. `brand_id=21` Meta `connection_id=12` sahibi fakat aktif linked account'u yok; `brand_id=73` aktif Facebook/Instagram linked account'larinin sahibi fakat bu account'lar `brand_id=21`e ait connection `12`yi kullaniyor.
- Etkilenen aktif hedefler: Facebook `linked_social_accounts.id=3`, Instagram `id=13`; ayrica disabled legacy Facebook link `id=22` ayni cross-brand connection'i kullaniyor.
- Collector cross-brand connection'i guvenlik kontroluyle dogru olarak reddediyor; ancak `list_connected()` generator'u tek bozuk hedefi izole etmek yerine exception ile 91 aktif hesabin tum batch'ini durduruyor.
- Inceleme aninda 91 aktif hesabinin metric kartlarinin tamami en az 3 gun geride: Facebook `40`, Instagram `36`, TikTok `3` hesap tam 3 gun; Demo Company'nin uc platformu 5 gun.
- Daha eski ve account-health=`error` kartlar: Vatan Yapi & Miamarin FB/IG `108` gun, Biblos Alacati FB/IG `94` gun, Tarti Medikal FB `63` gun, Zupp.in FB/IG `24` gun, CTG Elektrik IG `20` gun, Istanbul Marin IG `20` gun.
- Onerilen onarim iki parcali: canonical Turk Eximbank brand karariyla connection/link ownership verisini uzlastirmak; ardindan malformed bir target'in tum scheduled batch'i durdurmamasini saglayan per-target isolation ve regresyon testi eklemek.
- Inceleme salt-okunur yapildi; brand, connection, gate, timer veya runtime kodunda degisiklik yapilmadi.

### 2026-08-24 - Story freshness kontrolu

- Veritabaninda `2,625` adet `story` ve `76` adet `shared_story` content row'u var; story gecmisi bos degil.
- Aktif Instagram hesaplarinin `40/42` tanesinde toplam `2,559` story row'u mevcut. En yeni Instagram story zamani `2026-08-21 10:13:15 Europe/Istanbul`, son projection write `2026-08-21 11:20:01 Europe/Istanbul`.
- Aktif Facebook hesaplarinin `5/45` tanesinde toplam `96` story/shared-story row'u mevcut. En yeni Facebook story zamani `2026-08-13 14:00 Europe/Istanbul`; son projection write `2026-08-21 10:44:06 Europe/Istanbul`.
- Collection batch'i `2026-08-21`de kirildigi icin 21 Agustos sonrasi yeni story projection'i yok. Dolayisiyla gecmis story'ler tasinmis/toplanmis, fakat son uc gunun story'leri guncel degil.

## 2026-08-24 - Collection freshness recovery execution

- V2 collection timer stopped and disabled before code or ownership changes. V1 was not changed.
- Exact target-materialization check found 88 joined rows: 87 valid and 1 invalid.
- The batch-level exception is caused by `linked_social_accounts.id=57` (CTG Elektrik Instagram, `connection_id=47`, `brand_id=286189`): external account `17841471029369177` is absent from the connection projection account list.
- `connection_id=12` is a separate ownership inconsistency: the connection/projection owner is `brand_id=21`, while its three linked accounts belong to active `brand_id=73`. It will be reconciled transactionally without moving or deleting historical metric/content rows.
- Collector remediation: enforce `platform_connections.brand_id = linked_social_accounts.brand_id` and isolate malformed targets so one target cannot abort the complete batch. Skips log identifiers and the validation error only; payloads and credentials are never logged.
- CTG account 57 will remain isolated until its projection is repaired or the account is reauthorized. No credential reference will be guessed or copied from another account.

### Recovery execution result

- Focused regression test: `backend/tests/test_collection_targets.py` passed (`2 passed`).
- Backend-only immutable release deployed: `/opt/social-media-v2/releases/20260824T062548Z-collection-target-isolation/backend`.
- V2 API restarted successfully. Frontend remained on `/opt/social-media-v2/releases/20260821T085149Z-tiktok-account-management/frontend`.
- `connection_id=12` ownership was changed in one guarded transaction from `brand_id=21` to active `brand_id=73`; `v2:meta:connection:12` projection ownership was changed in the same transaction. Its three linked accounts were already owned by brand 73. Historical metric/content rows under brand 21 were not moved or deleted.
- Two timer-disabled scheduled recovery runs completed with service exit code 0. Run 1 processed 43/87 targets before the internal collection budget; run 2 processed 47/87. Per-account provider failures did not terminate either batch.
- The systemd start timeout was temporarily inspected during recovery. A runtime-only `/run` override was used, then removed. The collection service is restored to its original `TimeoutStartSec=25min` configuration.
- The remaining five healthy 3-day-stale accounts were processed with scoped `--complete` runs for brands 70, 60, 62, and 30. The transient unit completed successfully with exit code 0 and processed six account targets (the scopes included one already-fresh sibling account).
- Metric freshness after recovery: 91 eligible active/connected accounts; 79 at 0-1 day lag, 0 at 2 days, 0 at 3 days, and 12 older exceptions. The incident population of 79 accounts at exactly 3 days lag is fully cleared.
- Recovery write evidence since 2026-08-24 06:27:44 UTC: 78 accounts / 1,836 content rows touched; 10 accounts / 19 story rows touched; 45 accounts / 74 media rows touched.
- The 12 older exceptions are not timer-regression accounts: eight provider authorization/access failures (Vatan Yapi & Miamarin 2, Biblos Alacati 2, Tarti Medikal 1, Zupp.in 2, Istanbul Marin 1), CTG Elektrik Instagram link 57 with the projection mismatch, and three Demo Company accounts intentionally left without a collection projection.
- Timer re-enabled after the batch-level recovery gate passed. `social-media-v2-collection.timer` is enabled and active; enabling it triggered a scheduled collection at 2026-08-24 07:20:28 UTC.
- V1 was not changed during this recovery.

## 2026-08-24 - Salamis Bay Conti provider account discovery entrypoints

- Production diagnosis: active Salamis Bay Conti is `brand_id=286200`, tenant 1. It has no Meta connection/discovery rows and no TikTok linked account yet. No account was linked or moved during this work.
- The Brand Setup `Connect` action opened the account manager, but the provider authorization actions existed only in the modal footer. In the reported viewport the footer was outside the visible area, leaving an empty account panel with no usable way to load provider accounts.
- Empty Meta panels now show a visible `Load Meta accounts` action inside the account panel. Meta authorization only discovers accounts; linking still requires the user to select accounts and save.
- Empty TikTok panels now show a visible `Load TikTok account` action inside the account panel and hand off to the separate TikTok authorization flow.
- Added a frontend regression test for a Brand with zero saved Meta/TikTok accounts.
- Backend ownership boundaries, production account ownership, credentials, and V1 were not changed.
- Immutable frontend deployment target: `/opt/social-media-v2/releases/20260824-salamis-account-discovery/frontend`.

### Correction: existing in-application Meta catalog, not OAuth

- The initial interpretation was incorrect: the requested source was the application's existing Meta account inventory, not a new provider authorization.
- The temporary inline `Load Meta accounts` / `Load TikTok account` empty-state actions were removed from the frontend.
- The application catalog contains four Salamis matches: Facebook `242253949139245`, Instagram `17841400914154651`, and the Lemon Spa Facebook/Instagram accounts `487207687995064` / `17841449554579048`.
- A guarded tenant-local catalog reuse transaction created Salamis Meta selection `connection_id=79` with 98 credential-backed discovery rows in `available` state.
- The transaction created no `linked_social_accounts` rows. Account selection and linking remain entirely with the user.
- The source and target are both tenant 1. No cross-tenant catalog or credential access was introduced.
- Corrected immutable frontend deployment target: `/opt/social-media-v2/releases/20260824-salamis-existing-meta-catalog/frontend`.

## 2026-08-24 - Existing account catalog plus provider authorization

- Confirmed desired UX: existing in-application accounts and provider OAuth must coexist.
- Meta keeps the existing 98-account application catalog for Salamis and now always exposes `Authorize another Meta account` beside catalog save actions.
- TikTok readiness now returns a separate `available_accounts` collection containing credential-backed accounts from other Brands in the same tenant. Cross-tenant accounts and entries without a live connection projection are excluded.
- TikTok existing accounts are displayed as `Available in app`; `Authorize another TikTok account` remains available in the same panel.
- Existing TikTok entries are intentionally read-only in this change. TikTok credentials are account/Brand scoped; silently cloning a token or transferring ownership would risk disabling collection for the source Brand. No TikTok account was moved, copied, linked, or unlinked.
- Added backend and frontend regression coverage for the new readiness contract and catalog rendering.
- Immutable backend/frontend deployment target: `/opt/social-media-v2/releases/20260824-account-catalog-and-auth`.
- V1 is unchanged.

## 2026-08-24 - Newly linked account self-healing collection remediation

- Salamis Bay Conti Facebook link `108` and Instagram link `109` were provider-accessible and
  current raw metrics/content were written, but their initial backfills did not finalize cleanly.
- Facebook exhausted the 300-second account budget inside media persistence after profile/daily
  writes. Instagram encountered an optimistic checkpoint race and returned partial. These were
  collector lifecycle defects, not Meta authorization failures.
- Meta initial content backfill is now one 25-item page per timer turn. The durable cursor keeps
  the account in `in_progress`; subsequent timer turns resume automatically and only mark
  `complete` when the provider feed reaches its end.
- The first 30-day metric window is collected before content. Once durable core data exists, an
  account-budget interruption records partial progress instead of changing an accessible account
  to `health_status=error`.
- Feed and Story media each receive a bounded 30-second slice and individual fetches are bounded
  to 10 seconds. When the slice is exhausted, the content checkpoint is deliberately not advanced;
  the next timer pass replays the idempotent page, reuses media already on disk, and fills the
  remaining files.
- A checkpoint compare-and-swap loss now adopts the durable concurrent winner. Refreshes complete
  without an account failure and backfills continue from the winner's cursor.
- `nightly_enabled` becomes true automatically when backfill reaches `complete`; partial initial
  progress remains false and cannot be mistaken for a finalized account.
- Regression coverage was added for incremental Meta backfill bounds, media deferral, and
  checkpoint-race recovery. V1 was not changed.

### Salamis dashboard snapshot visibility follow-up

- Production inventory proved the apparently empty follower and audience cards were not missing
  provider data. Facebook held `52,562` followers plus 45 country and 45 city rows; Instagram held
  `46,848` followers plus follower/engaged/reached country-city and follower age-gender rows.
- Preset reporting ranges end on the previous completed day, while a newly linked account's first
  profile/audience snapshots are written on the current day. The dashboard query therefore removed
  the only current snapshot even though freshness and collection were healthy.
- Preset dashboards now supplement KPI and audience breakdown surfaces with the latest post-range
  snapshot. Current-day flow totals remain excluded, custom historical ranges remain exact, and
  trend history is never fabricated.
- Instagram demographics previously matched the substring `age` inside `engage`, allowing the
  best-time heatmap (`Mon|18`, etc.) to render as age data. Dimension matching is now token-based.
- Follower geography is preferred over engaged/reached geography for primary country/city widgets.
- Organic/paid reach remains explicitly unavailable where Meta did not return that family; no zero,
  estimate, or synthetic split is written. V1 remains unchanged.

### 2026-08-24 - Salamis eksik follower akislari ve provider capability ayrimi

- Salamis Facebook ve Instagram hesaplarinda current follower/audience snapshot supplement duzeltmesi sonrasinda follower toplamlari ve audience kirilimlari gorunur hale geldi.
- Kalan follower trend bosluklarinin veri kaybi degil, V2 daily collector'in Meta tarafinda desteklenen follower flow metriklerini hic istememesi oldugu provider uzerinde dogrulandi.
- Facebook `page_daily_follows` ve `page_daily_unfollows`; Instagram `follows_and_unfollows` + `follow_type` contract'i kullanilarak `follows`, `new_followers`, `unfollows` ve signed `followers_net` uretilmesi eklendi.
- Dashboard, en yeni gercek follower snapshot'ini anchor alip gunluk gercek follow/unfollow akislariyla geriye dogru follower toplamlarini yeniden kuracak. Bir gunde follows veya unfollows eksikse tahmin yapmadan reconstruction duracak.
- Salamis provider capability probe sonucu Facebook reach insight'lari ile Instagram organic/paid views/reach breakdown'lari Meta tarafindan `400:100` ile reddediliyor. Bu alanlara sentetik veri yazilmayacak; bunlar hesap/uygulama capability siniri olarak ele alinacak.
- Reader fixture ve follower reconstruction regression testleri eklendi. Testler operasyon talebi olmadan calistirilmadi.
