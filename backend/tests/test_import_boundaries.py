from __future__ import annotations

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"
FORBIDDEN_TOP_LEVEL_IMPORTS = {"SocialMedia", "Accumulate", "performance_marketing"}
DOMAIN_FORBIDDEN_IMPORTS = {"fastapi", "sqlalchemy", "httpx"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(item.name.split(".")[0] for item in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module.split(".")[0])
    return result


def test_only_canonical_backend_tree_exists() -> None:
    assert APP.is_dir()
    assert not (BACKEND / "src" / "social_media_v2").exists()


def test_runtime_has_no_source_project_import_or_path_dependency() -> None:
    violations: list[str] = []
    for path in APP.rglob("*.py"):
        if _imports(path) & FORBIDDEN_TOP_LEVEL_IMPORTS:
            violations.append(str(path))
        text = path.read_text(encoding="utf-8")
        for token in (
            "/colab_scripts/SocialMedia",
            "/colab_scripts/Accumulate",
            "/performance_marketing",
        ):
            if token in text:
                violations.append(f"{path}: {token}")
    assert not violations


def test_domain_layer_has_no_framework_or_infrastructure_imports() -> None:
    violations: list[str] = []
    for path in (APP / "domain").rglob("*.py"):
        imports = _imports(path)
        if imports & DOMAIN_FORBIDDEN_IMPORTS:
            violations.append(str(path))
        if "app.infrastructure" in path.read_text(encoding="utf-8"):
            violations.append(str(path))
    assert not violations
