# Social Media V2 Downstream Handoff Log

## Güncel durum — 2026-07-14

- Faz 0–9: **KAPALI, sertifikasyon kapıları yeşil**.
- Son canonical doğrulama: `./scripts/quality/fase9_offline_release_check.sh`.
- Faz 9 sonucu: migration-built PostgreSQL fingerprint eşleşti; full backend `121 passed`,
  hedefli rehearsal `5 passed`, Faz 8 backend regression `15 passed`, frontend `13 passed`,
  Chromium `8 passed` (`4` intentional skip) ve npm audit `0 vulnerabilities`.
- **V2 Release Candidate Complete** gate'i kapandı; bu production aktivasyonu değildir.
- V2 hâlâ dormant; production DB/provider/traffic/schedule, source-project write ve Git push yoktur.
- Sonraki production/cutover adımı yalnız ayrı açık kullanıcı onayıyla başlayabilir.
- Ayrıntı: `docs/fase9/Faz9_Offline_Release_Rehearsal_Report.md`.

## Hedef ve bağlam

- Proje: `/home/api/colab_scripts/SocialMediadownstream`
- Canonical plan: [SOCIAL_MEDIA_V2_MASTER_PLAN.md](/home/api/colab_scripts/SocialMediadownstream/docs/SOCIAL_MEDIA_V2_MASTER_PLAN.md)
- Bu dosya: yalnızca faz bazlı ilerleme, kararlar, riskler, onay ihtiyaçları ve kanıt kayıtları için kullanılacaktır.
- V1/diğer projeler (SocialMedia, Accumulate, performance_marketing) hiçbir zaman düzenlenmeyecektir.
- Çalışma modu: V2 dormant; production erişimi/aktifasyonlar phase kapanmadan yapılmayacaktır.

## Hedeflenen akış

1. Planı kaynak ve tek referans alarak ilerlemek.
2. Her fazı, master plandaki teslimatlar + çıkış kapısıyla birlikte işlemek.
3. Her faz bittiğinde handoff’a:
   - Gerçekleşenler
   - Kanıt listesi
   - Kararlar
   - Riskler
   - Bir sonraki adım
   yazmak.
4. Faz geçişi yalnız ilgili çıkış kapısı temiz olduğunda yapılacak.

## Tarih

- `2026-07-10`

## Günlük durum özeti

- `13:45` — `handoff.md` dosyası başlangıçta boş olarak tespit edildi (0 byte).
- `13:46` — Master planın faz başlıkları incelenerek fazlara göre ilerleme şablonu çıkarıldı.
- `13:48` — Mevcut turda ilk handoff sürümü oluşturuldu; aktif takip formatı tanımlandı.
- `13:58` — `Faz 1` kapanış mini-raporu kontrol edildi: `fase1_bootstrap_check.sh`, `compileall` ve
  bağımsız `fase1_smoke_check.py` çalıştırıldı; statik kapanış kriterleri geçti.
- `14:05` — `Faz 2 (SSO/Webhook)` için başlangıç artefaktları eklendi: sözleşme, session/provisioning portları ve authority payload parser iskeleti.

## Fazların durumu

### Faz 0 — Baseline ve koruma

Status: **EN AKTİF / BOOTSTRAP AŞAMASI**

Plana göre teslimatlar:

- Kaynak repo immutable snapshot raporu
- canonical GitHub remote doğrulaması
- V1 committed HEAD migration baseline referansı
- dirty behavior inventory + hash
- generic entegrasyon rehberinin migration input olarak ayrımı
- downstream-only branch
- source-write guard scripti

Bu turda yapılanlar:

- `SOCIAL_MEDIA_V2_MASTER_PLAN.md` içindeki Faz 14 başlıkları doğrulandı.
- Handoff formatı ve log şablonu oluşturuldu.

Henüz tamamlanmayanlar (bir sonraki adım):

- Kaynak repo snapshot ve hash envanterinin çıkarılması.
- Canonical remote doğrulaması ve repo bootstrap raporunun yazılması.
- `source-write guard` için uygulanacak temel guard dosyasının taslak planı ve yerleştirilmesi.

Çıkış kapısı durumu:

- Şimdilik **KAPALI** (planlama tamamlandı, teknik deliverable henüz tamamlanmadı).

Riskler:

- Kaynak projelerde local dirty durum varsa yanlışlıkla “değişiklik” algısı yanlış yorumlanabilir.
- Planın sonraki adımlarının her biri önceki snapshot bütünlüğüne bağımlı.

Gereken onay:

- Faz 0'ın teknik teslimatını başlatmam için **onay beklenmiyor**; direkt devam edebiliriz.

### Faz 1 — Güvenli bootstrap

Status: **KISMİ KAPALI (runtime testi bağımlı bekleme)**

Teslimatlar:

