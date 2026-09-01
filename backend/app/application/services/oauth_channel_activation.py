"""Fail-closed OAuth coordination shared by X, LinkedIn, and YouTube."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta

from app.application.ports import (
    OAUTH_CHANNEL_PLATFORMS,
    ActivationAuthority,
    ActivationContext,
    ActivationIntent,
    ActivationIntentStore,
    ActivationStart,
    OAuthAccountGrant,
    OAuthActivationStatePort,
    OAuthChannelError,
    OAuthChannelProvider,
    OAuthConnectionResult,
    OAuthConnectionStore,
    OAuthCredentialBinding,
    OAuthDiscovery,
    OAuthLinkResult,
    OAuthLinkSelection,
)
from app.application.ports.credentials import (
    CredentialRef,
    CredentialStore,
    SecretToken,
    TokenKind,
)
from app.core.time import utc_now
from app.core.write_policy import WritePolicy
from app.domain.platforms import PlatformId

from .tiktok_activation import ActivationGate

OAUTH_CHANNEL_INTENT_TTL = timedelta(minutes=15)
_CALLBACK_REQUIRED_FIELDS = frozenset({"code", "state"})
_CALLBACK_ALLOWED_FIELDS = _CALLBACK_REQUIRED_FIELDS | frozenset(
    {"authuser", "hd", "prompt", "scope"}
)


class OAuthChannelActivationCoordinator:
    def __init__(
        self,
        *,
        platform: PlatformId,
        gate: ActivationGate,
        write_policy: WritePolicy,
        requested_scopes: tuple[str, ...],
        allowed_scopes: tuple[str, ...],
        intent_store: ActivationIntentStore,
        state_port: OAuthActivationStatePort,
        provider: OAuthChannelProvider,
        credential_store: CredentialStore,
        connection_store: OAuthConnectionStore,
        authority: ActivationAuthority,
        clock: Callable[[], datetime] = utc_now,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        if (
            platform not in OAUTH_CHANNEL_PLATFORMS
            or provider.platform is not platform
            or not requested_scopes
            or len(requested_scopes) != len(set(requested_scopes))
            or len(allowed_scopes) != len(set(allowed_scopes))
            or not set(requested_scopes).issubset(allowed_scopes)
        ):
            raise OAuthChannelError("oauth_activation_contract_invalid")
        self.platform = platform
        self._gate = gate
        self._write_policy = write_policy
        self._requested_scopes = requested_scopes
        self._allowed_scopes = frozenset(allowed_scopes)
        self._intent_store = intent_store
        self._state_port = state_port
        self._provider = provider
        self._credential_store = credential_store
        self._connection_store = connection_store
        self._authority = authority
        self._clock = clock
        self._random_bytes = random_bytes

    def ready_for_start(self, context: ActivationContext) -> bool:
        now = self._now()
        return (
            self._write_policy.allows(self._command("start"))
            and self._gate.allows(now)
            and self._provider.activation_enabled
            and self._authority.allows(context)
        )

    def start(self, context: ActivationContext) -> ActivationStart:
        now = self._assert_enabled("start")
        self._assert_authorized(context)
        raw_reference = self._random_bytes(32)
        if len(raw_reference) != 32:
            raise OAuthChannelError("oauth_activation_entropy_invalid")
        reference_hash = hashlib.sha256(raw_reference).hexdigest()
        expires_at = now + OAUTH_CHANNEL_INTENT_TTL
        intent = ActivationIntent(
            reference_hash=reference_hash,
            context=context,
            requested_scopes=self._requested_scopes,
            redirect_uri=self._provider.redirect_uri,
            created_at=now,
            expires_at=expires_at,
            leased_at=now,
        )
        try:
            if not self._intent_store.create_and_lease(intent):
                raise OAuthChannelError("oauth_activation_intent_conflict")
            state = self._state_port.issue(
                intent_hash=reference_hash,
                context=context,
                expires_at=expires_at,
            )
            authorization_url = self._provider.authorization_url(
                state=state,
                scopes=self._requested_scopes,
            )
        except OAuthChannelError:
            raise
        except Exception as exc:
            raise OAuthChannelError("oauth_activation_start_failed") from exc
        return ActivationStart(authorization_url=authorization_url, expires_at=expires_at)

    def callback_brand_id(self, *, query: Mapping[str, str]) -> int:
        self._callback_values(query)
        try:
            return self._state_port.verified_brand_id(query["state"])
        except Exception as exc:
            raise OAuthChannelError("oauth_activation_callback_rejected") from exc

    def complete(
        self,
        *,
        query: Mapping[str, str],
        context: ActivationContext,
    ) -> OAuthConnectionResult:
        now = self._assert_enabled("callback")
        authorization_code, state = self._callback_values(query)
        self._assert_authorized(context)
        try:
            claims = self._state_port.consume(state, expected_context=context)
            intent = self._intent_store.consume(
                reference_hash=claims.intent_hash,
                expected_context=context,
                consumed_at=now,
            )
        except Exception as exc:
            raise OAuthChannelError("oauth_activation_callback_rejected") from exc
        if (
            intent is None
            or intent.requested_scopes != self._requested_scopes
            or intent.redirect_uri != self._provider.redirect_uri
            or intent.expires_at != claims.expires_at
        ):
            raise OAuthChannelError("oauth_activation_callback_rejected")
        provider_token: str | None = None
        written: list[CredentialRef] = []
        try:
            grant = self._provider.exchange_and_discover(
                authorization_code=authorization_code
            )
            provider_token = grant.access_token
            self._validate_grant(grant.granted_scopes, grant.accounts)
            self._assert_authorized(context)
            access_expires_at = now + timedelta(seconds=grant.access_expires_in)
            refresh_expires_at = (
                now + timedelta(seconds=grant.refresh_expires_in)
                if grant.refresh_expires_in is not None
                else None
            )
            bindings: list[OAuthCredentialBinding] = []
            for account in grant.accounts:
                reference_value = self._credential_reference(
                    brand_id=context.brand_id,
                    external_id=account.external_id,
                )
                access_reference = CredentialRef(
                    platform=self.platform,
                    connection_id=reference_value,
                    token_kind=TokenKind.ACCESS,
                )
                self._credential_store.put(
                    access_reference,
                    SecretToken(value=grant.access_token, expires_at=access_expires_at),
                )
                written.append(access_reference)
                if grant.refresh_token:
                    refresh_reference = CredentialRef(
                        platform=self.platform,
                        connection_id=reference_value,
                        token_kind=TokenKind.REFRESH,
                    )
                    self._credential_store.put(
                        refresh_reference,
                        SecretToken(
                            value=grant.refresh_token,
                            expires_at=refresh_expires_at,
                        ),
                    )
                    written.append(refresh_reference)
                bindings.append(
                    OAuthCredentialBinding(
                        platform=self.platform,
                        external_id=account.external_id,
                        display_name=account.display_name,
                        credential_reference=reference_value,
                    )
                )
            result = self._connection_store.create_pending(
                brand_id=context.brand_id,
                platform=self.platform,
                provider_subject_id=grant.provider_subject_id,
                credentials=tuple(bindings),
                expires_at=access_expires_at,
            )
        except OAuthChannelError:
            self._discard(provider_token, written)
            raise
        except Exception as exc:
            self._discard(provider_token, written)
            raise OAuthChannelError("oauth_activation_completion_failed") from exc
        if (
            result.brand_id != context.brand_id
            or result.platform is not self.platform
            or result.state != "pending_verification"
        ):
            self._discard(provider_token, written)
            raise OAuthChannelError("oauth_activation_connection_invalid")
        return result

    def list_discoveries(self, context: ActivationContext) -> tuple[OAuthDiscovery, ...]:
        self._assert_authorized(context)
        try:
            return self._connection_store.list_discoveries(
                brand_id=context.brand_id,
                platform=self.platform,
            )
        except Exception as exc:
            raise OAuthChannelError("oauth_discovery_failed") from exc

    def link_accounts(
        self,
        *,
        context: ActivationContext,
        connection_id: int,
        selections: tuple[OAuthLinkSelection, ...],
    ) -> OAuthLinkResult:
        self._assert_enabled("link")
        self._assert_authorized(context)
        if (
            connection_id < 1
            or not selections
            or len({item.external_id for item in selections}) != len(selections)
        ):
            raise OAuthChannelError("oauth_link_selection_invalid")
        try:
            result = self._connection_store.link_accounts(
                brand_id=context.brand_id,
                platform=self.platform,
                connection_id=connection_id,
                selections=selections,
            )
        except OAuthChannelError:
            raise
        except Exception as exc:
            raise OAuthChannelError("oauth_link_failed") from exc
        if result.brand_id != context.brand_id or result.platform is not self.platform:
            raise OAuthChannelError("oauth_link_result_invalid")
        return result

    def unlink(
        self,
        *,
        context: ActivationContext,
        external_id: str,
    ) -> OAuthLinkResult:
        self._assert_enabled("unlink")
        self._assert_authorized(context)
        selection = OAuthLinkSelection(external_id=external_id)
        try:
            result = self._connection_store.disconnect(
                brand_id=context.brand_id,
                platform=self.platform,
                external_id=selection.external_id,
            )
        except OAuthChannelError:
            raise
        except Exception as exc:
            raise OAuthChannelError("oauth_unlink_failed") from exc
        if result is None:
            raise OAuthChannelError("oauth_link_not_found")
        reference_value = self._credential_reference(
            brand_id=context.brand_id,
            external_id=selection.external_id,
        )
        access_reference = CredentialRef(
            platform=self.platform,
            connection_id=reference_value,
            token_kind=TokenKind.ACCESS,
        )
        try:
            access_token = self._credential_store.get(access_reference)
            if access_token is not None:
                self._provider.revoke(access_token=access_token.value)
        except Exception:
            pass
        for token_kind in (TokenKind.ACCESS, TokenKind.REFRESH):
            try:
                self._credential_store.revoke(
                    CredentialRef(
                        platform=self.platform,
                        connection_id=reference_value,
                        token_kind=token_kind,
                    )
                )
            except Exception:
                pass
        return result

    def _validate_grant(
        self,
        scopes: tuple[str, ...],
        accounts: tuple[OAuthAccountGrant, ...],
    ) -> None:
        granted = set(scopes)
        if (
            not set(self._requested_scopes).issubset(granted)
            or not granted.issubset(self._allowed_scopes)
            or not accounts
            or any(account.platform is not self.platform for account in accounts)
        ):
            raise OAuthChannelError("oauth_activation_grant_denied")

    def _callback_values(self, query: Mapping[str, str]) -> tuple[str, str]:
        if (
            not _CALLBACK_REQUIRED_FIELDS.issubset(query)
            or not set(query).issubset(_CALLBACK_ALLOWED_FIELDS)
        ):
            raise OAuthChannelError("oauth_activation_callback_rejected")
        code = query.get("code", "")
        state = query.get("state", "")
        if not code or len(code.encode()) > 4096 or not state:
            raise OAuthChannelError("oauth_activation_callback_rejected")
        return code, state

    def _assert_enabled(self, operation: str) -> datetime:
        try:
            self._write_policy.assert_allows_mutation(self._command(operation))
        except PermissionError as exc:
            raise OAuthChannelError("oauth_activation_disabled") from exc
        now = self._now()
        if not self._gate.allows(now) or not self._provider.activation_enabled:
            raise OAuthChannelError("oauth_activation_disabled")
        return now

    def _assert_authorized(self, context: ActivationContext) -> None:
        if not self._authority.allows(context):
            raise OAuthChannelError("oauth_activation_authority_denied")

    def _discard(self, access_token: str | None, written: list[CredentialRef]) -> None:
        for reference in reversed(written):
            try:
                self._credential_store.revoke(reference)
            except Exception:
                pass
        if access_token:
            try:
                self._provider.revoke(access_token=access_token)
            except Exception:
                pass

    def _now(self) -> datetime:
        current = self._clock()
        if current.tzinfo is None:
            raise OAuthChannelError("oauth_activation_clock_invalid")
        return current.astimezone(UTC)

    def _command(self, operation: str) -> str:
        return f"{self.platform.value}_oauth_{operation}"

    def _credential_reference(self, *, brand_id: int, external_id: str) -> str:
        canonical = f"{brand_id}:{self.platform.value}:{external_id}".encode()
        return hashlib.sha256(canonical).hexdigest()


__all__ = ["OAUTH_CHANNEL_INTENT_TTL", "OAuthChannelActivationCoordinator"]
