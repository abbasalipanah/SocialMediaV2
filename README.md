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
- Collection: `python -m app.workers collect --platform all --scheduled`
- TikTok ilk doğrulama:
  `python -m app.workers verify-tiktok --connection-id <ID>`
- Deploy dosyaları: `deploy/`

Provider OAuth ve automated schedule varsayılan olarak kapalıdır. Üretim kurulum adımları
[`docs/STANDALONE_DEPLOYMENT.md`](docs/STANDALONE_DEPLOYMENT.md), Accumulate’ın yapacağı tek SSO
işi [`docs/ACCUMULATE_SSO_HANDOFF.md`](docs/ACCUMULATE_SSO_HANDOFF.md) içinde tanımlıdır.