- fail-closed env/DB resolver
- production host/DB guard
- `SOCIAL_WRITES_ENABLED=false` default
- lock dosyaları
- secretsız env örnekleri
- canonical package scaffold
- canonical vocabulary guard
- command/query boundary + WritePolicy
- dependency/import boundary testleri

Bu faz başlamadan önce Faz 0 kapanışı gerekir.

Çıkış kapısı: downstream kaynak bağımsız, production DB erişimi olmadan import/build mümkün.

### Faz 2 — SSO ve webhook contract

Status: **AKTİF — hazırlık**

Teslimatlar:

- SSO verify/consume/local session
- HMAC, nonce/JTI/idempotency
- provisioning parser + projection
- SessionStore ve ProvisioningStore portları
- sözleşme dokümanı ve replay testleri

Çıkış kapısı: disposable PostgreSQL üzerinde SSO/webhook testleri yeşil.

Durum notu:

- `docs/contracts/social-media-v2-sso-provisioning.md` dokümanı oluşturuldu.
- Bu fazda runtime endpoint ve persistent store implementasyonuna geçilmeden önce sözleşme kapanışı ve test stratejisi onayı bekliyor.

Başlangıç kod iskeleti:

- `backend/app/application/ports/session_store.py`
- `backend/app/application/ports/provisioning_store.py`
- `backend/app/application/services/sso_payload.py`
- `backend/app/domain/authority/models.py`

### Faz 3 — Parent/child authority projection

Status: **BEKLİYOR**

Teslimatlar:

- brand shell + snapshot
- parent/child/hidden-parent model
- brand-family API
- cross-brand yetki testleri

Çıkış kapısı: parent rollup izinli child listesiyle doğru çalışır.

### Faz 4 — Backend bağımsızlaştırma

Status: **BEKLİYOR**

Teslimatlar:

- local transport/rate guard
- local metric/content/comment/media persistence
- platform adapter sınırı (fb/ig/tiktok)
- capability portları
- TikTok Business v1.3 account-holder adapter
- App ID/endpoint/env sözleşmesi
- TokenVault/CredentialStore, CheckpointStore portları
- metric semantic catalog
- dormant worker config

Çıkış kapısı: import/path bağımlılığı, monolit adapter ve katalog dışı metric tespiti yok.

### Faz 5 — Collector parity

Status: **BEKLİYOR**

Teslimatlar:

- fake Meta server
- golden fixture
- v1 karşılaştırma suite
- TikTok token akışı ve scope doğrulaması
- crash/restart-rate-limit testleri

Çıkış kapısı: metric/status/request farkı sıfır.

### Faz 6 — Dashboard ve operasyon API'leri

Status: **BEKLİYOR**

Teslimatlar:

- Overview/Facebook/Instagram/TikTok dashboard servisleri
- media proxy
- accounts/connections/sync/settings/insights API
- parent rollup
- response contract testleri

Çıkış kapısı: feature matrix parity tamam.

### Faz 7 — Frontend shell

Status: **BEKLİYOR**

Teslimatlar:

- performance-style shell
- sidebar/topbar + brand selector
- SSO loading/login/logout
- capability-driven navigation
- localhost:3010

Çıkış kapısı: desktop/mobile shell referans ile uyumlu.

### Faz 8 — Social sayfalar ve Settings

Status: **KAPALI — canonical sertifikasyon yeşil**

Teslimatlar:

- Overview / FB / IG / TikTok sayfaları
- TikTok ve sosyal kartlar
- yalnız 3 platformlu settings
- owner gated `/settings/tiktok/connect`
- client/ARS/legacy terim temizliği

Çıkış kapısı: ürün parity checklist ve erişilebilirlik testleri yeşil.

### Faz 9 — Offline release rehearsal

Status: **KAPALI — canonical sertifikasyon yeşil**

Teslimatlar:

- tam test turu
- production schema rehearsal
- dormant unit taslakları
- cutover/recovery checklist
- owner activation dry-run
- fake provider + fake SSO doğrulaması

Çıkış kapısı: release candidate hazır, production write/activasyon yok.

### V2 Release Candidate Complete gate

Status: **TAMAMLANDI — production hâlâ dormant**

Tanım:

- Faz 0–9 tamamlandığında alırız.
- V1 production yazım sorumluluğu dokunulmaz.
- V2 production DB veya provider egress ile çalışmaz.
- Writer cutover'a geçişe hazır ancak üretim aktifleştirme yapılmamış kabul edilir.

## Bu tur karar defteri (sadece önemli kararlar)

