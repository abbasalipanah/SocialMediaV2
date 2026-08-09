#!/usr/bin/env python3
"""Capture and verify immutable source-project state without storing source data.

The baseline contains Git metadata and SHA-256 content manifests only. It never
copies source patches, file contents, credentials, or runtime artifacts into V2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "docs" / "revision6" / "r0"
BASELINE_FILE = REPORT_DIR / "source_baseline_revision6.json"
HISTORICAL_BASELINE_FILE = ROOT / "docs" / "fase0" / "source_baseline_v2.json"
SCHEMA_VERSION = 3
BASELINE_REVISION = 6
SOURCE_PROJECTS = {
    "SocialMedia": Path("/home/api/colab_scripts/SocialMedia"),
    "Accumulate": Path("/home/api/colab_scripts/Accumulate"),
    "performance_marketing": Path("/home/api/colab_scripts/performance_marketing"),
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


class BaselineError(RuntimeError):
    pass


def _run(project: Path, *args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(project), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise BaselineError(f"git {' '.join(args)} failed for {project}: {message}")
    if binary:
        return result.stdout
    return result.stdout.decode("utf-8", errors="surrogateescape")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _included(relative_path: str) -> bool:
    return not (set(PurePosixPath(relative_path).parts) & EXCLUDED_PARTS)


def _git_paths(project: Path) -> list[str]:
    tracked = str(_run(project, "ls-files", "-z")).split("\0")
    untracked = str(
        _run(project, "ls-files", "--others", "--exclude-standard", "-z")
    ).split("\0")
    return sorted({path for path in [*tracked, *untracked] if path and _included(path)})


def _untracked_paths(project: Path) -> list[str]:
    untracked = str(
        _run(project, "ls-files", "--others", "--exclude-standard", "-z")
    ).split("\0")
    # The untracked inventory is exact, including runtime artifacts. Only the
    # content manifest applies EXCLUDED_PARTS, so no artifact content is hashed.
    return sorted(path for path in untracked if path)


def _content_manifest(project: Path, paths: Iterable[str]) -> bytes:
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


def _snapshot(label: str, project: Path, write_manifest: bool) -> dict[str, object]:
    if not project.is_dir():
        raise BaselineError(f"source project missing: {project}")

    branch = str(_run(project, "branch", "--show-current")).strip()
    head = str(_run(project, "rev-parse", "HEAD")).strip()
    status = str(_run(project, "status", "--short", "--untracked-files=normal"))
    origin = str(_run(project, "remote", "get-url", "origin")).strip()
    diff = bytes(_run(project, "diff", "--binary", "HEAD", "--", binary=True))
    untracked_paths = _untracked_paths(project)
    paths = _git_paths(project)
    manifest = _content_manifest(project, paths)
    manifest_name = f"baseline_revision6_{label}_content.sha256"

    if write_manifest:
        (REPORT_DIR / manifest_name).write_bytes(manifest)

    return {
        "root": str(project),
        "branch": branch,
        "head": head,
        "origin": origin,
        "status": status.splitlines(),
        "status_sha256": _sha256(status.encode("utf-8", errors="surrogateescape")),
        "tracked_diff_sha256": _sha256(diff),
        "untracked_files": untracked_paths,
        "untracked_files_sha256": _sha256(
            "\0".join(untracked_paths).encode("utf-8", errors="surrogateescape")
        ),
        "content_manifest": manifest_name,
        "content_manifest_sha256": _sha256(manifest),
        "content_file_count": len(paths),
    }


def capture() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    projects = {
        label: _snapshot(label, project, write_manifest=True)
        for label, project in SOURCE_PROJECTS.items()
    }
    historical_baseline = {
        "path": str(HISTORICAL_BASELINE_FILE.relative_to(ROOT)),
        "relationship": "superseded_by_revision_6",
        "sha256": (
            _sha256(HISTORICAL_BASELINE_FILE.read_bytes())
            if HISTORICAL_BASELINE_FILE.is_file()
            else None
        ),
    }
    document = {
        "schema_version": SCHEMA_VERSION,
        "revision": BASELINE_REVISION,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "policy": (
            "branch+head+origin+status+tracked-binary-diff+exact-untracked-list+"
            "artifact-excluded-content-manifest"
        ),
        "excluded_path_parts": sorted(EXCLUDED_PARTS),
        "historical_baseline": historical_baseline,
        "projects": projects,
    }
    BASELINE_FILE.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"SOURCE BASELINE CAPTURED: {BASELINE_FILE}")


def verify() -> None:
    if not BASELINE_FILE.is_file():
        raise BaselineError(f"baseline missing: {BASELINE_FILE}")
    baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    if baseline.get("schema_version") != SCHEMA_VERSION:
        raise BaselineError("unsupported source baseline schema")
    if baseline.get("revision") != BASELINE_REVISION:
        raise BaselineError("source baseline revision mismatch")

    violations: list[str] = []
    for label, project in SOURCE_PROJECTS.items():
        expected = baseline["projects"].get(label)
        if not isinstance(expected, dict):
            violations.append(f"{label}: baseline entry missing")
            continue
        actual = _snapshot(label, project, write_manifest=False)
        for field in (
            "root",
            "branch",
            "head",
            "origin",
            "status",
            "status_sha256",
            "tracked_diff_sha256",
            "untracked_files",
            "untracked_files_sha256",
            "content_manifest_sha256",
            "content_file_count",
        ):
            if actual[field] != expected.get(field):
                violations.append(
                    f"{label}: {field} changed "
                    f"(expected={expected.get(field)!r}, actual={actual[field]!r})"
                )
        manifest_name = expected.get("content_manifest")
        if not isinstance(manifest_name, str):
            violations.append(f"{label}: content manifest name missing")
            continue
        manifest_path = REPORT_DIR / manifest_name
        if not manifest_path.is_file():
            violations.append(f"{label}: stored content manifest missing")
            continue
        stored_manifest_sha256 = _sha256(manifest_path.read_bytes())
        if stored_manifest_sha256 != expected.get("content_manifest_sha256"):
            violations.append(f"{label}: stored content manifest hash mismatch")

    if violations:
        raise BaselineError("SOURCE IMMUTABILITY VIOLATION:\n- " + "\n- ".join(violations))
    print("SOURCE WRITE GUARD PASS: source Git and content baselines match.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("capture", "verify"))
    parser.add_argument(
        "--approve-current-state",
        action="store_true",
        help="required acknowledgement when replacing the immutable baseline",
    )
    args = parser.parse_args()
    try:
        if args.command == "capture":
            if not args.approve_current_state:
                raise BaselineError("capture requires --approve-current-state")
            capture()
        else:
            verify()
    except (BaselineError, KeyError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
