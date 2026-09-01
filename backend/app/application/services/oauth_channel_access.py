"""Refresh and identity checks for background OAuth channel collection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.application.ports import (
    OAUTH_CHANNEL_PLATFORMS,
    OAuthChannelError,
    OAuthChannelProvider,
)
from app.application.ports.credentials import (
    CredentialRef,
    CredentialStore,
    SecretToken,
    TokenKind,
)
from app.core.time import utc_now
from app.domain.platforms import PlatformId


@dataclass(frozen=True)
class OAuthAccessContext:
    platform: PlatformId
    external_id: str
    access_token: str = field(repr=False)
    granted_scopes: frozenset[str]


class OAuthChannelAccessManager:
    def __init__(
        self,
        *,
        platform: PlatformId,
        required_scopes: tuple[str, ...],
        allowed_scopes: tuple[str, ...],
        provider: OAuthChannelProvider,
        credential_store: CredentialStore,
        clock: Callable[[], datetime] = utc_now,
        refresh_margin: timedelta = timedelta(minutes=5),
    ) -> None:
        if (
            platform not in OAUTH_CHANNEL_PLATFORMS
            or provider.platform is not platform
            or not required_scopes
            or not set(required_scopes).issubset(allowed_scopes)
            or refresh_margin < timedelta(0)
        ):
            raise OAuthChannelError("oauth_access_contract_invalid")
        self._platform = platform
        self._required_scopes = frozenset(required_scopes)
        self._allowed_scopes = frozenset(allowed_scopes)
        self._provider = provider
        self._credentials = credential_store
        self._clock = clock
        self._refresh_margin = refresh_margin

    def resolve(
        self,
        *,
        credential_reference: str,
        external_id: str,
    ) -> OAuthAccessContext:
        access_reference = self._reference(credential_reference, TokenKind.ACCESS)
        access = self._credentials.get(access_reference)
        scopes = self._required_scopes
        now = self._now()
        if access is None or (
            access.expires_at is not None
            and access.expires_at <= now + self._refresh_margin
        ):
            access, scopes = self._refresh(
                credential_reference=credential_reference,
                access_reference=access_reference,
                now=now,
            )
        try:
            accounts = self._provider.inspect_accounts(access_token=access.value)
        except OAuthChannelError:
            raise
        except Exception as exc:
            raise OAuthChannelError("oauth_access_identity_failed") from exc
        matches = [
            account
            for account in accounts
            if account.platform is self._platform and account.external_id == external_id
        ]
        if len(matches) != 1 or any(
            account.platform is not self._platform for account in accounts
        ):
            raise OAuthChannelError("oauth_access_identity_rejected")
        return OAuthAccessContext(
            platform=self._platform,
            external_id=external_id,
            access_token=access.value,
            granted_scopes=frozenset(scopes),
        )

    def _refresh(
        self,
        *,
        credential_reference: str,
        access_reference: CredentialRef,
        now: datetime,
    ) -> tuple[SecretToken, frozenset[str]]:
        refresh_reference = self._reference(
            credential_reference,
            TokenKind.REFRESH,
        )
        refresh = self._credentials.get(refresh_reference)
        if refresh is None:
            raise OAuthChannelError("oauth_refresh_token_unavailable")
        try:
            grant = self._provider.refresh(refresh_token=refresh.value)
        except OAuthChannelError:
            raise
        except Exception as exc:
            raise OAuthChannelError("oauth_access_refresh_failed") from exc
        granted = frozenset(grant.granted_scopes)
        if not self._required_scopes.issubset(granted) or not granted.issubset(
            self._allowed_scopes
        ):
            raise OAuthChannelError("oauth_access_scope_rejected")
        access = SecretToken(
            value=grant.access_token,
            expires_at=now + timedelta(seconds=grant.access_expires_in),
        )
        writes: list[tuple[CredentialRef, SecretToken]] = [(access_reference, access)]
        if grant.refresh_token is not None:
            writes.append(
                (
                    refresh_reference,
                    SecretToken(
                        value=grant.refresh_token,
                        expires_at=(
                            now + timedelta(seconds=grant.refresh_expires_in)
                            if grant.refresh_expires_in is not None
                            else None
                        ),
                    ),
                )
            )
        self._credentials.put_many(tuple(writes))
        return access, granted

    def _reference(self, value: str, token_kind: TokenKind) -> CredentialRef:
        return CredentialRef(
            platform=self._platform,
            connection_id=value,
            token_kind=token_kind,
        )

    def _now(self) -> datetime:
        current = self._clock()
        if current.tzinfo is None:
            raise OAuthChannelError("oauth_access_clock_invalid")
        return current.astimezone(UTC)


__all__ = ["OAuthAccessContext", "OAuthChannelAccessManager"]