- `handoff.md` başlangıçta boştu, bu yüzden ilk defa detaylı ilerleme günlüğü burada standart şekilde kuruluyor.
- Sonraki bütün notlar ChatGPT 5.3 tarafında kullanılmak üzere planla uyumlu, açık ve bölümlenmiş tutulacak.
- Sosyal medya terim standardizasyonu: `Brand`, `Parent Brand`, `Child Brand`, `platform` sadece `facebook|instagram|tiktok`.
- `Organic`, `client`, `ARS`, `Media Planner` ve legacy rol listesi bu faz akışında yeni runtime'a taşınmayacak.

## İleri adım (hedeflenen geçiş)

- Faz 0'ın teknik teslimatlarını sırayla tamamlayarak `Faz 0 — Baseline ve koruma`yı kapatacağım.
- Faz 0 kapanınca doğrudan `Faz 1 — Güvenli bootstrap`a geçiş yapılacak.
- Her yeni faz başlangıcında handoff güncellenecek; her kapanışta çıkış kapısı metinle belgelenip imzalı şekilde kaydedilecek.

## Faz 0 — Baseline ve koruma (Güncel kapanış durumu)

Tarih: 2026-07-10

### Teslimat kanıtları

- `source-write guard` scripti oluşturuldu: `scripts/source_write_guard.sh`
- Kaynak immutable envanterler çıkarıldı ve hashlendirme dosyaları üretildi:
  - `docs/fase0/baseline_SocialMedia_files.txt`
  - `docs/fase0/baseline_Accumulate_files.txt`
  - `docs/fase0/baseline_performance_marketing_files.txt`
  - `docs/fase0/source_manifest_hashes.sha256`
- Faz 0 rapor dosyası oluşturuldu: `docs/fase0/Faz0_Baseline_and_Guard_Report.md`
- Guard doğrulaması çalıştırıldı:
  - sonuç: `SOURCE WRITE GUARD PASS: downstream-only write boundary enforced and immutability baselines match.`

### Teknik detay özetleri

- Manifest hash sonuçları:
  - SocialMedia: `a8bc39bac6d75625c56d12a01f83f996dd5dd3619eebbf0f812ac3e891f57061`
  - Accumulate: `3ab4c28e603f6c05322612000e8d34183d6b1d292111f23400daf98c176212b2`
  - performance_marketing: `78773bcb40daa3be9310d4e403fa2ef55b4f965c56035ac3d8cdec99abb1be69`
- `SocialMediaV2` dizininde nested git kökü kurularak canonical bootstrap hedefi tamamlandı; bu madde kapanışta güncellenmiştir.
- Kaynak projelerin origin adresleri plan doğrultusunda okundu:
  - SocialMedia: `https://github.com/abbasalipanah/SocialMedia.git`
  - Accumulate: `git@github-accumulate:dexcore/accumulate.git`
  - performance_marketing: `git@github.com:abbasalipanah/performance_marketing.git`
  - Hedef repo: `https://github.com/abbasalipanah/SocialMediaV2.git`

### Çıkış kapısı değerlendirmesi

- [x] kaynak snapshot listesi ve hashleri üretildi
- [x] source-write guard scripti üretildi
- [x] guard doğrulaması başarıyla geçti
- [ ] downstream git bootstrap (local `origin` doğrulaması ve bağımsız branch temeli)

### Risk / Not

- `ls-remote --heads origin` çağrısında branch görünmeme durumu raporlandı; remote repo’nun ilk import aşamasında doğrulanacaktır.
- İleride guard, mutasyon öncesi “lockfile/manifest drift check” için doğrudan çağrılabilir.

### Faz 0 sonrası karar

- Fiziğin teknik olarak çoğunluğu tamamlandı; kalan tek blok `SocialMediadownstream` için git bootstrap kurulumu (canonical remote + branch modeli).
- Onay alındığında Faz 0 çıkış kapısını kapatıp Faz 1’e geçiyoruz.

## Faz 0 — Kapanış ve Faz 1 başlatma kararı (2026-07-10)

### Kapanış kararı

`Faz 0 — Baseline ve koruma` aşağıdaki maddelerle tamamlandı kabul edildi:

- immutable envanterlerin hashlenmesi tamam.
- source-write guard doğrulaması çalıştırıldı ve PASS alındı.
- `SocialMediaV2` içinde nested git bootstrapping gerçekleştirildi.
- canonical origin ayarlandı: `https://github.com/abbasalipanah/SocialMediaV2.git`
- nested repo root doğrulandı: `/home/api/colab_scripts/SocialMediadownstream`
- dal `main` ile başlatıldı.

### Kalan açık

- `ls-remote` çıktısında `origin` branch referansı görünmedi (remote tarafı boş/erişimsiz olabilir); bu durum ileride ilk import/push planıyla doğrulanacak.

### Yeni durum

- `Faz 0` → **KAPALI**
- `Faz 1` → **AKTİF**
- `Faz 2` → **AKTİF (hazırlık)**

### Faz 1 için başlangıç eylemleri

