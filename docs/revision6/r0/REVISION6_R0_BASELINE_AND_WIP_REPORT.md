# Revision 6 — R0 Baseline ve Mevcut WIP Raporu

**Durum:** PASS

**Tarih:** 2026-08-07

**Kapsam:** Yalnızca `/home/api/colab_scripts/SocialMediadownstream`

## 1. Sonuç

R0 kapısı kapatıldı. Canlı kaynak projeler salt okunur incelendi; hiçbir kaynak
projede dosya, Git index/worktree, yapı çıktısı, test/cache, servis, süreç, port,
zamanlayıcı, Nginx/routing, veri tabanı, medya veya secret değişikliği yapılmadı.

Yeni Revision 6 baseline'ı eski `docs/fase0` kanıtlarını silmeden veya yeniden
yazmadan ayrı bir dizinde oluşturuldu. Kaynak başlangıç snapshot'ı ile kapanış
guard doğrulaması birebir eşleşti. V2'de R0 başlangıcında bulunan 14 dosyalık
onaylı WIP de R0 altyapı dosyalarından ayrı olarak sabitlendi ve korundu.

## 2. Kanonik kanıt dosyaları

- `source_baseline_revision6.json`: üç salt-okunur kaynak için branch, HEAD,
  origin, porcelain status, status hash'i, binary-safe tracked diff hash'i,
  eksiksiz untracked dosya listesi ve artifact hariç içerik manifesti özeti.
- `baseline_revision6_<project>_content.sha256`: dosya içeriğini kopyalamadan
  üretilmiş SHA-256 içerik manifestleri.
- `v2_wip_baseline_revision6.json`: R0 girişindeki onaylı V2 WIP metadata'sı,
  binary-safe diff hash'i, dosya bazlı içerik hash'i, diff istatistiği ve davranış
  envanteri.
- `v2_wip_baseline_revision6.sha256`: onaylı V2 WIP dosyalarının içerik manifesti.

İçerik manifestlerinden `.git`, `.venv`, `venv`, `node_modules`, `__pycache__`,
`.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `build`, `dist`, `logs`,
`playwright-report`, `test-results` ve `tmp` path parçaları çıkarılmıştır.
Untracked dosya listesi ise artifact dosyaları dahil eksiksiz tutulmuştur; artifact
içerikleri manifestte hash'lenmemiştir.

## 3. Salt-okunur kaynak baseline'ı

Baseline yakalama zamanı: `2026-08-07T10:44:22.594705+00:00`

| Proje | Branch | HEAD | Origin | Status satırı | Untracked dosya | Manifest dosya sayısı |
|---|---|---|---|---:|---:|---:|
| SocialMedia | `feature/tiktok-integration` | `d871dde08c68b335a13187e4853ded85fb869ae5` | `https://github.com/abbasalipanah/SocialMedia.git` | 45 | 22 | 349 |
| Accumulate | `feature/social-ai-insights-ui` | `7d65db2da0a9c7cb866e984422b22bd5d8a1b5f7` | `git@github-accumulate:dexcore/accumulate.git` | 7 | 2 | 1411 |
| performance_marketing | `main` | `4bc9994084ef139667d135823c084376e2901b42` | `git@github.com:abbasalipanah/performance_marketing.git` | 7 | 7 | 522 |

### 3.1 Kaynak hash'leri

| Proje | Tracked binary diff SHA-256 | Artifact hariç içerik manifesti SHA-256 |
|---|---|---|
| SocialMedia | `db6c9b2d9c15d7242c7bf7e3ee0d29cf0258ff36f415a090706c291799b2dcde` | `bfeafc5b28d4e41146caebd4366dffe3583c9b4bf92760bd2ef4b3ba7f01cd38` |
| Accumulate | `326e96c9fdfde7058d485e245e34657f9e9b02f7476a348bdd02e56868e76b8b` | `4394c9828b1846c8549e12994a65545634356911260e38201b0162cf8c05dd5d` |
| performance_marketing | `2e4ef2a7ba1b9ade13313938e545f8fc460cf56c8ac122dfdf8f7543dc7aeb2b` | `d40e16b1b09895651a65edb532369644765d44eaa8453d61f51bd1580437612f` |

