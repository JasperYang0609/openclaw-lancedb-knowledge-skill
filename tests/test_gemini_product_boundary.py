from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_gemini_product_boundary import assert_exact_files  # noqa: E402


def test_executable_surface_allowlist_rejects_an_added_runtime(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "known.py").write_text("# known\n", encoding="utf-8")
    assert_exact_files(scripts, {"known.py"}, "fixture")

    (scripts / "local_model_runtime.py").write_text("# must be rejected\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="added=.*local_model_runtime.py"):
        assert_exact_files(scripts, {"known.py"}, "fixture")


def test_executable_surface_allowlist_rejects_a_missing_managed_script(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    with pytest.raises(SystemExit, match="missing=.*required.py"):
        assert_exact_files(scripts, {"required.py"}, "fixture")
