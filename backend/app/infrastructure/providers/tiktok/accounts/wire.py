"""Exact TikTok Business Accounts v1.3 request mapping."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from app.core.config import TIKTOK_APP_ID, TIKTOK_PROVIDER_PROFILE, TikTokConfig
from app.domain.metrics import MetricId

from .daily_metrics import MAX_TIKTOK_DAILY_WINDOW_DAYS, TIKTOK_DAILY_FIELDS


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

    def token_info_headers(self, *, access_token: str) -> dict[str, str]:
        self._assert_profile()
        if not access_token:
            raise TikTokWireError("access_token_required")
        return {"Access-Token": access_token}

    def profile_fields(self, *, business_id: str) -> dict[str, str]:
        self._assert_profile()
        if not business_id:
            raise TikTokWireError("business_id_required")
        return {
            "business_id": business_id,
            "fields": json.dumps(
                [
                    "business_id",
                    "display_name",
                    "username",
                    "profile_image",
                    "followers_count",
                    "likes",
                    "video_count",
                ],
                separators=(",", ":"),
            ),
        }

    def video_fields(
        self,
        *,
        business_id: str,
        cursor: str | None = None,
    ) -> dict[str, str]:
        self._assert_profile()
        if not business_id:
            raise TikTokWireError("business_id_required")
        fields = {
            "business_id": business_id,
            "fields": json.dumps(
                [
                    "item_id",
                    "thumbnail_url",
                    "share_url",
                    "embed_url",
                    "caption",
                    "likes",
                    "comments",
                    "shares",
                    "video_views",
                    MetricId.REACH.value,
                    "full_video_watched_rate",
                    "total_time_watched",
                    "average_time_watched",
                    "create_time",
                ],
                separators=(",", ":"),
            ),
        }
        if cursor:
            fields["cursor"] = cursor
        return fields

    def daily_metric_fields(
        self,
        *,
        business_id: str,
        since: date,
        until: date,
    ) -> dict[str, str]:
        self._assert_profile()
        if (
            not business_id
            or until < since
            or (until - since).days >= MAX_TIKTOK_DAILY_WINDOW_DAYS
        ):
            raise TikTokWireError("metric_range_invalid")
        return {
            "business_id": business_id,
            "fields": json.dumps(TIKTOK_DAILY_FIELDS, separators=(",", ":")),
            "start_date": since.isoformat(),
            "end_date": until.isoformat(),
        }

    def comment_fields(
        self,
        *,
        business_id: str,
        video_id: str,
        cursor: str | None = None,
    ) -> dict[str, str]:
        self._assert_profile()
        if not business_id or not video_id:
            raise TikTokWireError("comment_scope_required")
        fields = {
            "business_id": business_id,
            "video_id": video_id,
            "fields": json.dumps(
                [
                    "comment_id",
                    "video_id",
                    "text",
                    "create_time",
                    "likes",
                    "reply_comment_total",
                    "username",
                    "user_id",
                ],
                separators=(",", ":"),
            ),
        }
        if cursor:
            fields["cursor"] = cursor
        return fields

    def audience_fields(self, *, business_id: str, observed_on: date) -> dict[str, str]:
        self._assert_profile()
        if not business_id:
            raise TikTokWireError("business_id_required")
        return {
            "business_id": business_id,
            "fields": json.dumps(
                [
                    "audience_countries",
                    "audience_genders",
                    "audience_ages",
                    "audience_activity",
                ],
                separators=(",", ":"),
            ),
            "start_date": observed_on.isoformat(),
            "end_date": observed_on.isoformat(),
        }

    def _assert_secret_request(self, value: str, missing_error: str) -> None:
        self._assert_profile()
        if not self.config.app_secret:
            raise TikTokWireError("app_secret_missing")
        if not value:
            raise TikTokWireError(missing_error)