Tam porcelain status ve status SHA-256 değerleri kanonik JSON kanıtındadır.

### 3.2 Eksiksiz untracked listeleri

**SocialMedia — 22 dosya**

```text
backend/app/connectors/facebook/audience.py
backend/app/social_media/facebook_audience_controls.py
deploy/systemd/ars-social-backend-facebook-audience.conf
deploy/systemd/facebook-audience-canary.service
deploy/systemd/facebook-audience-canary.timer
deploy/systemd/social-legacy-media-import.service
deploy/systemd/social-legacy-media-import.timer
docs/ACCUMULATE_SOCIAL_COVER_REPAIR_HANDOFF.md
docs/FACEBOOK_AUDIENCE_CANARY_REPORT_2026-07-29.md
docs/SERVER_LOCAL_TIKTOK_LIVE_HANDOFF.md
docs/SOCIALMEDIA_RELEASE_SCOPE_2026-07-29.md
docs/YOUTUBE_IMPLEMENTATION_AND_ROLLOUT_PLAN.md
frontend/src/components/dashboard/FacebookAudienceSection.tsx
frontend/src/components/dashboard/InstagramStoriesSection.tsx
scripts/facebook_audience_sync.py
scripts/import_legacy_media_assets.py
tests/test_facebook_audience_collector.py
tests/test_facebook_audience_controls.py
tests/test_facebook_collector_wrapper.py
tests/test_import_legacy_media_assets.py
tests/test_meta_graph_client.py
tests/test_social_cover_asset_repair_paths.py
```

**Accumulate — 2 dosya**

```text
backend/logs/mail_outbox.txt
how-to-work-accumulate (1).md
```

`backend/logs/mail_outbox.txt` untracked envanterinde tutulmuş, `logs` artifact
hariç tutma kuralı nedeniyle içerik manifestine alınmamıştır.

**performance_marketing — 7 dosya**

```text
docs/Campaign report (1).csv
docs/Performance Marketing – Accumulate Entegrasyonu Yönetici Raporu.pdf
docs/Trafik_edinme_Oturumla_ilişkilendirilen_birincil_kanal_grubu_(Varsayılan_Kanal_Grubu) (3).csv
docs/weborama/API SERVICE DESCRIPTION - Statistic API services.pdf
docs/weborama/Digital exchange (API integration) (1).pdf
docs/weborama/metrics vs dimensions.xlsx
frontend/public/branding/accumulate-ai-logo@4x.png
```

## 4. Eski baseline ilişkisi

`docs/fase0/source_baseline_v2.json` yerinde ve değiştirilmeden korunmuştur.

- İlişki: `superseded_by_revision_6`
- Eski baseline SHA-256:
  `ec1b243d3fe8427cd1f8c1ae2100dd1f3f90f2247f55f937e8d889c297ba0073`
- Yeni guard hedefi: `docs/revision6/r0/source_baseline_revision6.json`

Eski faz raporları tarihsel kanıttır; güncel sertifikasyon olarak kullanılmaz.

## 5. V2 mevcut WIP baseline'ı

| Alan | Değer |
|---|---|
| Branch | `main` |
| HEAD | `11e73bd86e41b5ad6f93d32e768486f857879e05` |
| Origin | `https://github.com/abbasalipanah/SocialMediaV2.git` |
| Dirty dosya | 14: 13 tracked diff + 1 untracked |
| Tracked binary diff SHA-256 | `3a09b4a815cc2e7b186a69a5cf7b4979de2dad783757ed8bd6429c03e92155ed` |
| WIP manifest SHA-256 | `823be17aa81a782d5b84bd7754321ce128a78ee3898e1b8c356df5377280692c` |

