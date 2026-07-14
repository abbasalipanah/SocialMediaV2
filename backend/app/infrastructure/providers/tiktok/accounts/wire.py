"""Exact TikTok Business Accounts v1.3 request mapping."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import TIKTOK_APP_ID, TIKTOK_PROVIDER_PROFILE, TikTokConfig


class TikTokWireError(ValueError):
    pass


@dataclass(frozen=True)
class TikTokAccountsWireMapper:
    config: TikTokConfig

    def _assert_profile(self) -> None:
        if (
            self.config.provider_profile != TIKTOK_PROVIDER_PROFILE
            or self.config.app_id != TIKTOK_APP_ID
        ):
            raise TikTokWireError("provider_profile_mismatch")

    def authorization_fields(
        self, *, state: str, requested_scopes: tuple[str, ...]
    ) -> dict[str, str]:
        self._assert_profile()
        if not state:
            raise TikTokWireError("state_required")
        requested = set(requested_scopes)
        required = set(self.config.required_scopes)
        allowed = required | set(self.config.optional_scopes)
        if not required.issubset(requested) or not requested.issubset(allowed):
            raise TikTokWireError("scope_contract_mismatch")
        ordered_scopes = [
            scope
            for scope in (*self.config.required_scopes, *self.config.optional_scopes)
            if scope in requested
        ]
        return {
            "client_key": self.config.app_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": ",".join(ordered_scopes),
            "state": state,
        }

    def token_fields(self, *, auth_code: str) -> dict[str, str]:
        self._assert_secret_request(auth_code, "auth_code_required")
        return {
            "auth_code": auth_code,
            "client_id": self.config.app_id,
            "client_secret": self.config.app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": self.config.redirect_uri,
        }

    def refresh_fields(self, *, refresh_token: str) -> dict[str, str]:
        self._assert_secret_request(refresh_token, "refresh_token_required")
        return {
            "client_id": self.config.app_id,
            "client_secret": self.config.app_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

    def revoke_fields(self, *, access_token: str) -> dict[str, str]:
        self._assert_secret_request(access_token, "access_token_required")
        return {
            "access_token": access_token,
            "client_id": self.config.app_id,
            "client_secret": self.config.app_secret,
        }

    def _assert_secret_request(self, value: str, missing_error: str) -> None:
        self._assert_profile()
        if not self.config.app_secret:
            raise TikTokWireError("app_secret_missing")
        if not value:
            raise TikTokWireError(missing_error)
