"""Instagram profile capability reader."""

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


class InstagramProfileReader:
    def __init__(
        self,
        transport: MetaTransport,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._transport = transport
        self._clock = clock

    def fetch_profile(self, account: ProviderAccount) -> ProfileSnapshot:
        if account.platform is not PlatformId.INSTAGRAM:
            raise ValueError("provider_family_mismatch")
        payload = self._transport.get(
            account.account_id,
            {"fields": "id,username,name,followers_count,media_count,follows_count"},
        )
        account_id = required_text(payload, "id")
        if account_id != account.account_id:
            raise ValueError("provider_account_mismatch")
        handle = optional_text(payload, "username")
        return ProfileSnapshot(
            account_id=account_id,
            display_name=optional_text(payload, "name") or handle or account_id,
            handle=handle,
            observed_at=self._clock(),
            metric_values={MetricId.FOLLOWERS: nonnegative_int(payload, "followers_count")},
        )


__all__ = ["InstagramProfileReader"]
