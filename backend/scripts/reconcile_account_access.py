#!/usr/bin/env python3
"""Preview or apply exact V2 account access reconciliation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import create_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core import WritePolicy, load_settings  # noqa: E402
from app.infrastructure.persistence.social_v2.access_reconciliation import (  # noqa: E402
    RECONCILIATION_REASONS,
    AccountAccessReconciliationStore,
    parse_exact_account_ref,
)


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Remove exact inaccessible accounts from V2 collection while preserving history. "
            "The default is a read-only preview; pass --apply to commit."
        )
    )
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument(
        "--account",
        action="append",
        required=True,
        metavar="LINK_ID:BRAND_ID:PLATFORM:EXTERNAL_ID",
    )
    parser.add_argument("--reason", choices=tuple(sorted(RECONCILIATION_REASONS)), required=True)
    parser.add_argument("--revoke-tiktok-credentials", action="store_true")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def _load_env(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    _load_env(args.env)
    settings = load_settings()
    if not settings.db.url:
        raise RuntimeError("SOCIAL_DB_URL_required")
    targets = tuple(parse_exact_account_ref(value) for value in args.account)
    engine = create_engine(settings.db.url, pool_pre_ping=True, pool_size=1, max_overflow=0)
    try:
        results = AccountAccessReconciliationStore(
            engine,
            WritePolicy.from_settings(settings),
        ).reconcile(
            targets,
            reason=args.reason,
            apply=args.apply,
            revoke_tiktok_credentials=args.revoke_tiktok_credentials,
        )
        print(json.dumps([asdict(result) for result in results], separators=(",", ":")))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
