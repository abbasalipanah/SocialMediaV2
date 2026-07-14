"""Consume-only normalization for known historical platform values."""

from __future__ import annotations

from app.domain.platforms import PlatformId

LEGACY_PLATFORM_ALIASES = {
    "facebook_organic": PlatformId.FACEBOOK,
    "instagram_organic": PlatformId.INSTAGRAM,
    "tiktok_organic": PlatformId.TIKTOK,
}


def normalize_legacy_platform(raw_value: object) -> PlatformId:
    try:
        return PlatformId(str(raw_value))
    except ValueError:
        try:
            return LEGACY_PLATFORM_ALIASES[str(raw_value).lower()]
        except KeyError as exc:
            raise ValueError("unsupported_platform") from exc


__all__ = ["normalize_legacy_platform"]