- fail-closed env/DB resolver taslağı
- production host/DB guard temel dosya iskeleti
- `SOCIAL_WRITES_ENABLED=false` başlangıç dayanağı
- secretsız env örnekleri için yapı dosyaları
- canonical package scaffold ve guard zinciri
- Sözleşme taslağı (Faz 2): `docs/contracts/social-media-v2-sso-provisioning.md`

## Faz 1 — Güvenli bootstrap (Başlangıç çıkışı) 2026-07-10

### Güncel teslimat durumu

Durum: **AKTİF (statik kapanış geçerli, runtime testler beklemede)**

#### Tamamlananlar

- `backend/` paket iskeleti kuruldu.
- Fail-closed bootstrap için `SOCIAL_WRITES_ENABLED=false` varsayılanlı config eklendi:
  - `backend/.env.example`
  - `backend/src/social_media_v2/config/settings.py`
  - `backend/src/social_media_v2/foundation/guard.py`
  - `backend/src/social_media_v2/core/write_policy.py`
- Canonical package scaffold:
  - `backend/app/` ve alt yapı ağacı
  - `frontend/src/` `app`, `api`, `auth`, `layout`, `routes`, `ui`, `features`
- Command/query boundary ve platform domain:
  - `backend/src/social_media_v2/core/boundary.py`
  - `backend/src/social_media_v2/domain/platforms.py`
  - `backend/src/social_media_v2/api/routes.py`
- Canonical vocabulary guard:
  - `backend/src/social_media_v2/foundation/vocabulary_guard.py`
- Paket ve lock başlangıçları eklendi:
  - `backend/pyproject.toml`
  - `backend/requirements.txt`
  - `backend/requirements.lock`
  - `frontend/package.json`
  - `frontend/package-lock.json`
- Frontend lokal geliştirme örnekleri eklendi:
- `frontend/.env.example`
- `frontend/README.md`
- `frontend/src/main.tsx`
- App giriş katmanı:
  - `backend/src/social_media_v2/app.py`
  - `backend/src/social_media_v2/main.py`
- Faz 1 raporları eklendi:
  - `docs/fase1/Faz1_Safe_Bootstrap_Report.md`
  - `docs/fase1/source_write_guard_report.md`
  - `docs/fase1/Faz1_Import_and_Write_Guard_Report.md`
- Test temeli eklendi:
  - `backend/tests/test_bootstrap_guard.py`
  - `backend/tests/test_bootstrap_contracts.py`
  - `backend/tests/conftest.py`
- `backend/tests/test_import_boundaries.py`
- `backend/tests/test_command_query_boundary.py`
- `backend/tests/test_vocabulary_guard.py`
- Faz 1 kalite çalıştırıcı script'i eklendi:
  - `scripts/quality/fase1_bootstrap_check.sh`
  - `scripts/quality/fase1_smoke_check.py`
  - `docs/fase1/Faz1_Quality_Checklist.md`
  - `docs/fase1/Faz1_Closure_Delta.md`
  - `scripts/quality/check_canonical_vocabulary.py`

#### Bekleyenler

- `SOCIAL_DB_HOST`/`SOCIAL_DB_URL` için daha net allowlist/denylist modeline geçiş.
- `pytest`/`fastapi` yüklü olmadığından `python3 -m pytest ...` runtime testleri beklemede.

#### Çıkış kapısı değerlendirmesi

- [x] fail-closed env/DB resolver temeli kuruldu
- [x] production write defaultu kapalı (false)
- [x] `Faz 0`-doğruluğuna uyumlu doğrudan downstream-only bootstrap
- [x] `scripts/quality/fase1_bootstrap_check.sh` — geçiş doğrulandı
- [x] `python3 scripts/quality/fase1_smoke_check.py` — statik kriterler geçti
- [ ] dependency/test/certification checklist run (CI hook ve validation) — runtime testleri için pytest/fastapi gerekli, ortam hazır değil
- [x] backend app import boundary + write-path guard testleri taslaklandı ve yazıldı

### Özet

- Faz 1 kalan doğrulama adımı `python3 -m pytest backend/tests/test_bootstrap_*` ve runtime kontrollerinin çalıştırılmasıdır.
- Ortamda `pytest` ve `fastapi` yüklü olmadığından bu adım beklemektedir: ` /usr/bin/python3: No module named pytest`.
- Statik kapanış için `python3 scripts/quality/fase1_smoke_check.py` çalıştırıldı ve geçti.

### Not

- `SOCIAL_MEDIA_V2_MASTER_PLAN.md` faz 1 hedefleri doğrultusunda sadece temel güvenli mimari iskelet bırakıldı; işlevsel endpointler sonraki fazlara ertelendi.

### Faz 2 başlangıç iskeleti (hazırlık tamamlandı)

