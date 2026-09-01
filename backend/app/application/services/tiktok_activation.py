"""Fail-closed coordination for the owner-only TikTok account activation."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.ports import (
    ActivationAuthority,
    ActivationContext,
    ActivationIntent,
    ActivationIntentStore,
    ActivationLink,
    ActivationLinkStore,
    ActivationResult,
    ActivationStart,
    ActivationStatePort,
    SessionStore,
    TikTokActivationError,
    TikTokActivationProvider,
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
from app.infrastructure.providers.tiktok.accounts.oauth_state import CALLBACK_FIELDS

from .authority import AuthorityError, build_brand_workspace
from .sso import session_can_access_settings

INTENT_TTL = timedelta(minutes=15)


@dataclass(frozen=True)
class ActivationGate:
    active: bool
    config_version: str
    expected_config_version: str
    enabled_at: datetime
    expires_at: datetime

    def allows(self, now: datetime) -> bool:
        return (
            self.active
            and bool(self.config_version)
            and self.config_version == self.expected_config_version
            and self.enabled_at.tzinfo is not None
            and self.expires_at.tzinfo is not None
            and self.enabled_at <= now
            and now < self.expires_at
        )

    def allows_context(self, context: ActivationContext) -> bool:
        return context.sso_consumed_at >= self.enabled_at


class SessionActivationAuthority:
    """Re-check the V2-owned SSO session before and after provider exchange."""

    def __init__(self, store: SessionStore) -> None:
        self._store = store

    def allows(self, context: ActivationContext) -> bool:
        session = self._store.get_session(context.session_binding)
        if (
            session is None
            or session.get("revoked") is True
            or str(session.get("user_id") or "") != context.user_id
        ):
            return False
        # Settings authority may connect a provider for any Brand its signed
        # scope grants write on: an admin opens Brand Setup for the row they
        # clicked, which need not be the Brand the session was launched with. A
        # session Accumulate delegated for one Brand stays bound to that Brand,
        # which is what the delegation is for.
        if str(session.get("brand_id") or "") != str(
            context.brand_id
        ) and not session_can_access_settings(session):
            return False
        # The scope decides the rest: write on this Brand, resolving to this
        # Brand alone so a rollup cannot stand in for one of its members.
        try:
            workspace = build_brand_workspace(
                session=session,
                selected_brand_id=str(context.brand_id),
                rollup=False,
                require_write=True,
            )
        except AuthorityError:
            return False
        return workspace.scope.resolved_brand_ids == (str(context.brand_id),)


class TikTokActivationCoordinator:
    def __init__(
        self,
        *,
        gate: ActivationGate,
        write_policy: WritePolicy,
        requested_scopes: tuple[str, ...],
        required_scopes: tuple[str, ...],
        optional_scopes: tuple[str, ...],
        intent_store: ActivationIntentStore,
        state_port: ActivationStatePort,
        provider: TikTokActivationProvider,
        credential_store: CredentialStore,
        link_store: ActivationLinkStore,
        authority: ActivationAuthority,
        clock: Callable[[], datetime] = utc_now,
        random_bytes: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        if (
            not requested_scopes
            or len(requested_scopes) != len(set(requested_scopes))
            or not set(required_scopes).issubset(requested_scopes)
            or not set(requested_scopes).issubset(set(required_scopes) | set(optional_scopes))
        ):
            raise TikTokActivationError("activation_scope_contract_invalid")
        self._gate = gate
        self._write_policy = write_policy
        self._requested_scopes = requested_scopes
        self._required_scopes = required_scopes
        self._optional_scopes = optional_scopes
        self._intent_store = intent_store
        self._state_port = state_port
        self._provider = provider
        self._credential_store = credential_store
        self._link_store = link_store
        self._authority = authority
        self._clock = clock
        self._random_bytes = random_bytes

    def ready_for_start(
        self,
        context: ActivationContext,
        *,
        require_gate_context: bool = True,
    ) -> bool:
        now = self._now()
        return (
            self._write_policy.allows("tiktok_activation_start")
            and self._gate.allows(now)
            and (not require_gate_context or self._gate.allows_context(context))
            and self._provider.activation_enabled
            and self._authority.allows(context)
        )

    def start(
        self,
        context: ActivationContext,
        *,
        require_gate_context: bool = True,
    ) -> ActivationStart:
        now = self._assert_enabled("tiktok_activation_start")
        self._assert_authorized(context, require_gate_context=require_gate_context)
        raw_reference = self._random_bytes(32)
        if len(raw_reference) != 32:
            raise TikTokActivationError("activation_entropy_invalid")
        reference_hash = hashlib.sha256(raw_reference).hexdigest()
        expires_at = now + INTENT_TTL
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
            raise TikTokActivationError("activation_intent_conflict")
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
            raise TikTokActivationError("activation_start_failed") from exc
        return ActivationStart(authorization_url=authorization_url, expires_at=expires_at)

    def complete(
        self,
        *,
        query: Mapping[str, str],
        context: ActivationContext,
        require_gate_context: bool = True,
    ) -> ActivationResult:
        now = self._assert_enabled("tiktok_activation_callback")
        # See `validate_callback`: Login Kit returns `code` and the granted
        # `scopes`; `auth_code` is the token endpoint's name for the same value.
        if set(query) != CALLBACK_FIELDS:
            raise TikTokActivationError("activation_callback_rejected")
        auth_code = query.get("code", "")
        state = query.get("state", "")
        if not auth_code or len(auth_code.encode("utf-8")) > 2048 or not state:
            raise TikTokActivationError("activation_callback_rejected")
        self._assert_authorized(context, require_gate_context=require_gate_context)
        try:
            claims = self._state_port.consume(state, expected_context=context)
        except Exception as exc:
            raise TikTokActivationError("activation_callback_rejected") from exc
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
            raise TikTokActivationError("activation_callback_rejected")

        access_token: str | None = None
        written: list[CredentialRef] = []
        try:
            token = self._provider.exchange(auth_code=auth_code)
            access_token = token.access_token
            account = self._provider.inspect(access_token=token.access_token)
            optional = self._validated_optional_scopes(token.scopes, account.scopes)
            self._assert_authorized(context, require_gate_context=require_gate_context)
            credential_reference = self._credential_reference(
                brand_id=context.brand_id,
                business_id=account.business_id,
            )
            access_reference = CredentialRef(
                platform=PlatformId.TIKTOK,
                connection_id=credential_reference,
                token_kind=TokenKind.ACCESS,
            )
            refresh_reference = CredentialRef(
                platform=PlatformId.TIKTOK,
                connection_id=credential_reference,
                token_kind=TokenKind.REFRESH,
            )
            access_expires_at = now + timedelta(seconds=token.expires_in)
            refresh_expires_at = now + timedelta(seconds=token.refresh_expires_in)
            self._credential_store.put(
                access_reference,
                SecretToken(value=token.access_token, expires_at=access_expires_at),
            )
            written.append(access_reference)
            self._credential_store.put(
                refresh_reference,
                SecretToken(value=token.refresh_token, expires_at=refresh_expires_at),
            )
            written.append(refresh_reference)
            link = self._link_store.create_pending(
                brand_id=context.brand_id,
                business_id=account.business_id,
                credential_reference=credential_reference,
                access_expires_at=access_expires_at,
            )
        except TikTokActivationError:
            self._discard(access_token, written)
            raise
        except Exception as exc:
            self._discard(access_token, written)
            raise TikTokActivationError("activation_completion_failed") from exc

        if link.brand_id != context.brand_id or link.state != "pending_verification":
            self._discard(access_token, written)
            raise TikTokActivationError("activation_link_invalid")
        return ActivationResult(
            connection_id=link.connection_id,
            link_id=link.link_id,
            brand_id=link.brand_id,
            state=link.state,
            optional_scopes_available=optional,
        )

    def linked_accounts(self, context: ActivationContext) -> tuple[ActivationLink, ...]:
        self._assert_authorized(context, require_gate_context=False)
        return self._link_store.list_for_brand(brand_id=context.brand_id)

    def available_accounts(self, context: ActivationContext) -> tuple[ActivationLink, ...]:
        self._assert_authorized(context, require_gate_context=False)
        return self._link_store.list_available_for_brand(brand_id=context.brand_id)

    def unlink(self, *, context: ActivationContext, business_id: str) -> ActivationLink:
        try:
            self._write_policy.assert_allows_mutation("tiktok_activation_unlink")
        except PermissionError as exc:
            raise TikTokActivationError("activation_disabled") from exc
        self._assert_authorized(context, require_gate_context=False)
        if not business_id or len(business_id.encode("utf-8")) > 255:
            raise TikTokActivationError("activation_link_invalid")
        link = self._link_store.disconnect(
            brand_id=context.brand_id,
            business_id=business_id,
        )
        if link is None:
            raise TikTokActivationError("activation_link_not_found")

        # The Brand link is already disabled before any provider call, so a
        # temporary TikTok revoke failure cannot leave collection enabled. The
        # locally encrypted access and refresh credentials are then revoked on
        # a best-effort basis as defense in depth.
        if link.credential_reference:
            access_reference = CredentialRef(
                platform=PlatformId.TIKTOK,
                connection_id=link.credential_reference,
                token_kind=TokenKind.ACCESS,
            )
            refresh_reference = CredentialRef(
                platform=PlatformId.TIKTOK,
                connection_id=link.credential_reference,
                token_kind=TokenKind.REFRESH,
            )
            try:
                access_token = self._credential_store.get(access_reference)
                if access_token is not None:
                    self._provider.revoke(access_token=access_token.value)
            except Exception:
                pass
            for reference in (access_reference, refresh_reference):
                try:
                    self._credential_store.revoke(reference)
                except Exception:
                    pass
        return link

    def _assert_enabled(self, command: str) -> datetime:
        try:
            self._write_policy.assert_allows_mutation(command)
        except PermissionError as exc:
            raise TikTokActivationError("activation_disabled") from exc
        now = self._now()
        if not self._gate.allows(now) or not self._provider.activation_enabled:
            raise TikTokActivationError("activation_disabled")
        return now

    def _assert_authorized(
        self,
        context: ActivationContext,
        *,
        require_gate_context: bool,
    ) -> None:
        if (
            (require_gate_context and not self._gate.allows_context(context))
            or not self._authority.allows(context)
        ):
            raise TikTokActivationError("activation_authority_denied")

    def _validated_optional_scopes(
        self,
        token_scopes: tuple[str, ...],
        account_scopes: tuple[str, ...],
    ) -> tuple[str, ...]:
        if (
            not token_scopes
            or len(token_scopes) != len(set(token_scopes))
            or len(account_scopes) != len(set(account_scopes))
            or set(token_scopes) != set(account_scopes)
        ):
            raise TikTokActivationError("activation_scope_mismatch")
        granted = set(account_scopes)
        allowed = set(self._required_scopes) | set(self._optional_scopes)
        if not set(self._required_scopes).issubset(granted) or not granted.issubset(allowed):
            raise TikTokActivationError("activation_scope_denied")
        return tuple(scope for scope in self._optional_scopes if scope in granted)

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
        now = self._clock()
        if now.tzinfo is None:
            raise TikTokActivationError("activation_clock_invalid")
        return now.astimezone(UTC)

    @staticmethod
    def _credential_reference(*, brand_id: int, business_id: str) -> str:
        if not business_id or len(business_id.encode("utf-8")) > 255:
            raise TikTokActivationError("activation_account_invalid")
        canonical = f"{brand_id}:{business_id}".encode()
        return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "ActivationGate",
    "INTENT_TTL",
    "SessionActivationAuthority",
    "TikTokActivationCoordinator",
]
