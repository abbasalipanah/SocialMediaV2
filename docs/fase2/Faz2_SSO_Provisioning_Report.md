# Faz 2 — SSO ve Provisioning Kapanış Adayı Raporu

Tarih: `2026-07-13`

Durum: **UYGULAMA TAMAM — ÇIKIŞ KAPISI EXTERNAL SOURCE DRIFT NEDENİYLE BLOKE**

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
- Schema-compatible disposable PostgreSQL projection/session adapterı.
- Normatif `docs/contracts/social-media-v2-sso-provisioning.md` contract'ı.
- Tek komutluk `scripts/quality/fase2_contract_check.sh` sertifika zinciri.

Eski bootstrap `sso_payload.py`, gerçek Accumulate SSO sözleşmesini temsil etmediği ve runtime'da
kullanılmadığı için kaldırıldı.

## Teknik doğrulama

Source guard dışındaki bütün kontroller geçmiştir:

```text
Ruff: clean
Backend without DB: 31 passed, 2 skipped
Disposable PostgreSQL full suite: 33 passed
Python wheel: successfully built
Frontend: npm ci + Vite production build passed
Canonical source/built-artifact vocabulary guard: clean
git diff --check: clean
```

PostgreSQL `postgres:16-alpine` containerı yalnız test süresince random localhost portunda
çalıştırılmış ve test sonunda silinmiştir. Production DB, provider, secret, worker veya schedule
kullanılmamıştır.

## Çıkış kapısı blokajı

`scripts/quality/fase2_contract_check.sh`, ilk source immutability guard adımında doğru biçimde
fail-closed durmuştur. Faz 0 baseline'ından sonra aşağıdaki yeni untracked kaynak dosya
görünmüştür:

```text
/home/api/colab_scripts/performance_marketing/docs/
Trafik_edinme_Oturumla_ilişkilendirilen_birincil_kanal_grubu_(Varsayılan_Kanal_Grubu) (3).csv
```

Kanıt: `size=56909`, `mtime/ctime=2026-07-13 06:44:37 UTC`, baseline file count `398`, güncel
file count `399`. Dosya downstream kapsamı dışındadır; içeriği okunmamış, değiştirilmemiş,
silinmemiş ve baseline'a alınmamıştır.

Bu nedenle Faz 2 henüz `KAPALI` olarak işaretlenmez ve checkpoint commit'i oluşturulmaz.
Dosya beklenen bir kullanıcı girdisiyse yeni source state açıkça onaylanarak Faz 0 v2 baseline'ı
yenilenmelidir. Beklenmeyen bir dosyaysa kaynak repository sahibi tarafından ele alınmalıdır.
Her iki durumda da ardından full Faz 2 certification yeniden çalıştırılmalıdır.

## Sonraki faz kuralı

Faz 3 parent/child authority projection geliştirmesi, source guard ve full Faz 2 sertifikası
aynı koşuda yeşil olmadan başlatılmaz.
