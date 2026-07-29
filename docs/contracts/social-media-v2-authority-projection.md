# Social Media V2 — Session Authority Contract

Tarih: `2026-07-29`

V2 yetkiyi yalnız doğrulanmış SSO session snapshot’ından çözer. Ayrı provisioning/projection
kanalı yoktur.

- Concrete Brand okuması yalnız session `brand_scope` içinde active erişim varsa yapılır.
- Mutation için aynı Brand’de `access_mode=write` gerekir.
- Hidden parent doğrudan veri okuyamaz; yalnız `rollup=true` ile erişilebilir child Brand’leri
  gruplar.
- Rollup mutation her zaman reddedilir.
- Browser’dan gelen `brand_id` yeni yetki üretmez.
- Bilinmeyen parent, cycle, tekrar eden ID veya malformed scope fail-closed olur.
- SSO consume sırasında Brand adları ve hiyerarşi V2’nin kendi `brands` tablosuna kopyalanır;
  sosyal hesap, metric, content ve provider credential verileri yalnız V2’de tutulur.
- `/api/auth/me`, `/api/workspace/brands` ve bütün dashboard/Settings route’ları aynı local
  sessionı kullanır; Accumulate’a runtime API isteği yapmaz.
