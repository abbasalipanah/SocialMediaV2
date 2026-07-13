"""Hashing and constant-time security helpers."""

from __future__ import annotations

import hashlib
import hmac


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def secure_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("ascii"), right.encode("ascii"))
