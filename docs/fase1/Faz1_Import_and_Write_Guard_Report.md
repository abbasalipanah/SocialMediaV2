# Faz 1 — Import ve Write Guard Raporu

Tarih: `2026-07-13`

- Runtime yalnız `backend/app` package'ından import edilir.
- Kaynak proje import/path bağımlılığı architecture testleriyle reddedilir.
- Domain katmanının FastAPI, SQLAlchemy, HTTP transport ve infrastructure bağımlılığı reddedilir.
- Bütün bootstrap HTTP route'ları explicit query olarak işaretlidir.
- Bootstrap mutation endpoint'i yoktur.
- Merkezi `WritePolicy`, yalnız açık disposable development DB + explicit write flag birleşiminde izin verir.
- Dormant, production-like ve bütün cutover mode'ları Faz 1'de fail-closed kalır.

Kanıt: `backend/tests/test_import_boundaries.py`,
`backend/tests/test_command_query_boundary.py`, `backend/tests/test_bootstrap_guard.py`.
