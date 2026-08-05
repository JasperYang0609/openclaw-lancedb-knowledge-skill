#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "openclaw-lancedb-knowledge"
OUTPUT = ROOT / "dist" / "openclaw-lancedb-knowledge.skill"
EXCLUDED_PARTS = {"node_modules", "__pycache__", "data", "reports"}
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def source_files() -> list[Path]:
    return sorted(
        path
        for path in SOURCE.rglob("*")
        if path.is_file()
        and not any(part in EXCLUDED_PARTS for part in path.relative_to(SOURCE).parts)
        and path.suffix != ".pyc"
    )


def build(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in source_files():
            archive_name = Path(SOURCE.name) / path.relative_to(SOURCE)
            info = zipfile.ZipInfo(str(archive_name), date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or verify the deterministic .skill archive")
    parser.add_argument("--check", action="store_true", help="Fail when dist artifact differs from source")
    args = parser.parse_args()

    if args.check:
        with tempfile.TemporaryDirectory(prefix="skill-archive-check-") as tmp_dir:
            candidate = Path(tmp_dir) / OUTPUT.name
            build(candidate)
            if not OUTPUT.exists() or candidate.read_bytes() != OUTPUT.read_bytes():
                raise SystemExit("dist/openclaw-lancedb-knowledge.skill is stale; rebuild it")
        print(f"PASS skill archive matches {len(source_files())} source files")
        return

    with tempfile.NamedTemporaryFile(dir=OUTPUT.parent, prefix=".skill-", delete=False) as handle:
        candidate = Path(handle.name)
    try:
        build(candidate)
        os.replace(candidate, OUTPUT)
    finally:
        candidate.unlink(missing_ok=True)
    print(f"built {OUTPUT} with {len(source_files())} files")


if __name__ == "__main__":
    main()