- Sözleşme dokümanı tamamlandı:
  - [docs/contracts/social-media-v2-sso-provisioning.md](/home/api/colab_scripts/SocialMediadownstream/docs/contracts/social-media-v2-sso-provisioning.md)
- Canonical port ve domain iskeleti eklendi:
  - [backend/app/application/ports/session_store.py](/home/api/colab_scripts/SocialMediadownstream/backend/app/application/ports/session_store.py)
  - [backend/app/application/ports/provisioning_store.py](/home/api/colab_scripts/SocialMediadownstream/backend/app/application/ports/provisioning_store.py)
  - [backend/app/domain/authority/models.py](/home/api/colab_scripts/SocialMediadownstream/backend/app/domain/authority/models.py)
- SSO payload parser eklenmesi:
  - [backend/app/application/services/sso_payload.py](/home/api/colab_scripts/SocialMediadownstream/backend/app/application/services/sso_payload.py)

### Faz 1 ek çıktı (2026-07-10)

- App giriş katmanı:
  - [backend/src/social_media_v2/app.py](/home/api/colab_scripts/SocialMediadownstream/backend/src/social_media_v2/app.py)
  - [backend/src/social_media_v2/main.py](/home/api/colab_scripts/SocialMediadownstream/backend/src/social_media_v2/main.py)
- Paket/önbellek güvenliği:
  - [backend/src/social_media_v2/core/__init__.py](/home/api/colab_scripts/SocialMediadownstream/backend/src/social_media_v2/core/__init__.py)
  - [backend/src/social_media_v2/foundation/__init__.py](/home/api/colab_scripts/SocialMediadownstream/backend/src/social_media_v2/foundation/__init__.py)
- Test iskeleti:
  - [backend/tests/test_bootstrap_guard.py](/home/api/colab_scripts/SocialMediadownstream/backend/tests/test_bootstrap_guard.py)
- Bu aşama sonrası Faz 1 rapor ekleri:
  - `docs/fase1/Faz1_Safe_Bootstrap_Report.md`
  - `docs/fase1/source_write_guard_report.md`

## Authoritative durum güncellemesi — 2026-07-13

Bu bölüm önceki `runtime testleri beklemede` kayıtlarının yerini alan güncel durumdur.

### Faz 0 — KAPALI

- Eski path-only baseline yetersiz bulundu ve retired edildi.
- Branch, HEAD, origin, dirty inventory, tracked diff ve file-content hashlerini birlikte
  doğrulayan v2 baseline oluşturuldu.
- Mevcut source dirty state değiştirilmeden kaydedildi.
- Source guard başlangıç ve final doğrulamasında geçti.
- Generic entegrasyon rehberi canonical repository artifact'inden çıkarıldı.
- Canonical downstream origin ve bağımsız Git root doğrulandı.

### Faz 1 — KAPALI

- Runtime tek `backend/app` canonical package ağacına taşındı; paralel `backend/src` kaldırıldı.
- Production DB, remote DB, production-benzeri config, erken TikTok gate ve secret yükleme
  kuralları fail-closed hale getirildi.
- SHA-256 hashli Python runtime/development lock'ları ve resolved npm lock üretildi.
- Backend: Ruff temiz, `18 passed`.
- Frontend: clean `npm ci`, React 19 + TypeScript strict + Vite 7 production build geçti.
- Source ve build artifact vocabulary guard geçti.
- `scripts/quality/fase1_bootstrap_check.sh` tam certification sonucu PASS.

### Faz 2 — SIRADAKİ / BAŞLAMADI

Mevcut contract, port, model ve parser dosyaları yalnız hazırlık girdisidir. HMAC, SSO consume,
local session, replay/idempotency, persistent adapter, webhook route ve disposable PostgreSQL
testleri henüz uygulanmadığı için Faz 2 aktif veya kısmi kapalı sayılmaz.

Bir sonraki izinli iş: Faz 2 normatif contract'ını master plan §7–8 ile birebir kapatmak ve
disposable PostgreSQL test harness'ını kurmak. Faz 3 feature geliştirmesine Faz 2 gate'i yeşil
olmadan geçilemez.

## Authoritative durum güncellemesi — 2026-07-13 / Faz 2 kapanış adayı

Bu bölüm önceki `Faz 2 — SIRADAKİ / BAŞLAMADI` kaydının yerini alan güncel durumdur.

### Faz 2 — UYGULAMA TAMAM / EXIT GATE BLOKE

- Gerçek upstream nested `sso_contract` v1 şekli doğrulanmaktadır.
- SSO consume, one-time JTI, hash-only local session ve session revoke tamamlandı.
- Signed provisioning, nonce/event replay, version ordering ve typed parser tamamlandı.
- PostgreSQL projection adapterı ve tam disposable test harness'ı tamamlandı.
- Ruff, wheel, frontend build, vocabulary guard ve disposable PostgreSQL üzerindeki `33 passed`
  sonucu yeşildir.
