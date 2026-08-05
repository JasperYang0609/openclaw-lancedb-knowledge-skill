#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_skill_archive import OUTPUT, archive_manifest  # noqa: E402


def repack(source: Path, target: Path, mutate_first: bool = False) -> None:
    with zipfile.ZipFile(source, "r") as original, zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_STORED
    ) as rewritten:
        for index, info in enumerate(original.infolist()):
            data = original.read(info)
            if mutate_first and index == 0:
                data += b"\nchanged"
            replacement = zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0))
            replacement.compress_type = zipfile.ZIP_STORED
            replacement.external_attr = info.external_attr
            rewritten.writestr(replacement, data)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="skill-archive-test-") as tmp_dir:
        tmp = Path(tmp_dir)
        differently_compressed = tmp / "stored.skill"
        repack(OUTPUT, differently_compressed)
        assert archive_manifest(OUTPUT) == archive_manifest(differently_compressed)

        changed = tmp / "changed.skill"
        repack(OUTPUT, changed, mutate_first=True)
        assert archive_manifest(OUTPUT) != archive_manifest(changed)

        duplicate = tmp / "duplicate.skill"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(duplicate, "w") as archive:
                archive.writestr("duplicate.txt", b"first")
                archive.writestr("duplicate.txt", b"second")
        try:
            archive_manifest(duplicate)
        except ValueError as exc:
            assert "duplicate archive member" in str(exc)
        else:
            raise AssertionError("duplicate archive member must fail closed")

    print("PASS test_skill_archive")


if __name__ == "__main__":
    main()
