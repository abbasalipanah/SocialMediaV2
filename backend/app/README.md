# Backend canonical package

Bu klasör, `SOCIAL_MEDIA_V2_MASTER_PLAN.md` §5 içindeki tek canonical backend
paketidir. Runtime kodu başka bir paralel kaynak ağacında tutulmaz.

- `backend/app/core`: uygulama çekirdeği ve güvenlik/izin katmanları
- `backend/app/domain`: domain modeli ve sözleşim sınırları
- `backend/app/application`: command/query ve servis portları
- `backend/app/infrastructure`: persistence/credential/checkpoint/provider katmanları
- `backend/app/api`: HTTP API yüzeyi
- `backend/app/workers`: collector/worker runtime taslakları

Uygulama giriş noktası `app.main:create_app` fonksiyonudur.
