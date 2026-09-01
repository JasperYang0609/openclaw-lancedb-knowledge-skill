from __future__ import annotations

import sys
import tempfile
from collections.abc import Callable
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_gemini_product_boundary import assert_exact_files  # noqa: E402


def assert_rejected(expected_parts: tuple[str, ...], action: Callable[[], None]) -> None:
    try:
        action()
    except SystemExit as exc:
        message = str(exc)
        for expected in expected_parts:
            assert expected in message, message
    else:
        raise AssertionError("Expected the executable-surface check to reject the fixture")


def test_executable_surface_allowlist_rejects_an_added_runtime() -> None:
    with tempfile.TemporaryDirectory(prefix="gemini-boundary-added-") as temp_dir:
        scripts = Path(temp_dir) / "scripts"
        scripts.mkdir()
        (scripts / "known.py").write_text("# known\n", encoding="utf-8")
        assert_exact_files(scripts, {"known.py"}, "fixture")

        (scripts / "local_model_runtime.py").write_text(
            "# must be rejected\n", encoding="utf-8"
        )
        assert_rejected(
            ("added=", "local_model_runtime.py"),
            lambda: assert_exact_files(scripts, {"known.py"}, "fixture"),
        )


def test_executable_surface_allowlist_rejects_a_missing_managed_script() -> None:
    with tempfile.TemporaryDirectory(prefix="gemini-boundary-missing-") as temp_dir:
        scripts = Path(temp_dir) / "scripts"
        scripts.mkdir()
        assert_rejected(
            ("missing=", "required.py"),
            lambda: assert_exact_files(scripts, {"required.py"}, "fixture"),
        )


if __name__ == "__main__":
    test_executable_surface_allowlist_rejects_an_added_runtime()
    test_executable_surface_allowlist_rejects_a_missing_managed_script()
    print("PASS test_gemini_product_boundary")