Tracked diff toplamı 1.976 ekleme ve 346 silmedir. Untracked kartın satırları bu
toplama dahil değildir.

### 5.1 Dosya ve davranış envanteri

| Durum | Dosya | Diff | Gözlenen işlevsel alan |
|---|---|---:|---|
| M | `backend/app/api/dashboards/__init__.py` | +1/-0 | Dashboard router kaydı |
| M | `backend/app/local_demo.py` | +380/-23 | Genişletilmiş local-demo dashboard/audience payload'ı |
| M | `backend/tests/test_local_demo.py` | +1/-1 | Local-demo beklentisi |
| M | `docs/SOCIAL_MEDIA_V2_MASTER_PLAN.md` | +413/-77 | Onaylı Revision 6 planı ve salt-okunur kurallar |
| M | `frontend/package-lock.json` | +475/-3 | Frontend dependency lock |
| M | `frontend/package.json` | +10/-0 | Frontend dependency tanımları |
| ?? | `frontend/src/features/dashboard/AudienceDemographicsCard.tsx` | untracked | Yeni ortak audience-demographics kartı |
| M | `frontend/src/features/dashboard/PlatformPage.tsx` | +1/-1 | Platform sayfası kompozisyonu |
| M | `frontend/src/features/dashboard/catalog.ts` | +5/-4 | Dashboard katalog metadata'sı |
| M | `frontend/src/features/facebook/FacebookPulseDashboard.tsx` | +291/-67 | Facebook pulse/audience görünümü |
| M | `frontend/src/features/instagram/InstagramPulseDashboard.tsx` | +166/-62 | Instagram pulse/audience görünümü |
| M | `frontend/src/features/tiktok/TikTokPulseDashboard.tsx` | +140/-92 | TikTok pulse/audience görünümü |
| M | `frontend/src/styles.css` | +72/-4 | Ortak dashboard stilleri |
| M | `frontend/src/test/Phase8Products.test.tsx` | +21/-12 | Frontend ürün testi |

Bu envanter bir doğrulama sonucu değildir. Mevcut WIP henüz R2'de test edilmemiştir;
R0 yalnızca onu kayıpsız biçimde sabitler.

## 6. Guard davranışı

`scripts/source_write_guard.sh` aynı çağrı yüzeyini korur, ancak kullandığı
`scripts/quality/source_baseline.py` artık yalnız Revision 6 baseline'ını doğrular.
Doğrulama şu değişikliklerin herhangi birinde başarısız olur:

- kaynak root, branch, HEAD veya origin;
- porcelain status veya status hash'i;
- tracked binary diff hash'i;
- eksiksiz untracked dosya listesi;
- artifact hariç içerik manifesti veya saklanan manifest kanıtı.

`scripts/quality/v2_wip_baseline.py` ise R0'ın kendi guard/kanıt dosyalarını dışarıda
tutarak yalnız R0 girişindeki 14 dosyalık onaylı V2 WIP'yi doğrular.

## 7. R0 doğrulamaları

| Kontrol | Sonuç |
|---|---|
| Revision 6 kaynak baseline yakalama | PASS |
| `scripts/source_write_guard.sh` başlangıç doğrulaması | PASS |
| Onaylı V2 WIP yakalama | PASS |
| `v2_wip_baseline.py verify` | PASS |
| Kaynak projelerde test/build/format/migration | Çalıştırılmadı |
| Kaynak projelerde yazma veya runtime operasyonu | Yapılmadı |
| Başlangıç/kapanış kaynak snapshot eşitliği | PASS |

## 8. R0 çıkış kararı

R0 tamamlandı. R1'e geçiş için gereken immutable kaynak baseline'ı ve mevcut V2
WIP koruması hazırdır. Master plan gereği bu rapor sunulmadan R1 başlatılmamıştır.
