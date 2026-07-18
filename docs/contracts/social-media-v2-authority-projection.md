# Social Media V2 — Authority Projection Contract

Tarih: `2026-07-14`

Durum: **NORMATİF — Faz 3**

## Projection namespace

Mevcut `social_projection_state.payload_json` tablosunda aşağıdaki key'ler kullanılır:

```text
v2:brand-shell:<brand_id>
v2:brand-entitlement:<brand_id>
v2:brand-app-access:<brand_id>
v2:membership:<membership_id>
v2:brand-access-snapshot:<user_id>
v2:brand-access:<user_id>:<brand_id>
v2:user:<user_id>
```

Brand shell; `brand_id`, nullable `name`, nullable `parent_brand_id`, `active`, `placeholder`,
event type ve version taşır. Access satırı; exact user/Brand, canonical role, `read|write`
access mode, `active`, authority source ve version taşır.

## Full snapshot semantiği

`brand_access.sync`, user için tam replacement snapshot'tır. Event ID claim'i, snapshot version
gate'i, shell upsert'leri, yeni access satırları ve snapshot'ta bulunmayan eski access satırlarının
inactive yapılması tek PostgreSQL transaction'ında gerçekleşir.

- Snapshot'taki Brand'ler `social_media` erişimi için upstream tarafından filtrelenmiş authority
  kabul edilir.
- Incremental `membership.upserted`, tek başına erişim açamaz; exact Brand entitlement ve app
  access projection'larının ikisi de active olmalıdır.
- Eski/eşit snapshot version güncel erişimi geri alamaz.
- Empty snapshot bütün mevcut user–Brand access satırlarını inactive yapar.
- Snapshot apply edildiğinde user session'ları revoke edilir; sonraki SSO güncel projection'a göre
  yeni session kurar.
- Parent entitlement child access'i açmaz.

## Parent, child ve hidden parent

Snapshot Brand entry'si `id`, nullable `name`, nullable `parent_brand_id`, status ve canonical role
taşır. Erişimli child'ın parent shell'i henüz gelmediyse insert-only placeholder shell oluşturulur.
Mevcut gerçek parent shell placeholder tarafından overwrite edilemez.

Hidden parent:

- doğrudan Brand data access'i veya mutation capability'si taşımaz;
- yalnız erişilebilir active descendant bulunduğunda workspace hierarchy'sinde görünür;
- yalnız `rollup=true` scope'unda seçilebilir;
- rollup yalnız kullanıcının active ve yetkili descendant Brand ID'lerini döndürür;
- unrelated sibling, başka family veya inactive/app-revoked Brand scope'a giremez.

Hierarchy cycle fail-closed `brand_hierarchy_cycle` üretir.

## Query ve authorization

`GET /api/workspace/brands` local session user'ını authority kabul eder. Optional
`selected_brand_id` yalnız projection içindeki görünür Brand veya hidden-parent shell olabilir;
browser query değeri yeni yetki üretmez.

Response:

- Brand listesi ve `active|hidden_parent` visibility;
- family root ve family Brand ID'leri;
- requested Brand/rollup;
- backend tarafından çözülmüş exact `resolved_brand_ids`.

Concrete Brand mutation authorization'ı `require_write=true` ister. Read access mutation için
yeterli değildir ve parent rollup mutationı reddedilir. Dashboard rollup aggregation daha sonraki
API fazında yalnız bu resolved scope'u kullanacaktır.

`GET /api/auth/me`, session payload'ındaki user/Brand'i her istekte güncel projection'a karşı
side-effect üretmeden doğrular. Brand/access/entitlement/app-access revoke edilmişse session
query'si fail-closed olur; GET içinde repair, upsert veya commit yapılmaz.
