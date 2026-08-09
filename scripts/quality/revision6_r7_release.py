#!/usr/bin/env python3
"""R7 source/package gate for a standalone Social Media V2 release candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


SOURCE_PATH_PATTERN = re.compile(rb"/home/api/colab_scripts/|file://")
FORBIDDEN_RUNTIME_PATTERNS = {
    "historical runtime mode": re.compile(rb"cutover_(?:read_only|credential|canary|control|activation)"),
    "provisioning endpoint": re.compile(rb"/internal/provisioning/events"),
    "local source API": re.compile(rb"https?://(?:127\.0\.0\.1|localhost):8000"),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "repository token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    "API token": re.compile(rb"sk-(?:proj|live)-[A-Za-z0-9_-]{20,}"),
    "workspace token": re.compile(rb"xox[baprs]-[A-Za-z0-9-]{20,}"),
}
FORBIDDEN_PLATFORM_SUFFIX = re.compile(
    rb"(?i)(facebook|instagram|tiktok)[ _-]*organic|"
    rb"organic[ _-]*(facebook|instagram|tiktok)|/organic\b"
)
FORBIDDEN_PRODUCT_TERM = re.compile(rb"(?i)(?<![a-z0-9])(ars|media[ _-]?planner)(?![a-z0-9])")
CANONICAL_TIKTOK_UNAVAILABLE_COPY = b"Not provided by TikTok Organic API"
LEGACY_PLATFORM_ALIAS_MEMBER = (
    "wheel:app/infrastructure/persistence/legacy_socialmedia/platforms.py"
)
LEGACY_PLATFORM_ALIASES = (
    b"facebook_organic",
    b"instagram_organic",
    b"tiktok_organic",
)


def fail(message: str) -> None:
    raise SystemExit(f"R7 RELEASE CHECK FAILED: {message}")


def digest(path: Path) -> dict[str, object]:
    return {
        "name": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": path.stat().st_size,
    }


def scan_bytes(label: str, payload: bytes) -> None:
    if SOURCE_PATH_PATTERN.search(payload):
        fail(f"source filesystem path leaked into {label}")
    for finding, pattern in FORBIDDEN_RUNTIME_PATTERNS.items():
        if pattern.search(payload):
            fail(f"{finding} leaked into {label}")
    normalized = payload.replace(CANONICAL_TIKTOK_UNAVAILABLE_COPY, b"")
    if label == LEGACY_PLATFORM_ALIAS_MEMBER:
        for alias in LEGACY_PLATFORM_ALIASES:
            normalized = normalized.replace(b'"' + alias + b'"', b'""')
            normalized = normalized.replace(b"'" + alias + b"'", b"''")
    if FORBIDDEN_PLATFORM_SUFFIX.search(normalized):
        fail(f"forbidden platform suffix leaked into {label}")
    if FORBIDDEN_PRODUCT_TERM.search(normalized):
        fail(f"forbidden product vocabulary leaked into {label}")


def scan_frontend(frontend_dist: Path) -> tuple[int, list[dict[str, object]]]:
    if not (frontend_dist / "index.html").is_file():
        fail("frontend build is missing index.html")
    files = tuple(path for path in frontend_dist.rglob("*") if path.is_file())
    if not any(path.suffix == ".js" for path in files):
        fail("frontend build has no JavaScript artifact")
    for path in files:
        scan_bytes(f"frontend:{path.relative_to(frontend_dist)}", path.read_bytes())
    return len(files), [digest(path) for path in files]


def scan_wheel(wheel: Path) -> tuple[int, list[dict[str, object]]]:
    if wheel.suffix != ".whl" or not wheel.is_file():
        fail("backend wheel is missing")
    members: list[dict[str, object]] = []
    with zipfile.ZipFile(wheel) as archive:
        names = tuple(archive.namelist())
        if not any(name == "app/main.py" for name in names):
            fail("backend wheel is missing canonical app/main.py")
        if any(name.startswith(("tests/", "docs/", "frontend/")) for name in names):
            fail("backend wheel contains non-runtime project trees")
        for name in names:
            if name.endswith("/"):
                continue
            payload = archive.read(name)
            scan_bytes(f"wheel:{name}", payload)
            members.append(
                {
                    "name": name,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                }
            )
    return len(members), members


def check_repository(root: Path) -> None:
    reports = tuple(
        root / f"docs/revision6/r{phase}" for phase in range(7)
    )
    if any(not report_dir.is_dir() for report_dir in reports):
        fail("R0-R6 evidence chain is incomplete")
    master_plan = (root / "docs/SOCIAL_MEDIA_V2_MASTER_PLAN.md").read_text(encoding="utf-8")
    r7_completion = re.search(
        r"R7[^\n]{0,160}(?:tamamlandı|sertifikalı)",
        master_plan,
        flags=re.IGNORECASE,
    )
    if not r7_completion or "`STANDALONE_PRODUCT_COMPLETE=true`" not in master_plan:
        fail("master plan does not identify the completed R7 product state")

    production_env = (root / "deploy/env/social-media-v2.production.env.example").read_text(
        encoding="utf-8"
    )
    for exact in (
        "SOCIAL_RUNTIME_MODE=standalone_ready",
        "SOCIAL_WRITES_ENABLED=false",
        "SOCIAL_META_ACCOUNT_ENABLED=false",
        "SOCIAL_META_COLLECTION_ENABLED=false",
        "SOCIAL_TIKTOK_ACCOUNT_ENABLED=false",
        "SOCIAL_TIKTOK_COLLECTION_ENABLED=false",
        "SOCIAL_WORKER_SCHEDULE_ENABLED=false",
    ):
        if exact not in production_env.splitlines():
            fail(f"safe-start env invariant is missing: {exact}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend-dist", type=Path, required=True)
    parser.add_argument("--backend-wheel", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    frontend_dist = args.frontend_dist.resolve()
    backend_wheel = args.backend_wheel.resolve()
    check_repository(root)
    frontend_count, frontend_files = scan_frontend(frontend_dist)
    wheel_count, wheel_files = scan_wheel(backend_wheel)

    manifest = {
        "schema_version": 1,
        "phase": "R7",
        "source_scope": str(root),
        "frontend": {
            "file_count": frontend_count,
            "files": frontend_files,
        },
        "backend_wheel": {
            **digest(backend_wheel),
            "member_count": wheel_count,
            "members": wheel_files,
        },
        "forbidden_source_path_findings": 0,
        "forbidden_runtime_findings": 0,
        "secret_findings": 0,
    }
    if args.manifest:
        manifest_path = args.manifest.resolve()
        if root not in manifest_path.parents:
            fail("manifest must be written inside the V2 repository")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        "R7 RELEASE CHECK PASS: "
        f"{frontend_count} frontend artifacts and {wheel_count} wheel members scanned."
    )


if __name__ == "__main__":
    main()
