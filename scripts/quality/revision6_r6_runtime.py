#!/usr/bin/env python3
"""Static R6 gate for the standalone runtime and SSO-only boundary."""

from __future__ import annotations

import ast
import json
from pathlib import Path

EXPECTED_RUNTIME_MODES = (
    "development",
    "dormant",
    "staging",
    "standalone_ready",
    "active",
)
SOURCE_ROOT_MARKERS = (
    "/home/api/colab_scripts/SocialMedia",
    "/home/api/colab_scripts/Accumulate",
    "/home/api/colab_scripts/performance_marketing",
)


def fail(message: str) -> None:
    raise SystemExit(f"R6 RUNTIME CHECK FAILED: {message}")


def iter_files(root: Path, suffixes: tuple[str, ...]) -> tuple[Path, ...]:
    return tuple(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in suffixes
        and not any(
            part in {"__pycache__", "node_modules", "dist", "build"}
            for part in path.parts
        )
    )


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition("=")
        if not separator or not key:
            fail(f"invalid env example line: {line!r}")
        values[key] = value
    return values


def check_runtime_source(root: Path) -> int:
    surfaces = (
        root / "backend/app",
        root / "frontend/src",
        root / "deploy",
    )
    files = tuple(
        path
        for surface in surfaces
        for path in iter_files(
            surface, (".py", ".ts", ".tsx", ".service", ".timer", ".conf", ".example")
        )
    )
    for path in files:
        text = path.read_text(encoding="utf-8")
        if "cutover_" in text or "before_cutover" in text:
            fail(f"historical runtime mode leaked into {path.relative_to(root)}")
        for marker in SOURCE_ROOT_MARKERS:
            if marker in text:
                fail(f"source-project path dependency in {path.relative_to(root)}")
    backend_app = root / "backend/app"
    for path in iter_files(backend_app, (".py",)):
        text = path.read_text(encoding="utf-8")
        if any(
            forbidden in text
            for forbidden in (
                "/internal/provisioning/events",
                "ProvisioningStore",
                "X-ARS-",
                "outbox consumer",
            )
        ):
            fail(f"forbidden authority integration in {path.relative_to(root)}")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "sys" and node.attr == "path":
                    fail(
                        f"runtime sys.path mutation surface in {path.relative_to(root)}"
                    )
    return len(files)


def check_contract(root: Path) -> None:
    schema_path = root / "docs/contracts/social-media-v2-openapi.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if "/internal/provisioning/events" in schema.get("paths", {}):
        fail("provisioning endpoint exists in OpenAPI")
    runtime_modes = tuple(schema["components"]["schemas"]["RuntimeMode"]["enum"])
    if runtime_modes != EXPECTED_RUNTIME_MODES:
        fail(f"OpenAPI runtime modes differ: {runtime_modes!r}")

    frontend_contract = (root / "frontend/src/api/contracts.ts").read_text(
        encoding="utf-8"
    )
    generated_contract = (root / "frontend/src/api/openapi.generated.ts").read_text(
        encoding="utf-8"
    )
    for mode in EXPECTED_RUNTIME_MODES:
        if (
            f'"{mode}"' not in frontend_contract
            or f'"{mode}"' not in generated_contract
        ):
            fail(f"frontend runtime contract is missing {mode}")


