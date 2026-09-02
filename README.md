# Social Media V2

Facebook, Instagram ve TikTok için bağımsız Social Media uygulaması. Accumulate ile tek çalışma
zamanı bağlantısı imzalı SSO’dur; uygulama kodu, veritabanı, frontend, provider bağlantıları,
media ve worker’lar V2’ye aittir.

## Güvenlik sınırı

Bu repository yalnız `/home/api/colab_scripts/SocialMediadownstream` kapsamındadır. Canlı
`SocialMedia`, `Accumulate` ve `performance_marketing` projeleri değiştirilmez veya yeniden
başlatılmaz. Ayrıntılı kural seti
[`docs/SOCIAL_MEDIA_V2_MASTER_PLAN.md`](docs/SOCIAL_MEDIA_V2_MASTER_PLAN.md) içindedir.

## Local kontrol

Gerçek provider veya production DB kullanmayan ürün demosu:

```bash
./scripts/dev/start_local.sh
```

Frontend dizininden aynı yığını başlatmak için:

```bash
cd frontend
npm run dev
```

Tarayıcı: `http://127.0.0.1:3010/`

Temel doğrulama:

```bash
cd backend
.venv/bin/python -m ruff check app tests
.venv/bin/python -m pytest

cd ../frontend
npm test -- --run
npm run build
```

## Bağımsız runtime

Runtime durum sözleşmesi `development → dormant → staging → standalone_ready → active`
sırasıdır. Repository'deki production env örneği güvenli olarak `standalone_ready`, writes off,
provider off ve schedule off başlar; `active` moda otomatik geçiş yoktur.

- DB migration: `backend/scripts/apply_migrations.py`
- API: `uvicorn app.main:app`
- Tek collection orchestrator: `python -m app.workers collect --platform all --scheduled`.
  Her `:00` ve `:30` çalışmasında önce bütün aktif Instagram story feed'lerini kalıcılaştırır;
  ardından Facebook, Instagram ve TikTok hesaplarının dayanıklı turuna kaldığı yerden devam eder.
  Yeni bağlanan hesaplar devam eden turun sonuna eklenir; ayrı bir collector timer yoktur.
- TikTok ilk doğrulama:
  `python -m app.workers verify-tiktok --connection-id <ID>`
- Erişimi kaldırılmış hesabı toplama kuyruğundan güvenli çıkarma (varsayılan dry-run):
  `python backend/scripts/reconcile_account_access.py --env <ENV> --reason access_disconnected --account <LINK_ID>:<BRAND_ID>:<PLATFORM>:<EXTERNAL_ID>`
  Kimlik ve bağlantı planı doğrulandıktan sonra aynı komut `--apply` ile uygulanır. TikTok
  yeniden yetkilendirme durumunda
  `--reason reauthorization_required --revoke-tiktok-credentials` kullanılır; tarihsel rapor
  verileri silinmez.
- Deploy dosyaları: `deploy/`

Provider OAuth ve automated schedule varsayılan olarak kapalıdır. Üretim kurulum adımları
[`docs/STANDALONE_DEPLOYMENT.md`](docs/STANDALONE_DEPLOYMENT.md), Accumulate’ın yapacağı tek SSO
işi [`docs/ACCUMULATE_SSO_HANDOFF.md`](docs/ACCUMULATE_SSO_HANDOFF.md) içinde tanımlıdır.
