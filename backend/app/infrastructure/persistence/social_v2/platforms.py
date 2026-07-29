"""Normalization for social platform identifiers stored by V2."""

from __future__ import annotations

from app.domain.platforms import PlatformId

PLATFORM_ALIASES = {
    "facebook_organic": PlatformId.FACEBOOK,
    "instagram_organic": PlatformId.INSTAGRAM,
    "tiktok_organic": PlatformId.TIKTOK,
}


def normalize_platform(raw_value: object) -> PlatformId:
    try:
        return PlatformId(str(raw_value))
    except ValueError:
        try:
            return PLATFORM_ALIASES[str(raw_value).lower()]
        except KeyError as exc:
            raise ValueError("unsupported_platform") from exc


__all__ = ["normalize_platform"]
