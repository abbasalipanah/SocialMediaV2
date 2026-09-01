from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def test_dependency_manifests_and_real_locks_exist() -> None:
    requirements = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
    runtime_lock = (BACKEND / "requirements.lock").read_text(encoding="utf-8")
    development_lock = (BACKEND / "requirements-dev.lock").read_text(encoding="utf-8")
    for package in ("fastapi", "uvicorn", "httpx", "sqlalchemy", "alembic", "psycopg"):
        assert package in requirements
        assert f"{package}==" in runtime_lock or f"{package}[binary]==" in runtime_lock
        assert package in development_lock
    assert "pytest==" in development_lock

    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((FRONTEND / "package-lock.json").read_text(encoding="utf-8"))
    assert package["dependencies"]["react"].startswith("^19")
    assert len(package_lock["packages"]) > 1


def test_safe_environment_contract_is_complete() -> None:
    env = (BACKEND / ".env.example").read_text(encoding="utf-8")
    required_lines = {
        "SOCIAL_WRITES_ENABLED=false",
        "SOCIAL_TIKTOK_PROVIDER_PROFILE=tiktok_business_accounts_v1_3",
        "SOCIAL_TIKTOK_BUSINESS_APP_ID=7657818426198474768",
        "SOCIAL_TIKTOK_ACCOUNT_ENABLED=false",
        "SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE=disabled",
        "SOCIAL_TIKTOK_COLLECTION_ENABLED=false",
        "SOCIAL_TIKTOK_ADVERTISER_ENABLED=false",
        "SOCIAL_TIKTOK_BUSINESS_APP_SECRET=",
        "SOCIAL_TIKTOK_OAUTH_STATE_SECRET=",
        "SOCIAL_TIKTOK_ACTIVATION_GATE_ENABLED=false",
        "SOCIAL_TIKTOK_ACTIVATION_ENABLED_AT=",
        "SOCIAL_TIKTOK_ACTIVATION_EXPIRES_AT=",
        "SOCIAL_CREDENTIAL_ACTIVE_KEY_ID=",
        "SOCIAL_CREDENTIAL_KEYRING_JSON=",
        "SOCIAL_META_APP_ID=1133669534788144",
        "SOCIAL_META_APP_SECRET=",
        "SOCIAL_META_ACCOUNT_ENABLED=false",
        "SOCIAL_META_ACCOUNT_OAUTH_MODE=disabled",
        "SOCIAL_META_REDIRECT_URI=https://social.theaccumulate.com/api/social/meta/oauth/callback",
        "SOCIAL_META_OAUTH_STATE_SECRET=",
        "SOCIAL_META_ACTIVATION_GATE_ENABLED=false",
        "SOCIAL_YOUTUBE_PROVIDER_PROFILE=youtube_data_analytics_v3_v2",
        "SOCIAL_YOUTUBE_OAUTH_APP_ID=",
        "SOCIAL_YOUTUBE_OAUTH_APP_SECRET=",
        "SOCIAL_YOUTUBE_ACCOUNT_ENABLED=false",
        "SOCIAL_YOUTUBE_ACCOUNT_OAUTH_MODE=disabled",
        "SOCIAL_YOUTUBE_COLLECTION_ENABLED=false",
        "SOCIAL_YOUTUBE_ACTIVATION_GATE_ENABLED=false",
        "SOCIAL_X_PROVIDER_PROFILE=x_api_v2_oauth2_pkce_v1",
        "SOCIAL_X_OAUTH_APP_ID=",
        "SOCIAL_X_OAUTH_APP_SECRET=",
        "SOCIAL_X_ACCOUNT_ENABLED=false",
        "SOCIAL_X_ACCOUNT_OAUTH_MODE=disabled",
        "SOCIAL_X_COLLECTION_ENABLED=false",
        "SOCIAL_X_ACTIVATION_GATE_ENABLED=false",
        "SOCIAL_AI_SUMMARY_ENABLED=false",
        "SOCIAL_AI_OPENROUTER_API_KEY=",
        "SOCIAL_AI_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1",
    }
    assert required_lines.issubset(set(env.splitlines()))


def test_canonical_scaffold_and_frontend_entrypoints_exist() -> None:
    required = (
        BACKEND / "app" / "main.py",
        BACKEND / "app" / "core" / "config.py",
        BACKEND / "app" / "core" / "write_policy.py",
        BACKEND / "app" / "domain" / "platforms" / "__init__.py",
        FRONTEND / "index.html",
        FRONTEND / "vite.config.ts",
        FRONTEND / "tsconfig.json",
        FRONTEND / "src" / "main.tsx",
    )
    for path in required:
        assert path.exists(), f"Missing required bootstrap path: {path}"


def test_generic_migration_guide_is_not_a_repository_artifact() -> None:
    assert not (ROOT / "docs" / "accumulate-alt-uygulama-teknik-entegrasyon-rehberi.md").exists()