- Full certificate, downstream dışındaki `performance_marketing` reposuna baseline sonrası gelen
  yeni untracked CSV nedeniyle source guard'ın ilk adımında fail-closed durmuştur.
- External dosyaya ve Faz 0 baseline'ına müdahale edilmedi; checkpoint commit'i oluşturulmadı.

Canonical ayrıntı ve blokaj kanıtı:
`docs/fase2/Faz2_SSO_Provisioning_Report.md`.

Faz 3, source state hakkında açık karar verilip full Faz 2 sertifikası geçmeden başlamaz.

## Authoritative durum güncellemesi — 2026-07-14 / Schema compatibility düzeltmesi

Bu bölüm önceki Faz 2 kapanış adayındaki PostgreSQL adapter kanıtını düzeltir.

### Faz 2 — UYGULAMA DÜZELTİLDİ / EXIT GATE BLOKE

- İlk PostgreSQL test fixture'ının gerçek V1 `social_projection_state` şemasını temsil etmediği
  tespit edildi: fixture `payload` ve `expires_at` kolonlarını üretirken mevcut şema
  `payload_json` kullanır ve ayrı expiry kolonu içermez.
- Adapter mevcut `payload_json` kolonuna geçirildi; TTL typed payload içinde tutuldu ve yeni DDL
  ihtiyacı kaldırıldı.
- Fixture, V1 kolon/default/key sözleşmesiyle değiştirildi; gerçek kolon kopyasındaki önceki
  `UndefinedColumn` hatası giderildi.
- `projection_key varchar(255)` sınırı event/entity parserında fail-closed uygulanıp negatif
  testlerle doğrulandı.
- Disposable PostgreSQL ile backend `36 passed`; Ruff, wheel, frontend clean build, vocabulary
  scan ve `git diff --check` yeşildir.
- Source guard hâlâ kırmızıdır: `performance_marketing` HEAD'i baseline'daki `7d79116...`
  değerinden `9d93374...` değerine ilerlemiş, content file count `398` yerine `418` olmuştur ve
  yeni untracked CSV bulunmaktadır.

Faz 2 ancak güncel external source state için açık kullanıcı kararı, gerekiyorsa onaylı baseline
yenileme ve tek koşuda yeşil full certification sonrasında kapatılabilir. Faz 3 başlamamıştır.

## Authoritative durum güncellemesi — 2026-07-14 / Faz 2 kapanışı

### Faz 2 — KAPALI

- Kullanıcı güncel `performance_marketing` HEAD ve untracked inventory'sini beklenen source state
  olarak açıkça onayladı.
- Faz 0 v2 baseline acknowledgement ile yenilendi; source projelere write yapılmadı.
- `scripts/quality/fase2_contract_check.sh` tek koşuda tamamen geçti.
- Başlangıç ve final source guard adımları yeşildir.
- Faz 1 certification yeniden geçti.
- Disposable PostgreSQL suite sonucu `36 passed` oldu.
- Schema-compatible `payload_json` adapterı, SSO/session, HMAC provisioning, replay/version
  ordering ve session revoke teslimatları Faz 2 gate'ini karşılamaktadır.

### Faz 3 — AKTİF

İzinli sıradaki kapsam parent/child authority projection'dır: Brand shell/access projection,
full snapshot semantiği, parent/child/hidden-parent model, brand-family API ve cross-brand
authorization testleri. Faz 4 çalışması Faz 3 çıkış kapısı yeşil olmadan başlamaz.

## Authoritative durum güncellemesi — 2026-07-14 / Faz 3 kapanışı

### Faz 3 — KAPALI

- Typed Brand shell ve user–Brand access projection'ları tamamlandı.
- Full snapshot atomic replacement, empty snapshot ve stale version davranışı gerçek PostgreSQL
  üzerinde doğrulandı.
- Hidden parent yalnız rollup shell'i olarak modellendi; mevcut gerçek shell placeholder ile
  overwrite edilmez.
- Parent rollup yalnız izinli active descendant'ları içerir; unrelated Brand/sibling scope'a
  sızmaz.
- Incremental membership, entitlement + app access olmadan erişim açamaz.
- Concrete mutation write access ister; read-only veya rollup mutation fail-closed olur.
- `/api/workspace/brands` ve session current-authority doğrulaması eklendi.
- `scripts/quality/fase3_authority_check.sh`: full suite `44 passed`, targeted suite `20 passed`,
  source guards ve bütün build/artifact kontrolleri yeşil.

Canonical kanıt: `docs/fase3/Faz3_Authority_Projection_Report.md`.

### Faz 4 — SIRADAKİ

