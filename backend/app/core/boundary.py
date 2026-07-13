"""Explicit command/query endpoint classification."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import TypeVar


class Boundary(StrEnum):
    QUERY = "query"
    COMMAND = "command"
    PROTOCOL_COMMAND = "protocol_command"


F = TypeVar("F", bound=Callable[..., object])


def mark_boundary(boundary: Boundary) -> Callable[[F], F]:
    def decorator(function: F) -> F:
        function.__route_boundary__ = boundary.value
        return function

    return decorator
