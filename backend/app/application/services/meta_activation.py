"""Fail-closed coordination for Brand-scoped Meta self-service connection."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta

from app.application.ports import (
    ActivationAuthority,
    ActivationContext,
    ActivationIntent,
    ActivationIntentStore,
    ActivationStart,
    ActivationStatePort,
    MetaActivationError,
    MetaActivationProvider,
    MetaConnectionResult,
    MetaConnectionStore,
    MetaCredentialBinding,
    MetaDiscovery,
    MetaLinkResult,
    MetaLinkSelection,
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

META_INTENT_TTL = timedelta(minutes=15)


class MetaActivationCoordinator:
    def __init__(
        self,
        *,
        gate: ActivationGate,
        write_policy: WritePolicy,
        requested_scopes: tuple[str, ...],
        intent_store: ActivationIntentStore,
        state_port: ActivationStatePort,
        provider: MetaActivationProvider,
        credential_store: CredentialStore,
        connection_store: MetaConnectionStore,
        authority: ActivationAuthority,
        clock: Callable[[], datetime] = utc_now,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        if not requested_scopes or len(requested_scopes) != len(set(requested_scopes)):
            raise MetaActivationError("meta_scope_contract_invalid")
        self._gate = gate
        self._write_policy = write_policy
        self._requested_scopes = requested_scopes
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
            self._write_policy.allows("meta_activation_start")
            and self._gate.allows(now)
            and self._provider.activation_enabled
            and self._authority.allows(context)
        )

    def start(self, context: ActivationContext) -> ActivationStart:
        now = self._assert_enabled("meta_activation_start")
        self._assert_authorized(context)
        raw_reference = self._random_bytes(32)
        if len(raw_reference) != 32:
            raise MetaActivationError("meta_activation_entropy_invalid")
        reference_hash = hashlib.sha256(raw_reference).hexdigest()
        expires_at = now + META_INTENT_TTL
        intent = ActivationIntent(
            reference_hash=reference_hash,
            context=context,
            requested_scopes=self._requested_scopes,
            redirect_uri=self._provider.redirect_uri,
            created_at=now,
            expires_at=expires_at,
            leased_at=now,
        )
        if not self._intent_store.create_and_lease(intent):
            raise MetaActivationError("meta_activation_intent_conflict")
        try:
            state = self._state_port.issue(
                intent_hash=reference_hash,
                context=context,
                expires_at=expires_at,
            )
            authorization_url = self._provider.authorization_url(
                state=state,
                scopes=self._requested_scopes,
            )
        except Exception as exc:
            raise MetaActivationError("meta_activation_start_failed") from exc
        return ActivationStart(authorization_url=authorization_url, expires_at=expires_at)

    def complete(
        self,
        *,
        query: Mapping[str, str],
        context: ActivationContext,
    ) -> MetaConnectionResult:
        now = self._assert_enabled("meta_activation_callback")
        if set(query) != {"code", "state"}:
            raise MetaActivationError("meta_activation_callback_rejected")
        authorization_code = query.get("code", "")
        state = query.get("state", "")
        if not authorization_code or len(authorization_code.encode()) > 2048 or not state:
            raise MetaActivationError("meta_activation_callback_rejected")
        self._assert_authorized(context)
        try:
            claims = self._state_port.consume(state, expected_context=context)
        except Exception as exc:
            raise MetaActivationError("meta_activation_callback_rejected") from exc
        intent = self._intent_store.consume(
            reference_hash=claims.intent_hash,
            expected_context=context,
            consumed_at=now,
        )
        if (
            intent is None
            or intent.requested_scopes != self._requested_scopes
            or intent.redirect_uri != self._provider.redirect_uri
            or intent.expires_at != claims.expires_at
        ):
            raise MetaActivationError("meta_activation_callback_rejected")

        provider_token: str | None = None
        written: list[CredentialRef] = []
        try:
            grant = self._provider.exchange_and_discover(authorization_code=authorization_code)
            provider_token = grant.access_token
            if not set(self._requested_scopes).issubset(grant.granted_scopes):
                raise MetaActivationError("meta_activation_scope_denied")
            if not grant.accounts:
                raise MetaActivationError("meta_activation_accounts_unavailable")
            self._assert_authorized(context)
            expires_at = now + timedelta(seconds=grant.expires_in)
            user_reference_value = self._credential_reference(
                brand_id=context.brand_id,
                platform=PlatformId.FACEBOOK,
                external_id=f"user-{grant.provider_user_id}",
            )
            user_reference = CredentialRef(
                platform=PlatformId.FACEBOOK,
                connection_id=user_reference_value,
                token_kind=TokenKind.ACCESS,
            )
            self._credential_store.put(
                user_reference,
                SecretToken(value=grant.access_token, expires_at=expires_at),
            )
            written.append(user_reference)

            bindings: list[MetaCredentialBinding] = []
            for account in grant.accounts:
                reference_value = self._credential_reference(
                    brand_id=context.brand_id,
                    platform=account.platform,
                    external_id=account.external_id,
                )
                reference = CredentialRef(
                    platform=account.platform,
                    connection_id=reference_value,
                    token_kind=TokenKind.ACCESS,
                )
                self._credential_store.put(
                    reference,
                    SecretToken(value=account.access_token, expires_at=expires_at),
                )
                written.append(reference)
                bindings.append(
                    MetaCredentialBinding(
                        platform=account.platform,
                        external_id=account.external_id,
                        display_name=account.display_name,
                        credential_reference=reference_value,
                    )
                )
            result = self._connection_store.create_pending(
                brand_id=context.brand_id,
                provider_user_id=grant.provider_user_id,
                user_credential_reference=user_reference_value,
                credentials=tuple(bindings),
                expires_at=expires_at,
            )
        except MetaActivationError:
            self._discard(provider_token, written)
            raise
        except Exception as exc:
            self._discard(provider_token, written)
            raise MetaActivationError("meta_activation_completion_failed") from exc
        if result.brand_id != context.brand_id or result.state != "pending_verification":
            self._discard(provider_token, written)
            raise MetaActivationError("meta_activation_connection_invalid")
        return result

    def list_discoveries(self, context: ActivationContext) -> tuple[MetaDiscovery, ...]:
        self._assert_authorized(context)
        return self._connection_store.list_discoveries(brand_id=context.brand_id)

    def link_accounts(
        self,
        *,
        context: ActivationContext,
        connection_id: int,
        selections: tuple[MetaLinkSelection, ...],
    ) -> MetaLinkResult:
        self._assert_enabled("meta_activation_link")
        self._assert_authorized(context)
        if not selections or len({(item.platform, item.external_id) for item in selections}) != len(
            selections
        ):
            raise MetaActivationError("meta_link_selection_invalid")
        try:
            result = self._connection_store.link_accounts(
                brand_id=context.brand_id,
                connection_id=connection_id,
                selections=selections,
            )
        except MetaActivationError:
            raise
        except Exception as exc:
            raise MetaActivationError("meta_link_failed") from exc
        if result.brand_id != context.brand_id or result.state != "connected":
            raise MetaActivationError("meta_link_result_invalid")
        return result

    def _assert_enabled(self, command: str) -> datetime:
        try:
            self._write_policy.assert_allows_mutation(command)
        except PermissionError as exc:
            raise MetaActivationError("meta_activation_disabled") from exc
        now = self._now()
        if not self._gate.allows(now) or not self._provider.activation_enabled:
            raise MetaActivationError("meta_activation_disabled")
        return now

    def _assert_authorized(self, context: ActivationContext) -> None:
        if not self._authority.allows(context):
            raise MetaActivationError("meta_activation_authority_denied")

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
            raise MetaActivationError("meta_activation_clock_invalid")
        return current.astimezone(UTC)

    @staticmethod
    def _credential_reference(
        *,
        brand_id: int,
        platform: PlatformId,
        external_id: str,
    ) -> str:
        if not external_id or len(external_id.encode()) > 255:
            raise MetaActivationError("meta_activation_account_invalid")
        return hashlib.sha256(f"{brand_id}:{platform.value}:{external_id}".encode()).hexdigest()


__all__ = ["META_INTENT_TTL", "MetaActivationCoordinator"]
