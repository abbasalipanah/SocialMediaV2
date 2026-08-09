#!/usr/bin/env python3
"""Export the deterministic downstream OpenAPI contract without starting a server."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.main import create_app  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the canonical OpenAPI file differs without rewriting it.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/contracts/social-media-v2-openapi.json",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if ROOT not in output.parents:
        raise SystemExit("output_must_be_inside_repository")
    rendered = json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
            raise SystemExit("openapi_contract_is_stale")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
