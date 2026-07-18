"""TikTok account permission gate."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import TikTokConfig


@dataclass(frozen=True)
class ScopeDecision:
    granted: tuple[str, ...]
    missing_required: tuple[str, ...]
    granted_optional: tuple[str, ...]
    forbidden: tuple[str, ...]

    @property
    def permitted(self) -> bool:
        return not self.missing_required and not self.forbidden


def evaluate_scopes(config: TikTokConfig, granted_scopes: tuple[str, ...]) -> ScopeDecision:
    if len(granted_scopes) != len(set(granted_scopes)) or any(
        not scope.strip() for scope in granted_scopes
    ):
        raise ValueError("scope_payload_invalid")
    granted = set(granted_scopes)
    required = set(config.required_scopes)
    optional = set(config.optional_scopes)
    return ScopeDecision(
        granted=tuple(granted_scopes),
        missing_required=tuple(scope for scope in config.required_scopes if scope not in granted),
        granted_optional=tuple(scope for scope in config.optional_scopes if scope in granted),
        forbidden=tuple(sorted(granted - required - optional)),
    )


__all__ = ["ScopeDecision", "evaluate_scopes"]
