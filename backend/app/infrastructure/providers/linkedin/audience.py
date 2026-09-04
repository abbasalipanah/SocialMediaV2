"""Supported LinkedIn follower demographic facets without opaque URN labels."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.audience import AudienceSnapshot
from app.core.time import utc_now
from app.domain.platforms import PlatformId

from .responses import (
    LinkedInResponseError,
    elements,
    required_count,
    required_mapping,
    required_text,
)
from .wire import organization_urn

_FACETS = {
    "followerCountsByStaffCountRange": ("staffCountRange", "staff_count"),
    "followerCountsByAssociationType": ("associationType", "association_type"),
}


class LinkedInAudienceReader:
    def __init__(
        self,
        fetch: Callable[[ProviderAccount], Mapping[str, Any]],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._fetch = fetch
        self._clock = clock

    def fetch_audience(self, account: ProviderAccount) -> AudienceSnapshot:
        if account.platform is not PlatformId.LINKEDIN:
            raise ValueError("provider_family_mismatch")
        rows = elements(self._fetch(account), limit=1)
        if len(rows) != 1 or rows[0].get("organizationalEntity") != organization_urn(
            account.account_id
        ):
            raise LinkedInResponseError("linkedin_audience_response_invalid")
        row = rows[0]
        breakdowns: dict[str, dict[str, int]] = {}
        for provider_key, (label_key, dimension) in _FACETS.items():
            values = row.get(provider_key, [])
            if not isinstance(values, list) or len(values) > 100:
                raise LinkedInResponseError("linkedin_audience_response_invalid")
            normalized: dict[str, int] = {}
            for item in values:
                if not isinstance(item, Mapping):
                    raise LinkedInResponseError("linkedin_audience_response_invalid")
                label = required_text(item, label_key)
                counts = required_mapping(item, "followerCounts")
                count = required_count(counts, "organicFollowerCount")
                if label in normalized:
                    raise LinkedInResponseError("linkedin_audience_response_invalid")
                normalized[label] = count
            if normalized:
                breakdowns[dimension] = normalized
        return AudienceSnapshot(
            account_id=account.account_id,
            observed_at=self._clock(),
            breakdowns=breakdowns,
        )


__all__ = ["LinkedInAudienceReader"]
