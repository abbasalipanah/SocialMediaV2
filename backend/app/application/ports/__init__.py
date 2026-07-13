"""Canonical application ports."""

from typing import Protocol

from .provisioning_store import ProvisioningStore
from .session_store import SessionStore


class AuthorityStore(SessionStore, ProvisioningStore, Protocol):
    """Combined schema-compatible store used by the first local adapter."""


__all__ = ["AuthorityStore", "ProvisioningStore", "SessionStore"]
