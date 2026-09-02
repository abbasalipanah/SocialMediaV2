"""Strict parsing for LinkedIn paging links."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlparse

from .responses import LinkedInResponseError, required_mapping, required_text


def next_posts_cursor(payload: Mapping[str, Any]) -> str | None:
    paging = required_mapping(payload, "paging")
    links = paging.get("links", [])
    if not isinstance(links, list) or len(links) > 10:
        raise LinkedInResponseError("linkedin_posts_paging_invalid")
    next_values: list[str] = []
    for item in links:
        if not isinstance(item, Mapping):
            raise LinkedInResponseError("linkedin_posts_paging_invalid")
        if item.get("rel") != "next":
            continue
        href = required_text(item, "href")
        parsed = urlparse(href)
        values = parse_qs(parsed.query).get("start", [])
        if len(values) != 1 or not values[0].isdigit() or int(values[0]) < 1:
            raise LinkedInResponseError("linkedin_posts_paging_invalid")
        next_values.append(values[0])
    if len(next_values) > 1:
        raise LinkedInResponseError("linkedin_posts_paging_invalid")
    return next_values[0] if next_values else None


__all__ = ["next_posts_cursor"]
