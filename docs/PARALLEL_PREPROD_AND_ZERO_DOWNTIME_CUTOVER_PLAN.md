# Social Media V2 — Paralel Pre-production ve Kesintisiz Geçiş Planı

Tarih: `2026-08-13`

Durum: **FAZ A–E TAMAMLANDI — FAZ F/G VE 24 SAAT SOAK DEVAM EDİYOR**

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
