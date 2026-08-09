#!/usr/bin/env python3
"""Capture and verify the approved V2 working-tree state at Revision 6 / R0.

R0's own guard and evidence files are excluded so the pre-existing application
work can be preserved and verified while R0 documentation is added around it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "docs" / "revision6" / "r0"
BASELINE_FILE = REPORT_DIR / "v2_wip_baseline_revision6.json"
MANIFEST_FILE = REPORT_DIR / "v2_wip_baseline_revision6.sha256"
R0_OWNED_EXACT_PATHS = {
    "scripts/quality/source_baseline.py",
    "scripts/quality/v2_wip_baseline.py",
    "scripts/source_write_guard.sh",
}
R0_OWNED_PREFIXES = ("docs/revision6/r0/",)

BEHAVIOR_INVENTORY = {
    "backend/app/api/dashboards/__init__.py": (
        "Dashboard API router registration changed for the in-progress parity work."
    ),
    "backend/app/local_demo.py": (
        "Local demo payload generation expanded, including audience/dashboard data."
    ),
    "backend/tests/test_local_demo.py": (
        "Local demo expectations adjusted for the expanded payload."
    ),
    "docs/SOCIAL_MEDIA_V2_MASTER_PLAN.md": (
        "Approved Revision 6 execution plan and read-only source rules."
    ),
    "frontend/package-lock.json": (
        "Frontend dependency lock updated by the pre-existing UI work."
    ),
    "frontend/package.json": (
        "Frontend dependency declarations updated by the pre-existing UI work."
    ),
    "frontend/src/features/dashboard/AudienceDemographicsCard.tsx": (
        "New shared audience-demographics card implementation."
    ),
    "frontend/src/features/dashboard/PlatformPage.tsx": (
        "Platform-page composition adjusted for the in-progress dashboards."
    ),
    "frontend/src/features/dashboard/catalog.ts": (
        "Dashboard catalog metadata adjusted for the in-progress dashboards."
    ),
    "frontend/src/features/facebook/FacebookPulseDashboard.tsx": (
        "Facebook dashboard expanded with the in-progress pulse/audience UI."
    ),
    "frontend/src/features/instagram/InstagramPulseDashboard.tsx": (
        "Instagram dashboard expanded with the in-progress pulse/audience UI."
    ),
    "frontend/src/features/tiktok/TikTokPulseDashboard.tsx": (
        "TikTok dashboard expanded with the in-progress pulse/audience UI."
    ),
    "frontend/src/styles.css": (
        "Shared dashboard styling expanded for the in-progress UI."
    ),
    "frontend/src/test/Phase8Products.test.tsx": (
        "Frontend product test coverage adjusted for the in-progress UI."
    ),
}


class BaselineError(RuntimeError):
    pass


def _run(*args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise BaselineError(f"git {' '.join(args)} failed: {message}")
    if binary:
        return result.stdout
    return result.stdout.decode("utf-8", errors="surrogateescape")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_r0_owned(path: str) -> bool:
    return path in R0_OWNED_EXACT_PATHS or path.startswith(R0_OWNED_PREFIXES)


def _paths(*args: str) -> list[str]:
    output = str(_run(*args))
    return sorted(path for path in output.split("\0") if path and not _is_r0_owned(path))


def _pathspec() -> list[str]:
    return [
        ".",
        *[f":(exclude){path}" for path in sorted(R0_OWNED_EXACT_PATHS)],
        *[f":(exclude){prefix}**" for prefix in R0_OWNED_PREFIXES],
    ]


def _file_payload(path: Path) -> bytes:
    if path.is_symlink():
        return b"symlink\0" + os.readlink(path).encode(
            "utf-8", errors="surrogateescape"
        )
    if path.is_file():
        return b"file\0" + path.read_bytes()
    return b"missing\0"


def _numstat() -> dict[str, dict[str, int | str]]:
    output = str(_run("diff", "--numstat", "HEAD", "--", *_pathspec()))
    result: dict[str, dict[str, int | str]] = {}
    for line in output.splitlines():
        additions, deletions, path = line.split("\t", 2)
        if _is_r0_owned(path):
            continue
        result[path] = {
            "additions": int(additions) if additions.isdigit() else additions,
            "deletions": int(deletions) if deletions.isdigit() else deletions,
        }
    return result


def _snapshot(write_manifest: bool) -> dict[str, object]:
    tracked = _paths("diff", "--name-only", "-z", "HEAD", "--", *_pathspec())
    untracked = _paths("ls-files", "--others", "--exclude-standard", "-z")
    dirty_paths = sorted(set(tracked) | set(untracked))
    status = str(
        _run("status", "--short", "--untracked-files=all", "--", *_pathspec())
    )
    diff = bytes(
        _run("diff", "--binary", "HEAD", "--", *_pathspec(), binary=True)
    )
    stats = _numstat()
    files: list[dict[str, object]] = []
    manifest_records: list[bytes] = []

    for relative_path in dirty_paths:
        payload = _file_payload(ROOT / relative_path)
        digest = _sha256(payload)
        encoded_path = relative_path.encode("utf-8", errors="surrogateescape")
        manifest_records.append(digest.encode("ascii") + b"  " + encoded_path + b"\n")
        files.append(
            {
                "path": relative_path,
                "state": "untracked" if relative_path in untracked else "tracked-diff",
                "content_sha256": digest,
                "diff": stats.get(relative_path),
                "behavior": BEHAVIOR_INVENTORY.get(
                    relative_path, "Unclassified approved pre-existing WIP."
                ),
            }
        )

    manifest = b"".join(manifest_records)
    if write_manifest:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        MANIFEST_FILE.write_bytes(manifest)

    branch = str(_run("branch", "--show-current")).strip()
    head = str(_run("rev-parse", "HEAD")).strip()
    origin = str(_run("remote", "get-url", "origin")).strip()
    return {
        "root": str(ROOT),
        "branch": branch,
        "head": head,
        "origin": origin,
        "status": status.splitlines(),
        "status_sha256": _sha256(status.encode("utf-8", errors="surrogateescape")),
        "tracked_binary_diff_sha256": _sha256(diff),
        "untracked_files": untracked,
        "untracked_files_sha256": _sha256(
            "\0".join(untracked).encode("utf-8", errors="surrogateescape")
        ),
        "dirty_file_count": len(dirty_paths),
        "manifest": MANIFEST_FILE.name,
        "manifest_sha256": _sha256(manifest),
        "files": files,
    }


def capture() -> None:
    snapshot = _snapshot(write_manifest=True)
    document = {
        "schema_version": 1,
        "revision": 6,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "approved_pre_existing_v2_wip_at_r0_entry",
        "r0_owned_exact_paths_excluded": sorted(R0_OWNED_EXACT_PATHS),
        "r0_owned_prefixes_excluded": list(R0_OWNED_PREFIXES),
        "snapshot": snapshot,
    }
    BASELINE_FILE.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"V2 WIP BASELINE CAPTURED: {BASELINE_FILE}")


def verify() -> None:
    if not BASELINE_FILE.is_file():
        raise BaselineError(f"V2 WIP baseline missing: {BASELINE_FILE}")
    baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    if baseline.get("schema_version") != 1 or baseline.get("revision") != 6:
        raise BaselineError("unsupported V2 WIP baseline schema or revision")
    expected = baseline.get("snapshot")
    if not isinstance(expected, dict):
        raise BaselineError("V2 WIP snapshot missing")
    actual = _snapshot(write_manifest=False)
    fields = (
        "root",
        "branch",
        "head",
        "origin",
        "status",
        "status_sha256",
        "tracked_binary_diff_sha256",
        "untracked_files",
        "untracked_files_sha256",
        "dirty_file_count",
        "manifest_sha256",
        "files",
    )
    violations = [field for field in fields if actual[field] != expected.get(field)]
    if not MANIFEST_FILE.is_file():
        violations.append("stored_manifest_missing")
    elif _sha256(MANIFEST_FILE.read_bytes()) != expected.get("manifest_sha256"):
        violations.append("stored_manifest_sha256")
    if violations:
        raise BaselineError(
            "V2 WIP BASELINE VIOLATION: changed fields: " + ", ".join(violations)
        )
    print("V2 WIP BASELINE PASS: approved pre-existing V2 work is unchanged.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("capture", "verify"))
    parser.add_argument("--approve-current-state", action="store_true")
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
