from datetime import UTC, datetime

import pytest

from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.domain.platforms import PlatformId
from app.infrastructure.providers.tiktok.accounts.content import TikTokContentReader


@pytest.mark.parametrize(
    ("create_time", "expected"),
    [
        ("2026-07-19 12:34:56", datetime(2026, 7, 19, 12, 34, 56, tzinfo=UTC)),
        ("1785253164", datetime.fromtimestamp(1_785_253_164, tz=UTC)),
    ],
)
def test_provider_datetime_formats_are_normalized_to_utc(
    create_time: str,
    expected: datetime,
) -> None:
    account = ProviderAccount(
        platform=PlatformId.TIKTOK,
        account_id="business-1",
        credential=ProviderCredential(access_token="fixture-access-value"),
    )
    reader = TikTokContentReader(
        lambda _account_id, _cursor: {
            "code": 0,
            "message": "OK",
            "request_id": "video-request",
            "data": {
                "videos": [
                    {
                        "item_id": "video-1",
                        "create_time": create_time,
                        "likes": 4,
                        "comments": 2,
                        "shares": 1,
                        "video_views": 25,
                    }
                ],
                "has_more": True,
                "cursor": 1_763_482_984_376,
            },
        },
        clock=lambda: datetime(2026, 8, 18, tzinfo=UTC),
    )

    page = reader.list_content(account)

    assert page.items[0].fields["published_at"] == expected
    assert page.next_cursor == "1763482984376"
