#!/usr/bin/env python3
"""Reject forbidden product vocabulary from runtime and build surfaces."""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = ROOT / "frontend" / "dist"
BACKEND_DIST = ROOT / "backend" / "dist"
SCAN_ROOTS = (
    ROOT / "backend" / "app",
    ROOT / "frontend" / "src",
    ROOT / "frontend" / "public",
    ROOT / "deploy",
    FRONTEND_DIST,
)
SCAN_FILES = (
    ROOT / "backend" / ".env.example",
    ROOT / "frontend" / ".env.example",
    ROOT / "frontend" / "vite.config.ts",
)
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".py",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
PATTERNS = {
    "forbidden product term": re.compile(r"(?i)(?<![a-z0-9])(client|ars|media[ _-]?planner)(?![a-z0-9])"),
    "forbidden platform suffix": re.compile(
        r"(?i)(facebook|instagram|tiktok)[ _-]*organic|organic[ _-]*(facebook|instagram|tiktok)|/organic\b"
    ),
}
ARTIFACT_PATTERNS = {
    "forbidden product term": re.compile(
        r"(?i)(?<![a-z0-9])(ars|media[ _-]?planner)(?![a-z0-9])"
    ),
    "forbidden platform suffix": PATTERNS["forbidden platform suffix"],
}
FRONTEND_VENDOR_ALLOWLIST = (
    "QueryClientProvider",
    "QueryClient",
    'client={queryCache}',
    '"react-dom/client"',
)
TIKTOK_WIRE_ALIAS_FILE = (
    ROOT / "backend" / "app" / "infrastructure" / "providers" / "tiktok" / "accounts" / "wire.py"
)
TIKTOK_WIRE_ALIASES = ("client_key", "client_id", "client_secret")
LEGACY_PLATFORM_ALIAS_FILE = (
    ROOT
    / "backend"
    / "app"
    / "infrastructure"
    / "persistence"
    / "legacy_socialmedia"
    / "platforms.py"
)
LEGACY_PLATFORM_ALIASES = (
    "facebook_organic",
    "instagram_organic",
    "tiktok_organic",
)


def apply_narrow_source_allowlist(path: Path, text: str) -> str:
    aliases: tuple[str, ...] = ()
    if path == TIKTOK_WIRE_ALIAS_FILE:
        aliases = TIKTOK_WIRE_ALIASES
    elif path == LEGACY_PLATFORM_ALIAS_FILE:
        aliases = LEGACY_PLATFORM_ALIASES
    for alias in aliases:
        text = text.replace(f'"{alias}"', '""').replace(f"'{alias}'", "''")
    return text


def apply_narrow_artifact_allowlist(member: str, text: str) -> str:
    if member.endswith("app/infrastructure/persistence/legacy_socialmedia/platforms.py"):
        for alias in LEGACY_PLATFORM_ALIASES:
            text = text.replace(f'"{alias}"', '""').replace(f"'{alias}'", "''")
    return text


def files_to_scan() -> list[Path]:
    paths = [path for path in SCAN_FILES if path.is_file()]
    for root in SCAN_ROOTS:
        if root.is_dir():
            paths.extend(
                path for path in root.rglob("*") if path.is_file() and path.suffix in TEXT_SUFFIXES
            )
    return sorted(set(paths))


def scan_text(label: str, text: str, patterns: dict[str, re.Pattern[str]]) -> list[str]:
    findings: list[str] = []
    for finding_label, pattern in patterns.items():
        if match := pattern.search(text):
            findings.append(f"{label}: {finding_label}: {match.group(0)!r}")
    return findings


def main() -> int:
    findings: list[str] = []
    for path in files_to_scan():
        text = path.read_text(encoding="utf-8", errors="ignore")
        is_built_artifact = FRONTEND_DIST in path.parents
        if path.suffix in {".ts", ".tsx", ".js", ".jsx"} and not is_built_artifact:
            for exact_vendor_token in FRONTEND_VENDOR_ALLOWLIST:
                text = text.replace(exact_vendor_token, "")
        if not is_built_artifact:
            text = apply_narrow_source_allowlist(path, text)
        patterns = ARTIFACT_PATTERNS if is_built_artifact else PATTERNS
        findings.extend(scan_text(str(path.relative_to(ROOT)), text, patterns))
    if BACKEND_DIST.is_dir():
        for wheel in BACKEND_DIST.glob("*.whl"):
            with zipfile.ZipFile(wheel) as archive:
                for member in archive.namelist():
                    if Path(member).suffix not in TEXT_SUFFIXES:
                        continue
                    text = archive.read(member).decode("utf-8", errors="ignore")
                    text = apply_narrow_artifact_allowlist(member, text)
                    findings.extend(
                        scan_text(
                            f"{wheel.relative_to(ROOT)}!/{member}",
                            text,
                            ARTIFACT_PATTERNS,
                        )
                    )
    if findings:
        print("\n".join(findings), file=sys.stderr)
        return 1
    print("OK: canonical vocabulary guard clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