İzinli sıradaki kapsam backend bağımsızlaştırmadır: küçük platform capability portları, local
Meta/TikTok adapter sınırları, schema-compatible persistence, TokenVault/CredentialStore,
CheckpointStore, metric semantic catalog, explicit model registry ve dormant worker config.

## Authoritative durum güncellemesi — 2026-07-14 / Faz 5 kapanışı

### Faz 4 — KAPALI

- Backend bağımsızlaştırma `510a98e` local checkpoint commit'i ile donduruldu.
- Faz 4 canonical raporu ve certification sonucu geçerlidir.

### Faz 5 — KAPALI

- Gerçek V1 Meta transport oracle'ı ve ayrı V2 candidate subprocess'i deterministic localhost
  fake provider üzerinde aynı pagination ve `500 → 429 → 200` sequence'ini üretti.
- Gerçek V1 `metrics_store` oracle'ı ile V2 persistence candidate iki ayrı disposable PostgreSQL
  database üzerinde çalıştı; metric/content persistence exact karşılaştırıldı.
- Facebook/Instagram profile, daily metrics, content, stories, comments, audience ve media
  capability'leri küçük adapter ve collector servislerine ayrıldı.
- Page-level durable checkpoint/replay, atomic media write, bounded retry/rate davranışı, D-1
  coverage, 30d + kalan 60d backfill ve follower history sözleşmeleri test edildi.
- TikTok Business Accounts v1.3 token/profile/video parser'ları, scope gate'i, exact callback ve
  PostgreSQL üzerinde atomic single-use OAuth state tamamlandı.
- SocialMedia source dirty davranışları hash-bound envanterle V2 karşılıklarına bağlandı; source
  projeler değiştirilmedi.
- `scripts/quality/fase5_collector_parity_check.sh`: full disposable PostgreSQL suite
  `108 passed`, hedefli suite `35 passed`; Ruff, secret/vocabulary/source guard temiz.
- Canonical differential sonucu request sequence, metric ID/value, status/summary,
  content/comment/media row ve media SHA-256 için `0` farktır.

Canonical kanıt: `docs/fase5/Faz5_Collector_Parity_Report.md`.

### Faz 6 — AKTİF

İzinli sıradaki kapsam Overview/Facebook/Instagram/TikTok dashboard servisleri, güvenli media
proxy, yalnız üç platform için accounts/connections/sync/settings/insights API'leri, backend
parent rollup ve response contract testleridir. Faz 7 frontend shell çalışması Faz 6 feature
matrix çıkış kapısı yeşil olmadan başlamaz.

## Authoritative durum güncellemesi — 2026-07-14 / Faz 6 kapanışı

### Faz 5 — KAPALI

- Collector parity `9648db7` local checkpoint commit'i ile donduruldu.
- Faz 5 canonical raporu ve sıfır-difference sonucu geçerlidir.

### Faz 6 — KAPALI

- Overview, Facebook, Instagram ve TikTok dashboard servisleri typed response DTO'larıyla
  tamamlandı.
- Snapshot/flow/cumulative/ratio ve previous-period aggregation yalnız metric catalog
  semantiğiyle yapılır; missing metric sahte `0` olmaz.
- Parent Brand rollup yalnız authorized active child Brand/account kapsamını backend'de toplar;
  arbitrary Brand ve account filter erişimi fail-closed olur.
- Platform accounts, Settings Brands/Social Accounts/Brand Links/connections/sync-jobs,
  readiness, stored insights ve workspace capabilities API'leri eklendi.
- Instagram media proxy yalnız persisted local dosyayı root confinement, size ve SHA-256
  doğrulamasından sonra servis eder; provider fallback veya GET-side persistence yoktur.
- Sync/backfill/disconnect command route'ları same-origin + concrete write scope + merkezi
  WritePolicy arkasında cutover öncesi fail-closed kalır.
- Response modelleri OpenAPI component schema olarak yayınlanır; canonical platform enum exact
  üçlü seti korunur.
- Live feature matrix'te internal audit store dürüst `unavailable`, PNG export ise Faz 8 frontend
  işi olarak işaretlendi; sahte veri/işlev üretilmedi.
- `scripts/quality/fase6_dashboard_operations_check.sh`: full disposable PostgreSQL suite
  `115 passed`, hedefli suite `19 passed`; Ruff, secret/vocabulary/source guard temiz.

Canonical kanıt: `docs/fase6/Faz6_Dashboard_Operations_Report.md`.

### Faz 7 — AKTİF

İzinli sıradaki kapsam Performance-style responsive shell, sidebar/topbar, Brand/child/account
selector'ları, SSO loading/login/logout, capability-driven navigation, gerçek routing ve Vite
strict development port `3010`'dur. Faz 8 sosyal sayfa/Settings feature uygulaması Faz 7 shell
çıkış kapısı yeşil olmadan başlamaz.

## Authoritative durum güncellemesi — 2026-07-14 / Faz 7 kapanışı

