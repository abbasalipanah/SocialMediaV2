"""Central fail-closed mutation policy."""

from __future__ import annotations

from dataclasses import dataclass

from .config import AppSettings, RuntimeMode


@dataclass(frozen=True)
class WritePolicy:
    runtime_mode: RuntimeMode
    writes_enabled: bool

    @classmethod
    def from_settings(cls, settings: AppSettings) -> WritePolicy:
        return cls(
            runtime_mode=settings.runtime_mode,
            writes_enabled=settings.social_writes_enabled,
        )

    def allows(self, command: str) -> bool:
        del command
        return (
            self.runtime_mode
            in {RuntimeMode.DEVELOPMENT, RuntimeMode.STAGING, RuntimeMode.ACTIVE}
            and self.writes_enabled
        )

    def assert_allows_mutation(self, command: str) -> None:
        if not self.allows(command):
            raise PermissionError("Mutation is disabled by the current runtime policy")