def check_safe_artifacts(root: Path) -> None:
    env = parse_env(root / "deploy/env/social-media-v2.production.env.example")
    expected = {
        "APP_ENV": "production",
        "SOCIAL_RUNTIME_MODE": "standalone_ready",
        "SOCIAL_WRITES_ENABLED": "false",
        "SOCIAL_VAULT_ENABLED": "false",
        "SOCIAL_META_ACCOUNT_ENABLED": "false",
        "SOCIAL_META_ACCOUNT_OAUTH_MODE": "disabled",
        "SOCIAL_META_COLLECTION_ENABLED": "false",
        "SOCIAL_META_ACTIVATION_GATE_ENABLED": "false",
        "SOCIAL_TIKTOK_ACCOUNT_ENABLED": "false",
        "SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE": "disabled",
        "SOCIAL_TIKTOK_COLLECTION_ENABLED": "false",
        "SOCIAL_TIKTOK_ADVERTISER_ENABLED": "false",
        "SOCIAL_TIKTOK_ACTIVATION_GATE_ENABLED": "false",
        "SOCIAL_WORKER_SCHEDULE_ENABLED": "false",
    }
    for key, value in expected.items():
        if env.get(key) != value:
            fail(f"unsafe production env example: expected {key}={value}")

    api_unit = (root / "deploy/systemd/social-media-v2-api.service").read_text(
        encoding="utf-8"
    )
    migrate_unit = (root / "deploy/systemd/social-media-v2-migrate.service").read_text(
        encoding="utf-8"
    )
    collector_unit = (
        root / "deploy/systemd/social-media-v2-collection.service"
    ).read_text(encoding="utf-8")
    timer_unit = (root / "deploy/systemd/social-media-v2-collection.timer").read_text(
        encoding="utf-8"
    )
    if "apply_migrations.py" in api_unit or "ExecStartPre=" in api_unit:
        fail("API unit must not apply migrations automatically")
    if "apply_migrations.py" not in migrate_unit or "[Install]" in migrate_unit:
        fail("migration unit must be an explicit non-installable one-shot")
    if (
        "--scheduled" not in collector_unit
        or "social-media-v2-collection.service" not in timer_unit
    ):
        fail("collector/timer artifacts are incomplete")

    upgrade_script = (root / "scripts/deploy/upgrade_local_staging.sh").read_text(
        encoding="utf-8"
    )
    for required in (
        "social_media_v2_staging",
        "systemctl is-enabled --quiet social-media-v2-collection.timer",
        "restore_symlinks",
        'mv -Tf "$INSTALL_ROOT/.backend.next" "$INSTALL_ROOT/backend"',
        "systemctl start social-media-v2-migrate.service",
        "http://127.0.0.1:8026/api/operations/readiness",
        "http://127.0.0.1:3026/",
    ):
        if required not in upgrade_script:
            fail(f"V2 staging upgrade safety contract is missing: {required}")

    snapshot_script = (
        root / "scripts/deploy/copy_local_snapshot_to_staging.py"
    ).read_text(encoding="utf-8")
    for required in (
        'source.database != "social_media_v2_local"',
        'target.database != "social_media_v2_staging"',
        'source.execute(text("SET TRANSACTION READ ONLY"))',
        "source_must_contain_exact_allowlisted_brand",
        "source_contains_non_snapshot_projection_state",
        "target_tables_must_be_empty",
    ):
        if required not in snapshot_script:
            fail(f"V2 staging snapshot safety contract is missing: {required}")

    full_import_script = (
        root / "backend/scripts/import_legacy_all_brands.py"
    ).read_text(encoding="utf-8")
    for required in (
        'source.database != "socialmedia_adv"',
        'startswith("social_media_v2_shadow_")',
        'isolation_level="REPEATABLE READ"',
        'source_connection.execute(text("SET TRANSACTION READ ONLY"))',
        "target_tables_must_be_empty",
        "_secure_media_tree",
        "shutil.chown",
        "path.chmod(0o750 if path.is_dir() else 0o640)",
        "credentials and ephemeral OAuth/job state are intentionally handled by separate",
    ):
        if required not in full_import_script:
            fail(f"full legacy import safety contract is missing: {required}")
    for forbidden in (
        "access_token_enc",
        "refresh_token_enc",
        "tiktok_oauth_states",
    ):
        if forbidden in full_import_script:
            fail(f"full legacy import must exclude credential/OAuth state: {forbidden}")

    parity_script = (root / "backend/scripts/verify_legacy_full_import.py").read_text(
        encoding="utf-8"
    )
    for required in (
        'source.database != "socialmedia_adv"',
        'startswith("social_media_v2_shadow_")',
        'isolation_level="REPEATABLE READ"',
        'source.execute(text("SET TRANSACTION READ ONLY"))',
        'target.execute(text("SET TRANSACTION READ ONLY"))',
        "legacy_full_import_parity=verified",
    ):
        if required not in parity_script:
            fail(f"full legacy parity safety contract is missing: {required}")

    credential_script = (
        root / "backend/scripts/migrate_legacy_credentials_to_v2.py"
    ).read_text(encoding="utf-8")
    for required in (
        'source.database != "socialmedia_adv"',
        'startswith("social_media_v2_shadow_")',
        'isolation_level="REPEATABLE READ"',
        'source.execute(text("SET TRANSACTION READ ONLY"))',
        "target_credential_projection_state_must_be_empty",
        "PROVIDER_DISABLED_SETTINGS",
        "hide_parameters=True",
        "legacy_credential_migration=verified",
    ):
        if required not in credential_script:
            fail(f"credential migration safety contract is missing: {required}")
    for forbidden in ("print(access", "print(refresh", "print(token", "echo=True"):
        if forbidden in credential_script:
            fail(f"credential migration contains a secret logging surface: {forbidden}")

    credential_verifier = (
        root / "backend/scripts/verify_legacy_credentials_v2.py"
    ).read_text(encoding="utf-8")
    for required in (
        'source.execute(text("SET TRANSACTION READ ONLY"))',
        'target.execute(text("SET TRANSACTION READ ONLY"))',
        "hide_parameters=True",
        "credential_plaintext_parity=",
        "legacy_credential_parity=verified",
    ):
        if required not in credential_verifier:
            fail(f"credential parity safety contract is missing: {required}")

    dashboard_verifier = (
        root / "backend/scripts/verify_shadow_dashboard_coverage.py"
    ).read_text(encoding="utf-8")
    for required in (
        'startswith("social_media_v2_shadow_")',
        '"-c default_transaction_read_only=on"',
        'connection.execute(text("SHOW transaction_read_only"))',
        "KNOWN_LEGACY_METRIC_IDS_BY_PLATFORM",
        "KNOWN_LEGACY_BREAKDOWN_KEYS",
        "shadow_dashboard_coverage=verified",
    ):
        if required not in dashboard_verifier:
            fail(f"shadow dashboard verifier contract is missing: {required}")

    browser_verifier = (
        root / "frontend/e2e/verify-shadow-runtime.mjs"
    ).read_text(encoding="utf-8")
    for required in (
        "_must_remain_disabled",
        "shadow_browser_roles=viewer_operator,agency_admin,super_admin",
        "shadow_browser_console_and_api_errors=0",
        "shadow_browser_e2e=verified",
    ):
        if required not in browser_verifier:
            fail(f"shadow browser verifier contract is missing: {required}")

    nginx = (root / "deploy/nginx/social-media-v2.conf").read_text(encoding="utf-8")
    if (
        "127.0.0.1:8026" not in nginx
        or "root /opt/social-media-v2/frontend/dist" not in nginx
    ):
        fail("Nginx artifact does not target the standalone V2 runtime")
    if "location = /sso/consume" not in nginx or "access_log off" not in nginx:
        fail("SSO consume query logging is not disabled")


