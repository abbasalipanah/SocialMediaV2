#!/usr/bin/env python3
"""Dependency-free static preflight for the Faz 1 certification suite."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def require(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"MISSING: {path.relative_to(ROOT)}")


def check_python_syntax() -> None:
    for path in (BACKEND / "app").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def check_canonical_tree() -> None:
    require(BACKEND / "app" / "main.py")
    require(BACKEND / "app" / "core" / "config.py")
    require(BACKEND / "app" / "core" / "write_policy.py")
    if (BACKEND / "src" / "social_media_v2").exists():
        raise SystemExit("PARALLEL BACKEND TREE: backend/src/social_media_v2")


def check_manifests() -> None:
    for path in (
        BACKEND / "pyproject.toml",
        BACKEND / "requirements.txt",
        BACKEND / "requirements.lock",
        BACKEND / "requirements-dev.lock",
        FRONTEND / "package.json",
        FRONTEND / "package-lock.json",
        FRONTEND / "index.html",
        FRONTEND / "vite.config.ts",
        FRONTEND / "tsconfig.json",
    ):
        require(path)
    package_lock = json.loads((FRONTEND / "package-lock.json").read_text(encoding="utf-8"))
    if len(package_lock.get("packages", {})) <= 1:
        raise SystemExit("frontend/package-lock.json is not a resolved lock")


def check_environment_contract() -> None:
    env = (BACKEND / ".env.example").read_text(encoding="utf-8")
    for line in (
        "SOCIAL_WRITES_ENABLED=false",
        "SOCIAL_TIKTOK_BUSINESS_APP_ID=7657818426198474768",
        "SOCIAL_TIKTOK_ACCOUNT_ENABLED=false",
        "SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE=disabled",
        "SOCIAL_TIKTOK_COLLECTION_ENABLED=false",
        "SOCIAL_TIKTOK_ADVERTISER_ENABLED=false",
    ):
        if line not in env.splitlines():
            raise SystemExit(f"ENV CONTRACT MISSING: {line}")


def run_guard(relative_path: str) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / relative_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise SystemExit(result.stdout + result.stderr)


def main() -> None:
    check_python_syntax()
    check_canonical_tree()
    check_manifests()
    check_environment_contract()
    run_guard("scripts/quality/check_canonical_vocabulary.py")
    print("OK: Faz 1 static smoke checks passed.")


if __name__ == "__main__":
    main()
