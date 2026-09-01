"""Canonical product metadata for each social platform."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.platforms import PlatformId


@dataclass(frozen=True)
class PlatformDefinition:
    platform: PlatformId
    dashboard_tabs: frozenset[str]
    audience_source: str
    overview_enabled: bool

    @property
    def route(self) -> str:
        return self.platform.value


PLATFORM_CATALOG = (
    PlatformDefinition(
        platform=PlatformId.FACEBOOK,
        dashboard_tabs=frozenset({"cover", "page", "content", "audience"}),
        audience_source="meta_graph_api_v23",
        overview_enabled=True,
    ),
    PlatformDefinition(
        platform=PlatformId.INSTAGRAM,
        dashboard_tabs=frozenset({"cover", "page", "content", "stories", "audience"}),
        audience_source="meta_graph_api_v23",
        overview_enabled=True,
    ),
    PlatformDefinition(
        platform=PlatformId.TIKTOK,
        dashboard_tabs=frozenset({"cover", "account", "content", "audience"}),
        audience_source="tiktok_display_api",
        overview_enabled=True,
    ),
    PlatformDefinition(
        platform=PlatformId.X,
        dashboard_tabs=frozenset({"cover", "profile", "content", "audience"}),
        audience_source="x_api",
        overview_enabled=False,
    ),
    PlatformDefinition(
        platform=PlatformId.LINKEDIN,
        dashboard_tabs=frozenset({"cover", "page", "content", "audience"}),
        audience_source="linkedin_community_management_api",
        overview_enabled=False,
    ),
    PlatformDefinition(
        platform=PlatformId.YOUTUBE,
        dashboard_tabs=frozenset({"cover", "account", "content", "audience"}),
        audience_source="youtube_analytics_api",
        overview_enabled=False,
    ),
)

_BY_PLATFORM = {definition.platform: definition for definition in PLATFORM_CATALOG}


def platform_definition(platform: PlatformId) -> PlatformDefinition:
    try:
        return _BY_PLATFORM[platform]
    except KeyError as exc:
        raise LookupError("platform_definition_not_found") from exc


def overview_platforms() -> tuple[PlatformId, ...]:
    return tuple(
        definition.platform for definition in PLATFORM_CATALOG if definition.overview_enabled
    )


__all__ = [
    "PLATFORM_CATALOG",
    "PlatformDefinition",
    "overview_platforms",
    "platform_definition",
]
