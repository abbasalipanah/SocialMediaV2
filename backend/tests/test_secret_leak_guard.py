from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_repository_secret_leak_guard_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "quality" / "check_secret_leaks.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
