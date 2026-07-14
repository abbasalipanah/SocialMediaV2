"""V2 Meta transport subprocess candidate."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.application.ports.platforms import ProviderCredential  # noqa: E402
from app.infrastructure.providers.meta.rate_guard import MetaRateGuard  # noqa: E402
from app.infrastructure.providers.meta.transport import MetaTransport  # noqa: E402


class ForwardingTransport(httpx.BaseTransport):
    def __init__(self, origin: str) -> None:
        self._origin = origin
        self._wire = httpx.HTTPTransport(retries=0)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        forwarded = httpx.Request(
            request.method,
            f"{self._origin}{request.url.raw_path.decode()}",
            headers=request.headers,
        )
        return self._wire.handle_request(forwarded)

    def close(self) -> None:
        self._wire.close()


def main() -> int:
    transport = MetaTransport(
        credential=ProviderCredential(access_token=os.environ["FIXTURE_PROVIDER_TOKEN"]),
        rate_guard=MetaRateGuard(sleeper=lambda _: None),
        wire=ForwardingTransport(os.environ["FAKE_META_ORIGIN"]),
        egress_enabled=True,
        max_retries=2,
        base_backoff_seconds=0,
        jitter=lambda _start, _end: 0,
    )
    profile = transport.get(
        "page-1",
        {"fields": "id,name,username,followers_count,fan_count"},
    )
    if os.getenv("PARITY_SCENARIO") == "retry":
        transport.close()
        print(
            json.dumps(
                {"followers": profile.get("followers_count") or profile.get("fan_count") or 0},
                sort_keys=True,
            )
        )
        return 0
    content_ids: list[str] = []
    cursor = None
    while True:
        page = transport.page(
            "page-1/published_posts",
            {"fields": "id", "limit": 100},
            cursor=cursor,
        )
        content_ids.extend(str(row["id"]) for row in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break
    transport.close()
    print(
        json.dumps(
            {
                "followers": profile.get("followers_count") or profile.get("fan_count") or 0,
                "content_ids": content_ids,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
