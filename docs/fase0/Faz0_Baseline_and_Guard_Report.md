# Faz 0 — Baseline ve Koruma Kapanış Raporu

Tarih: `2026-07-13`

Durum: **KAPALI**

## Düzeltme

`2026-07-10` tarihli ilk baseline yalnız sıralı dosya yollarını hashliyordu. Dosya içeriği
değişikliklerini algılamadığı için immutable-source kanıtı olarak yeterli değildi. Eski
path-only manifestler canonical baseline kapsamından çıkarıldı.

Yeni v2 baseline aşağıdakileri birlikte doğrular:

- repository root ve canonical source origin;
- branch ve committed HEAD;
- mevcut dirty/untracked inventory;
- committed HEAD'e göre binary tracked-diff SHA-256;
- tracked ve ilgili untracked dosyalar için içerik SHA-256 manifesti;
- content manifest file count ve toplam manifest SHA-256.

Runtime artifact klasörleri (`.git`, venv, cache, `node_modules`, `dist`, `logs`) içerik
manifestine alınmaz. Kaynak patch'i veya dosya içeriği downstream'e kopyalanmaz.

## Canonical kanıtlar

- `source_baseline_v2.json`
- `baseline_SocialMedia_content.sha256`
- `baseline_Accumulate_content.sha256`
- `baseline_performance_marketing_content.sha256`
- `scripts/quality/source_baseline.py`
- `scripts/source_write_guard.sh`

Baseline, `2026-07-13` tarihinde kaynak projelerde zaten mevcut olan dirty state'i aynen
kaydeder; bu değişikliklerin V2 tarafından üretildiği iddia edilmez. Capture işlemi açık
`--approve-current-state` acknowledgement olmadan çalışmaz.

## Doğrulama

```text
SOURCE WRITE GUARD PASS: source Git and content baselines match.
```

Guard downstream dışındaki explicit write hedeflerini de reddeder. Faz 1 sertifikasyonu
öncesinde ve sonrasında guard yeniden çalıştırılmıştır.

## Exclusion kararı

Generic `accumulate-alt-uygulama-teknik-entegrasyon-rehberi.md` yalnız migration girdisiydi;
master plan §7.4 gereği canonical repository artifact'inden çıkarıldı. Social Media'ya özel
contract `docs/contracts/social-media-v2-sso-provisioning.md` altında geliştirilecektir.