def check_docs(root: Path) -> None:
    canonical = root / "docs/contracts/social-media-v2-sso-only.md"
    old_path = root / "docs/contracts/social-media-v2-sso-provisioning.md"
    if "NORMATİF" not in canonical.read_text(encoding="utf-8"):
        fail("canonical SSO-only contract is not normative")
    if "ARCHIVED / SUPERSEDED" not in old_path.read_text(encoding="utf-8"):
        fail("historical SSO provisioning path is not archived")
    fase2 = root / "docs/fase2/Faz2_SSO_Provisioning_Report.md"
    if "ARCHIVED / SUPERSEDED" not in fase2.read_text(encoding="utf-8"):
        fail("historical provisioning report is not archived")
    archive = root / "docs/fase9/ARCHIVED_SUPERSEDED.md"
    if (
        not archive.is_file()
        or "Accumulate_final_cutover.patch" not in archive.read_text(encoding="utf-8")
    ):
        fail("historical cutover artifacts are not explicitly archived")
    handoff = (root / "docs/ACCUMULATE_SSO_HANDOFF.md").read_text(encoding="utf-8")
    if (
        "DRAFT — GÖNDERİLMEDİ" not in handoff
        or "social-media-v2-sso-only.md" not in handoff
    ):
        fail("Accumulate handoff is not safely gated to the SSO-only contract")


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    file_count = check_runtime_source(root)
    check_contract(root)
    check_safe_artifacts(root)
    check_docs(root)
    print(
        "R6 RUNTIME CHECK PASS: "
        f"{file_count} runtime/deploy files scanned; "
        "5 runtime modes; SSO-only and safe-start artifacts verified."
    )


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, ValueError, SyntaxError) as exc:
        fail(str(exc))
