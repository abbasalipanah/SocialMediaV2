# Social Media V2 Backend Independence Contract

Tarih: `2026-07-14`

Bu sözleşme Faz 4 backend sınırlarını tanımlar. Provider çağrısı, durable mutation ve worker
çalıştırma yalnız açık policy/capability kapılarından geçer. Production DB, provider credential,
traffic veya schedule bu fazın parçası değildir.

## Platform ve capability sınırı

- Canonical platform kümesi yalnız `facebook | instagram | tiktok` değerleridir.
- Provider davranışı Profile, Content, Comments ve Audience portlarına ayrılır.
- Registry her platform/capability çifti için exact status döndürür:
  `unsupported | not_approved | not_configured | blocked_configuration |
  manual_activation_required | partial | available`.
- Bootstrap registry hiçbir capability'yi sahte biçimde `available` yapmaz.
- TikTok ilk runtime mapper'ı yalnız `tiktok_business_accounts_v1_3` account-holder wire
  alanlarını üretir. Advertiser runtime adapterı veya route'u yoktur ve config disabled kalır.

## Metric semantic catalog

Collector, persistence veya query bir metric ID'yi serbest string olarak kullanamaz. Her metric
`MetricId` ve versioned `MetricDefinition` ile kayıtlıdır. Definition bütün zorunlu alanları ve
uygulanmayan conditional alanlar için açık `None`/`not_applicable` değerlerini taşır.

- `snapshot` ve `cumulative` period boyunca sum edilmez; `last_valid` kullanır.
- `flow` uyumlu dönemlerde `sum` kullanır.
- `ratio`, pay ve payda üzerinden period/Brand rollup sırasında `recompute` edilir.
- Missing değer `0` yapılmaz; `None` aynen korunur.
- Cumulative total ve delta-derived flow farklı metric ID'leridir.
- Derived metric kaynakları, operator, operator version ve pencere taşır.
- İlk cumulative sample ve counter reset açık policy olmadan flow üretmez.
- Katalog dışı metric collection, persistence ve query construction aşamasında fail-closed olur.

## Persistence ve model registry

Metric, content, comment ve media portları canonical application kayıtları kullanır. İlk adapter
mevcut production şemasına binary-compatible SQL uygular; yeni DDL üretmez.

- Eski tablo/kolon adları yalnız `infrastructure/persistence/legacy_socialmedia` içindedir.
- Yerel explicit SQLAlchemy registry dynamic source-project model yüklemez.
- Account, Brand ve platform eşleşmesi mutation transaction'ı içinde doğrulanır.
- Bilinen historical platform değerleri adapter girişinde canonical ID'ye çevrilir; raw değer
  domain, API veya log'a taşınmaz. Unknown değer `unsupported_platform` olur ve echo edilmez.
- Account-level ve breakdown metric satırları V1 partial unique index conflict target'larıyla
  idempotent upsert edilir.
- Query metotları transaction mutation yapmaz.
- Bütün mutation metotları merkezi `WritePolicy` ister; dormant modda reddedilir.

## TokenVault ve CredentialStore

OAuth access/refresh tokenları plaintext DB, file, fixture artifact veya log'a yazılamaz.

- Format: version `1`, `AES-256-GCM`, full 128-bit authentication tag.
- Key: yalnız injected active key ID + base64 encoded 32-byte keyring.
- Nonce: her encryption için OS CSPRNG'den 96 bit.
- Nonce reuse: aynı DB transaction'ında
  `v2:credential-nonce:<key_id>:<sha256_nonce>` atomik claim; bounded retry sonrası fail-closed.
- AAD: format version, product ID, platform, connection ID ve token kind için canonical UTF-8
  length-prefixed encoding.
- Payload: format/algorithm/key ID/nonce/ciphertext/expiry/revoke metadata; plaintext token yok.
- Missing/unknown/wrong key, invalid format, moved ciphertext veya authentication failure
  secretsız hata koduyla fail-closed olur.
- Revoke sonrası read token döndürmez.
- Rotation eski key ile in-memory decrypt, active key ile atomik re-encrypt yapar; dry-run
  inspected/eligible count döndürür. Failed nonce claim eski ciphertext'i rollback ile korur.

## CheckpointStore

Provider cursor/watermark state'i typed `ProviderCheckpoint` olarak
`social_projection_state` namespace'inde tutulur.

- Initial version `1`; sonraki update exact expected-version + 1 ister.
- Stale update güncel checkpoint'i değiştirmez.
- Cursor ve watermark payload boyutları bounded'dır.
- Idempotency claim hash-only key, TTL ve atomic conflict davranışı taşır.
- Read yolu satır üretmez veya güncellemez.

## Meta transport ve rate guard

- Egress default-off'tur; explicit runtime gate açılmadan request oluşmaz.
- Origin yalnız `https://graph.facebook.com`, API version explicit ve relative path bounded'dır.
- Token Authorization header'ındadır; URL/query parametresine alınmaz ve hata metnine girmez.
- Timeout/retry sayısı bounded; transient `429/5xx` exponential backoff ve `Retry-After`
  sözleşmesini uygular.
- Usage pressure eşikleri V1 davranış girdisini korur: `70` throttle, `85` degraded window,
  `92` cooldown. Provider limit kodları cooldown circuit'i açar.
- Testler yalnız injected fake HTTP transport kullanır; gerçek provider egress yoktur.

## Worker runtime

- Dormant worker config provider egress ve automated schedule'ı kapalı tutar.
- Automated schedule Faz 4 kodunda açılmaya çalışılırsa configuration error oluşur.
- Local manual egress yalnız disposable `development + writes_enabled` policy ile kurulabilir.
- Manual selection ayrıca exact `available` capability ister.
- Bootstrap registry nedeniyle normal runtime'da hiçbir provider worker seçilemez.

## Architecture gate

CI aşağıdakileri build blocker olarak uygular:

- kaynak proje import/path bağımlılığı;
- 250 satırı aşan provider adapter dosyası veya tek devasa platform adapter;
- schema identifier'ın compatibility adapter dışına çıkması;
- metric ID'nin catalog dışı literal olarak yeniden üretilmesi;
- query package içinde mutation çağrısı;
- canonical vocabulary veya secret leak bulgusu;
- source-project baseline drift'i.
