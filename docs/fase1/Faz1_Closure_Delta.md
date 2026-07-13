# Faz 1 — Kapanış Delta Notu

Tarih: `2026-07-13`

Önceki açık maddeler kapatıldı:

- pytest/FastAPI bağımlılıkları izole `backend/.venv` içinde kuruldu;
- runtime ve development lock'ları gerçek transitive/hash-locked dosyalara çevrildi;
- 18 backend testi geçti;
- eksik frontend lock düzeltildi ve clean install/build geçti;
- iki paralel backend ağacı tek `backend/app` ağacında birleştirildi;
- testteki `social_writes_enabled`/`writes_enabled` uyumsuzluğu giderildi;
- source guard path-only hash yerine Git + content baseline'a yükseltildi;
- generic migration rehberi repository artifact'inden çıkarıldı.

Son durum: **Faz 1 çıkış kapısı yeşil ve kapalıdır.**
