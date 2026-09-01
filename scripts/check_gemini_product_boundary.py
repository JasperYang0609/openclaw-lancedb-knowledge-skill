#!/usr/bin/env python3
"""Fail closed when local-model product code leaks into the Gemini edition."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "openclaw-lancedb-knowledge"
TEMPLATE = SKILL / "assets" / "knowledge-lancedb-template"
ARCHIVE = ROOT / "dist" / "openclaw-lancedb-knowledge.skill"

FORBIDDEN = (
    "qwen-local",
    "embed-qwen",
    "local-hash-v1",
    "embed-local",
    "shadow:index",
    "llama-server",
)


def production_files() -> list[Path]:
    roots = [
        ROOT / "README.md",
        SKILL / "SKILL.md",
        SKILL / "references" / "architecture.md",
        SKILL / "scripts" / "bootstrap_openclaw_lancedb.py",
        TEMPLATE / "config" / "source-map.example.json",
        TEMPLATE / "package.json",
    ]
    roots.extend(sorted((TEMPLATE / "src").glob("*")))
    return [path for path in roots if path.is_file()]


def assert_clean_blob(label: str, data: bytes) -> None:
    text = data.decode("utf-8", errors="ignore").lower()
    found = [token for token in FORBIDDEN if token in text]
    if found:
        raise SystemExit(f"Gemini product boundary violation in {label}: {', '.join(found)}")


def main() -> None:
    for path in production_files():
        assert_clean_blob(str(path.relative_to(ROOT)), path.read_bytes())

    source_map = json.loads((TEMPLATE / "config" / "source-map.example.json").read_text())
    embedding = source_map.get("embedding", {})
    if embedding.get("provider") != "google-gemini":
        raise SystemExit("source-map.example.json must default to google-gemini")
    if embedding.get("model") != "gemini-embedding-001":
        raise SystemExit("source-map.example.json must pin gemini-embedding-001")
    if embedding.get("dimensions") != 768:
        raise SystemExit("source-map.example.json balanced profile must use 768 dimensions")

    readme = (ROOT / "README.md").read_text()
    if "Gemini Edition" not in readme.splitlines()[0]:
        raise SystemExit("README first line must identify the Gemini edition")
    if "openclaw-lancedb-knowledge-embedding-local" not in readme:
        raise SystemExit("README must link to the local edition")

    if not ARCHIVE.exists():
        raise SystemExit("packaged skill archive is missing")
    with zipfile.ZipFile(ARCHIVE, "r") as archive:
        for info in archive.infolist():
            lowered_name = info.filename.lower()
            if any(token in lowered_name for token in FORBIDDEN):
                raise SystemExit(f"Gemini archive contains forbidden member: {info.filename}")
            assert_clean_blob(f"archive:{info.filename}", archive.read(info))

    print(f"PASS Gemini-only product boundary across {len(production_files())} source files and packaged archive")


if __name__ == "__main__":
    main()
