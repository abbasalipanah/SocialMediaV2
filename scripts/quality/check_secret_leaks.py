#!/usr/bin/env python3
"""Reject committed private keys, provider tokens, and non-empty secret templates."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (
    ROOT / "backend" / "app",
    ROOT / "backend" / "scripts",
    ROOT / "frontend" / "src",
    ROOT / "frontend" / "public",
    ROOT / "deploy",
)
SCAN_FILES = (ROOT / "backend" / ".env.example", ROOT / "frontend" / ".env.example")
TEXT_SUFFIXES = {".env", ".json", ".py", ".ts", ".tsx", ".yaml", ".yml"}
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "cloud access key": re.compile(r"(?<![A-Z0-9])AKIA[A-Z0-9]{16}(?![A-Z0-9])"),
    "repository token": re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{20,}"),
    "api token": re.compile(r"(?<![A-Za-z0-9])sk-(?:proj|live)-[A-Za-z0-9_-]{20,}"),
    "workspace token": re.compile(r"(?<![A-Za-z0-9])xox[baprs]-[A-Za-z0-9-]{20,}"),
}
NONEMPTY_SECRET_ENV = re.compile(
    r"(?im)^(?:SOCIAL|VITE)_[A-Z0-9_]*(?:SECRET|ACCESS_TOKEN|REFRESH_TOKEN|KEYRING_JSON)="
    r"(?![ \t]*(?:#.*)?$).+"
)
PYTHON_SECRET_LITERAL = re.compile(
    r"(?i)(?<![a-z0-9_])(app_secret|access_token|refresh_token)\s*=\s*['\"][^'\"]+['\"]"
)


def files_to_scan() -> list[Path]:
    paths = [path for path in SCAN_FILES if path.is_file()]
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        paths.extend(
            path for path in root.rglob("*") if path.is_file() and path.suffix in TEXT_SUFFIXES
        )
    return sorted(set(paths))


def main() -> int:
    findings: list[str] = []
    for path in files_to_scan():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}: {label}")
        if NONEMPTY_SECRET_ENV.search(text):
            findings.append(f"{path.relative_to(ROOT)}: non-empty secret template")
        if path.suffix == ".py" and PYTHON_SECRET_LITERAL.search(text):
            findings.append(f"{path.relative_to(ROOT)}: credential literal")
    if findings:
        print("\n".join(findings), file=sys.stderr)
        return 1
    print("OK: repository secret leak guard clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
