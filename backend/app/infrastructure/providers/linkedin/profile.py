"""LinkedIn Company Page identity and follower snapshot normalization."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.profile import ProfileSnapshot
from app.core.time import utc_now
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId

from .responses import LinkedInResponseError, optional_text, required_count, required_text


class LinkedInProfileReader:
    def __init__(
        self,
        fetch_organization: Callable[[ProviderAccount], Mapping[str, Any]],
        fetch_network_size: Callable[[ProviderAccount], Mapping[str, Any]],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._fetch_organization = fetch_organization
        self._fetch_network_size = fetch_network_size
        self._clock = clock

    def fetch_profile(self, account: ProviderAccount) -> ProfileSnapshot:
        if account.platform is not PlatformId.LINKEDIN:
            raise ValueError("provider_family_mismatch")
        organization = self._fetch_organization(account)
        organization_id = organization.get("id")
        if (
            isinstance(organization_id, bool)
            or not isinstance(organization_id, int)
            or str(organization_id) != account.account_id
        ):
            raise LinkedInResponseError("linkedin_organization_mismatch")
        network_size = self._fetch_network_size(account)
        return ProfileSnapshot(
            account_id=account.account_id,
            display_name=required_text(organization, "localizedName"),
            handle=optional_text(organization, "vanityName"),
            observed_at=self._clock(),
            metric_values={MetricId.FOLLOWERS: required_count(network_size, "firstDegreeSize")},
        )


__all__ = ["LinkedInProfileReader"]
