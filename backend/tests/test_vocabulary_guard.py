from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.domain.platforms import PlatformId

ROOT = Path(__file__).resolve().parents[2]


def test_platform_id_is_the_exact_canonical_set() -> None:
    assert PlatformId.exact_set() == {
        "facebook",
        "instagram",
        "tiktok",
        "x",
        "linkedin",
        "youtube",
    }


def test_canonical_vocabulary_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "quality" / "check_canonical_vocabulary.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
