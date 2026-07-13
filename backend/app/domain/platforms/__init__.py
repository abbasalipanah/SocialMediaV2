"""Canonical platform identifiers."""

from enum import StrEnum


class PlatformId(StrEnum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"

    @classmethod
    def exact_set(cls) -> set[str]:
        return {item.value for item in cls}


__all__ = ["PlatformId"]
