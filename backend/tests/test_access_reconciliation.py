from __future__ import annotations

import pytest

from app.domain.platforms import PlatformId
from app.infrastructure.persistence.social_v2.access_reconciliation import (
    ExactAccountRef,
    parse_exact_account_ref,
)


def test_exact_account_reference_requires_all_persisted_identity_fields() -> None:
    assert parse_exact_account_ref("56:65445:instagram:17841469232265526") == (
        ExactAccountRef(
            link_id=56,
            brand_id=65445,
            platform=PlatformId.INSTAGRAM,
            external_id="17841469232265526",
        )
    )


@pytest.mark.parametrize(
    "value",
    (
        "56:65445:instagram",
        "bad:65445:instagram:17841469232265526",
        "56:0:instagram:17841469232265526",
        "56:65445:youtube:17841469232265526",
        "56:65445:instagram:",
    ),
)
def test_invalid_account_reference_is_refused(value: str) -> None:
    with pytest.raises(ValueError, match="^account_reference_invalid$"):
        parse_exact_account_ref(value)