### Faz 6 — KAPALI

- Dashboard/operations API kapanışı `e6bc35b` local checkpoint commit'i ile donduruldu.
- Faz 6 canonical raporu ve disposable PostgreSQL kanıtı geçerlidir.

### Faz 7 — KAPALI

- React 19 + strict TypeScript shell; AuthProvider, BrandScopeProvider, TanStack Query ve gerçek
  nested/lazy routing ile tamamlandı.
- Performance-style desktop fixed sidebar ve `<1024px` mobile drawer/backdrop davranışı
  reference kaynakları değiştirilmeden yeniden uygulandı.
- Parent/child/all-child Brand scope ve platform-account selector'ları storage/reset/invalid
  selection kurallarıyla tamamlandı; rollup frontend'de merge edilmez.
- Navigation availability backend `linked_account_count + capability` cevabından gelir;
  permission role string'inden türetilmez.
- SSO loading/login/logout/profile ve accessible focus-trapped popover davranışı tamamlandı.
- OpenAPI export → generated TypeScript → Zod runtime validation zinciri eklendi.
- Vite development portu `3010` ve `strictPort=true`; PWA/service worker yok.
- `scripts/quality/fase7_frontend_shell_check.sh`: Faz 6 PostgreSQL regression `115 passed`,
  hedefli API suite `19 passed`, frontend `9 passed`, Playwright Chromium `4 passed`, build,
  audit, secret/vocabulary/source guard temiz.

Canonical kanıt: `docs/fase7/Faz7_Frontend_Shell_Report.md`.

### Faz 8 — AKTİF

İzinli sıradaki kapsam Overview, Facebook, Instagram (Stories aynı sayfa altında), TikTok,
AI Insights/export, yalnız üç social platformlu table-first Settings/Brand Setup drawer,
owner/fresh-SSO-gated TikTok activation, capability izinli audit/manual repair ve bütün
loading/error/empty/partial state'leridir. Faz 9 offline release rehearsal çalışması Faz 8 ürün
parity ve accessibility kapısı yeşil olmadan başlamaz.

## Authoritative durum güncellemesi — 2026-07-14 / Faz 9 ve RC kapanışı

### Faz 8 — KAPALI

- Social sayfalar, Settings, owner handoff ve accessibility kapanışı `e3da54d` local checkpoint
  commit'i ile donduruldu.
- Faz 8 canonical ürün ve browser kanıtı geçerlidir.

### Faz 9 — KAPALI

- Immutable SocialMedia migration zinciri temporary kopyada PostgreSQL 16'ya uygulandı; head
  `0009_tiktok_organic_oauth_config`, 23 tablo/259 kolon/79 constraint/81 index ve
  `fe786adb32c556b572e316457b4c008e39883ae4b4510f738800179d4be9ab15` fingerprint eşleşti.
- Fixture Accumulate outbox emitted/applied watermark `5`, full snapshot `S=4`, duplicate ack,
  ordered drain/replay ve launch-order provası tamamlandı.
- Owner akışı safe GET → 5 dakikalık fresh SSO + hashed JTI → same-origin explicit POST →
  create+lease intent → one-time state → fake callback/exchange → exact scope gate → AES-GCM
  credential → exact Brand link `pending_verification` zincirinde doğrulandı.
- Invalid/replayed state provider exchange öncesi kapanır; callback sırasında access revoke veya
  required scope eksiği token revoke/discard eder ve credential/link yazmaz.
- Runtime'da live TikTok activation transport yoktur; default production assembly coordinator
  enjekte etmez ve bütün TikTok gate'leri disabled kalır.
- Dormant/static systemd, loopback-only dark Nginx, environment, cutover, rollback ve writer
  inventory taslakları üretildi; hiçbir artifact kurulmadı veya çalıştırılmadı.
- Accumulate final cutover patch'i review draft olarak üretildi; source projeye uygulanmadı.
- `scripts/quality/fase9_offline_release_check.sh`: full backend `121 passed`, targeted rehearsal
  `5 passed`, frontend `13 passed`, Chromium `8 passed` + `4` intentional skip, build 1878 module,
  audit 0; secret/vocabulary/source guard temiz.

Canonical kanıt: `docs/fase9/Faz9_Offline_Release_Rehearsal_Report.md`.

### V2 Release Candidate Complete — TAMAMLANDI

Faz 0–9 kapalıdır. V1 production social verisi ve media için tek writer olmaya devam eder. V2'nin
production DB credential'ı, provider secret'ı, process'i, traffic route'u, mutation'ı, worker'ı,
timer'ı veya schedule'ı yoktur. Writer Ownership Cutover, dark deployment ve owner TikTok
aktivasyonu bu kapanışla otomatik yetkilendirilmez; her biri ayrı açık kullanıcı onayı gerektirir.
