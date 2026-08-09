# Faz 2 — SSO ve Provisioning Kapanış Adayı Raporu

> **ARCHIVED / SUPERSEDED:** Bu tarihsel rapor Revizyon 6 R6 ile hükümsüzdür. Güncel runtime
> sözleşmesi yalnız `docs/contracts/social-media-v2-sso-only.md` dosyasıdır; provisioning yüzeyi
> final mimaride yoktur.

Tarih: `2026-07-13`

Son doğrulama: `2026-07-14`

Durum: **KAPALI — ÇIKIŞ KAPISI YEŞİL**

## Tamamlanan teslimatlar

- Gerçek Accumulate v1 `sso_contract` yapısıyla uyumlu HS256/JWT doğrulaması.
- Exact audience/app/role/Brand/entitlement/access-mode/visibility/access-window kontrolleri.
- Allowlist edilmiş signed launch target, one-time JTI ve hash-only opaque local session.
- HttpOnly/SameSite cookie, no-store auth response ve same-origin logout.
- HMAC-SHA256 raw-body verification, timestamp window ve hash-only nonce replay claim.
- Exact event seti, nested status parser, canonical membership/snapshot role validation.
- Atomic event idempotency ve entity-version ordering.
- User/Brand/entitlement/app-access/membership/snapshot kaynaklı session revocation.
- `SessionStore`, `ProvisioningStore` ve combined local authority portu.
- Mevcut `social_projection_state.payload_json` ve `varchar(255)` sözleşmesiyle uyumlu,
  DDL gerektirmeyen disposable PostgreSQL projection/session adapterı.
- Normatif `docs/contracts/social-media-v2-sso-provisioning.md` contract'ı.
- Tek komutluk `scripts/quality/fase2_contract_check.sh` sertifika zinciri.

Eski bootstrap `sso_payload.py`, gerçek Accumulate SSO sözleşmesini temsil etmediği ve runtime'da
kullanılmadığı için kaldırıldı.

## Teknik doğrulama

Source guard dışındaki bütün kontroller geçmiştir:

```text
Ruff: clean
Backend without DB: 33 passed, 3 skipped
Disposable PostgreSQL full suite: 36 passed
Python wheel: successfully built
Frontend: npm ci + Vite production build passed
Canonical source/built-artifact vocabulary guard: clean
git diff --check: clean
```

PostgreSQL `postgres:16-alpine` containerı yalnız test süresince random localhost portunda
çalıştırılmış ve test sonunda silinmiştir. Production DB, provider, secret, worker veya schedule
kullanılmamıştır.

## 2026-07-14 schema compatibility düzeltmesi

İlk test fixture'ı production-compatible V1 tablo sözleşmesini kullanmıyor; var olmayan
`payload` ve `expires_at` kolonlarını oluşturuyordu. Bu nedenle testler geçmesine rağmen adapter
gerçek `social_projection_state` tablosunda `UndefinedColumn` üretiyordu.

Düzeltme sonrasında:

- bütün payload sorguları mevcut `payload_json` kolonunu kullanır;
- session/JTI/nonce TTL değeri yeni kolon eklemeden typed JSONB içinde tutulur;
- PostgreSQL fixture'ı V1 tablosundaki kolon adları, defaultlar ve `varchar(255)` key sınırını
  kullanır;
- event/entity key uzunluğu DB çağrısından önce `invalid_event` ile fail-closed reddedilir;
- gerçek V1 kolon sözleşmesinin disposable kopyasında integration testleri geçer.

## Çıkış kapısı blokajı

`scripts/quality/fase2_contract_check.sh`, ilk source immutability guard adımında doğru biçimde
fail-closed durmaktadır. `performance_marketing` kaynak projesi Faz 0 baseline'ından sonra hem
commit hem de untracked dosya düzeyinde ilerlemiştir:

```text
expected HEAD: 7d791162bbe0ab2eb3a4a4975ca9b12197341051
actual HEAD:   9d93374d05e542685f14ab6739b8c5a660db658f
expected content file count: 398
actual content file count:   418
```

Baseline'da zaten kayıtlı iki untracked dokümana ek olarak yeni trafik edinme CSV'si de vardır.
Bu kaynak değişiklikleri downstream düzeltmesi sırasında değiştirilmemiş veya baseline'a
alınmamıştır.

Bu nedenle Faz 2 henüz `KAPALI` olarak işaretlenmez. Güncel `performance_marketing` commit ve
untracked dosyaları beklenen kullanıcı çalışmasıysa yeni source state açıkça onaylanarak Faz 0
v2 baseline'ı yenilenmelidir. Beklenmeyen bir değişiklik varsa kaynak repository sahibi
tarafından ele alınmalıdır. Her iki durumda da ardından full Faz 2 certification yeniden
çalıştırılmalıdır.

## Sonraki faz kuralı

`2026-07-14` tarihinde kullanıcı güncel `performance_marketing` source state'ini beklenen durum
olarak açıkça onayladı. Baseline acknowledgement ile yenilendi ve aşağıdaki canonical komut tek
koşuda geçti:

```text
./scripts/quality/fase2_contract_check.sh
SOURCE WRITE GUARD PASS
Faz 1 certification passed
Disposable PostgreSQL: 36 passed
Final SOURCE WRITE GUARD PASS
OK: Faz 2 SSO/provisioning contract certification passed.
```

Faz 2 çıkış kapısı kapanmıştır. Faz 3 parent/child authority projection geliştirmesi artık
başlatılabilir.
