#!/usr/bin/env python3
"""Freeze and verify the protected source trees for the V2 cutover work.

This guard is intentionally separate from the historical Revision 6 baseline.
It records only Git metadata and SHA-256 fingerprints; it never copies source
contents, patches, credentials, or runtime data into the V2 repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
BASELINE_FILE = ROOT / "docs" / "cutover" / "phase_a_protected_source_baseline.json"
SCHEMA_VERSION = 1
PROTECTED_PROJECTS = {
    "SocialMediaV1": Path("/home/api/colab_scripts/SocialMedia"),
    "Accumulate": Path("/home/api/colab_scripts/Accumulate"),
    "AccumulateRuntime": Path("/home/api/colab_scripts/Accumulate-prelive-main"),
}
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "build",
    "dist",
    "logs",
    "playwright-report",
    "test-results",
    "tmp",
}


class GuardError(RuntimeError):
    """Raised when a protected source fingerprint cannot be trusted."""


def _git(project: Path, *args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(project), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise GuardError(f"git {' '.join(args)} failed for {project}: {message}")
    if binary:
        return result.stdout
    return result.stdout.decode("utf-8", errors="surrogateescape")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _included(relative_path: str) -> bool:
    path = PurePosixPath(relative_path)
    return not (set(path.parts) & EXCLUDED_PARTS)


def _secret_env(relative_path: str) -> bool:
    name = PurePosixPath(relative_path).name
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def _paths(project: Path, *, exclude_secret_env: bool) -> list[str]:
    tracked = str(_git(project, "ls-files", "-z")).split("\0")
    untracked = str(
        _git(project, "ls-files", "--others", "--exclude-standard", "-z")
    ).split("\0")
    return sorted(
        {
            path
            for path in (*tracked, *untracked)
            if path
            and _included(path)
            and not (exclude_secret_env and _secret_env(path))
        }
    )


def _manifest(project: Path, paths: Iterable[str]) -> bytes:
    records: list[bytes] = []
    for relative_path in paths:
        path = project / relative_path
        encoded_path = relative_path.encode("utf-8", errors="surrogateescape")
        if path.is_symlink():
            payload = b"symlink\0" + os.readlink(path).encode(
                "utf-8", errors="surrogateescape"
            )
        elif path.is_file():
            payload = b"file\0" + path.read_bytes()
        else:
            payload = b"missing\0"
        records.append(_sha256(payload).encode("ascii") + b"  " + encoded_path + b"\n")
    return b"".join(records)


def _snapshot(project: Path, *, exclude_secret_env: bool = False) -> dict[str, object]:
    if not project.is_dir():
        raise GuardError(f"protected project missing: {project}")
    status = str(_git(project, "status", "--short", "--untracked-files=all"))
    diff = bytes(_git(project, "diff", "--binary", "HEAD", "--", binary=True))
    origin = str(_git(project, "remote", "get-url", "origin")).strip()
    paths = _paths(project, exclude_secret_env=exclude_secret_env)
    manifest = _manifest(project, paths)
    return {
        "root": str(project),
        "branch": str(_git(project, "branch", "--show-current")).strip(),
        "head": str(_git(project, "rev-parse", "HEAD")).strip(),
        "origin_sha256": _sha256(origin.encode("utf-8", errors="surrogateescape")),
        "status": status.splitlines(),
        "status_sha256": _sha256(status.encode("utf-8", errors="surrogateescape")),
        "tracked_diff_sha256": _sha256(diff),
        "content_manifest_sha256": _sha256(manifest),
        "content_file_count": len(paths),
    }


def capture() -> None:
    if BASELINE_FILE.exists():
        raise GuardError(f"refusing to replace cutover baseline: {BASELINE_FILE}")
    document = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": datetime.now(UTC).isoformat(),
        "policy": "git-metadata-and-content-fingerprints-only",
        "projects": {
            label: _snapshot(project, exclude_secret_env=label == "AccumulateRuntime")
            for label, project in PROTECTED_PROJECTS.items()
        },
    }
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"CUTOVER PROTECTED SOURCE BASELINE CAPTURED: {BASELINE_FILE}")


def supplement() -> None:
    if not BASELINE_FILE.is_file():
        raise GuardError(f"cutover baseline missing: {BASELINE_FILE}")
    baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    if baseline.get("schema_version") != SCHEMA_VERSION:
        raise GuardError("cutover baseline schema mismatch")
    projects = baseline.get("projects")
    if not isinstance(projects, dict):
        raise GuardError("cutover baseline projects missing")
    missing = {
        label: project for label, project in PROTECTED_PROJECTS.items() if label not in projects
    }
    if not missing:
        raise GuardError("cutover baseline has no missing protected projects")
    projects.update(
        {
            label: _snapshot(project, exclude_secret_env=label == "AccumulateRuntime")
            for label, project in missing.items()
        }
    )
    baseline["supplemented_at"] = datetime.now(UTC).isoformat()
    BASELINE_FILE.write_text(
        json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("CUTOVER PROTECTED SOURCE BASELINE SUPPLEMENTED: " + ",".join(missing))


def verify() -> None:
    if not BASELINE_FILE.is_file():
        raise GuardError(f"cutover baseline missing: {BASELINE_FILE}")
    baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    if baseline.get("schema_version") != SCHEMA_VERSION:
        raise GuardError("cutover baseline schema mismatch")
    violations: list[str] = []
    for label, project in PROTECTED_PROJECTS.items():
        expected = baseline.get("projects", {}).get(label)
        if not isinstance(expected, dict):
            violations.append(f"{label}: baseline entry missing")
            continue
        actual = _snapshot(project, exclude_secret_env=label == "AccumulateRuntime")
        for field, actual_value in actual.items():
            if actual_value != expected.get(field):
                violations.append(f"{label}: {field} changed")
    if violations:
        raise GuardError("CUTOVER PROTECTED SOURCE VIOLATION:\n- " + "\n- ".join(violations))
    print("CUTOVER PROTECTED SOURCE GUARD PASS: V1 and Accumulate are unchanged.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("capture", "supplement", "verify"))
    args = parser.parse_args()
    try:
        if args.command == "capture":
            capture()
        elif args.command == "supplement":
            supplement()
        else:
            verify()
    except (GuardError, KeyError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
