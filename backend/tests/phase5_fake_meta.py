"""Deterministic localhost HTTP provider fixture."""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit


@dataclass(frozen=True)
class RecordedRequest:
    path: str
    query: dict[str, str]
    authorization_present: bool


class FakeMetaServer:
    def __init__(self, fixture_path: Path) -> None:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.expected = fixture["expected"]
        self._routes: dict[tuple[str, str | None], list[dict[str, Any]]] = {}
        for route in fixture["routes"]:
            self._routes[(route["path"], route["after"])] = deepcopy(route["responses"])
        self.requests: list[RecordedRequest] = []
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                split = urlsplit(self.path)
                query_values = parse_qs(split.query, keep_blank_values=True)
                query = {key: values[-1] for key, values in query_values.items()}
                after = query.get("after")
                with outer._lock:
                    outer.requests.append(
                        RecordedRequest(
                            path=split.path,
                            query=query,
                            authorization_present=bool(self.headers.get("Authorization")),
                        )
                    )
                    responses = outer._routes.get((split.path, after))
                    response = responses.pop(0) if responses else None
                if response is None:
                    self._send(404, {"error": {"message": "fixture_route_missing"}})
                    return
                self._send(int(response["status"]), response["json"], response.get("headers"))

            def _send(
                self,
                status: int,
                payload: Mapping[str, Any],
                headers: Mapping[str, str] | None = None,
            ) -> None:
                body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def origin(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)
        self._server.server_close()


__all__ = ["FakeMetaServer", "RecordedRequest"]
