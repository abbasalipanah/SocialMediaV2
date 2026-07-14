"""Canonical application ports."""

from typing import Protocol

from .provisioning_store import ProjectionReplacement, ProjectionWrite, ProvisioningStore
from .reporting import ReportingStore
from .session_store import SessionStore


class AuthorityStore(SessionStore, ProvisioningStore, Protocol):
    """Combined schema-compatible store used by the first local adapter."""


__all__ = [
    "AuthorityStore",
    "ProjectionReplacement",
    "ProjectionWrite",
    "ProvisioningStore",
    "ReportingStore",
    "SessionStore",
]
