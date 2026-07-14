"""Facebook profile capability reader."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.profile import ProfileSnapshot
from app.core.time import utc_now
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta.fields import nonnegative_int, optional_text, required_text
from app.infrastructure.providers.meta.transport import MetaTransport


class FacebookProfileReader:
    def __init__(
        self,
        transport: MetaTransport,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._transport = transport
        self._clock = clock

    def fetch_profile(self, account: ProviderAccount) -> ProfileSnapshot:
        if account.platform is not PlatformId.FACEBOOK:
            raise ValueError("provider_family_mismatch")
        payload = self._transport.get(
            account.account_id,
            {"fields": "id,name,username,followers_count,fan_count"},
        )
        account_id = required_text(payload, "id")
        if account_id != account.account_id:
            raise ValueError("provider_account_mismatch")
        followers = nonnegative_int(payload, "followers_count")
        if followers is None:
            followers = nonnegative_int(payload, "fan_count")
        return ProfileSnapshot(
            account_id=account_id,
            display_name=required_text(payload, "name"),
            handle=optional_text(payload, "username"),
            observed_at=self._clock(),
            metric_values={MetricId.FOLLOWERS: followers},
        )


__all__ = ["FacebookProfileReader"]
