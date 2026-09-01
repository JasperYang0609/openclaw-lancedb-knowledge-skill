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

EXPECTED_TEMPLATE_SRC = {
    "benchmark.js",
    "chunk.js",
    "cli.js",
    "embed-google.js",
    "enrichment.js",
    "glob-lite.js",
    "metadata.js",
    "quality-profile.js",
    "security.js",
    "sources.js",
}

EXPECTED_TEMPLATE_SCRIPTS = {
    "audit_cron_tooling.py",
    "knowledge_index_incremental.sh",
    "knowledge_search.sh",
    "post_run_check.mjs",
    "snapshot_knowledge_assets.py",
}

EXPECTED_SKILL_SCRIPTS = {
    "bootstrap_openclaw_lancedb.py",
}

EXPECTED_PRODUCT_COMMANDS = {
    "scan",
    "index",
    "search",
    "status",
    "test",
    "incremental",
    "sync-state",
    "compact-cache",
    "enrich:prepare",
    "enrich:validate",
    "benchmark",
    "profile",
    "audit",
    "snapshot:backup",
    "postrun:check",
}


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


def assert_exact_files(directory: Path, expected: set[str], label: str) -> None:
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != expected:
        added = sorted(actual - expected)
        missing = sorted(expected - actual)
        raise SystemExit(f"unexpected {label} surface; added={added}, missing={missing}")


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

    assert_exact_files(TEMPLATE / "src", EXPECTED_TEMPLATE_SRC, "Gemini runtime")
    assert_exact_files(TEMPLATE / "scripts", EXPECTED_TEMPLATE_SCRIPTS, "Gemini template script")
    assert_exact_files(SKILL / "scripts", EXPECTED_SKILL_SCRIPTS, "Gemini bootstrap script")

    package = json.loads((TEMPLATE / "package.json").read_text())
    actual_commands = set(package.get("scripts", {}))
    if actual_commands != EXPECTED_PRODUCT_COMMANDS:
        added = sorted(actual_commands - EXPECTED_PRODUCT_COMMANDS)
        missing = sorted(EXPECTED_PRODUCT_COMMANDS - actual_commands)
        raise SystemExit(f"unexpected Gemini command surface; added={added}, missing={missing}")

    readme = (ROOT / "README.md").read_text()
    if "Gemini Edition" not in readme.splitlines()[0]:
        raise SystemExit("README first line must identify the Gemini edition")
    if "openclaw-lancedb-knowledge-embedding-local" not in readme:
        raise SystemExit("README must link to the local edition")

    if not ARCHIVE.exists():
        raise SystemExit("packaged skill archive is missing")
    with zipfile.ZipFile(ARCHIVE, "r") as archive:
        archive_src = set()
        archive_template_scripts = set()
        archive_skill_scripts = set()
        for info in archive.infolist():
            lowered_name = info.filename.lower()
            if any(token in lowered_name for token in FORBIDDEN):
                raise SystemExit(f"Gemini archive contains forbidden member: {info.filename}")
            assert_clean_blob(f"archive:{info.filename}", archive.read(info))
            marker = "/assets/knowledge-lancedb-template/src/"
            if marker in info.filename:
                archive_src.add(Path(info.filename).name)
            template_scripts_marker = "/assets/knowledge-lancedb-template/scripts/"
            if template_scripts_marker in info.filename:
                archive_template_scripts.add(Path(info.filename).name)
            skill_scripts_marker = "openclaw-lancedb-knowledge/scripts/"
            if info.filename.startswith(skill_scripts_marker):
                archive_skill_scripts.add(Path(info.filename).name)
        if archive_src != EXPECTED_TEMPLATE_SRC:
            raise SystemExit("packaged archive runtime surface does not match the Gemini allowlist")
        if archive_template_scripts != EXPECTED_TEMPLATE_SCRIPTS:
            raise SystemExit("packaged archive template scripts do not match the Gemini allowlist")
        if archive_skill_scripts != EXPECTED_SKILL_SCRIPTS:
            raise SystemExit("packaged archive bootstrap scripts do not match the Gemini allowlist")

    print(f"PASS Gemini-only product boundary across {len(production_files())} source files and packaged archive")


if __name__ == "__main__":
    main()
