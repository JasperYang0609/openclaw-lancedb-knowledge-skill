#!/usr/bin/env python3
"""Bootstrap a portable OpenClaw LanceDB knowledge index project from this skill."""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def copytree(src: Path, dst: Path, overwrite: bool) -> None:
    if dst.exists() and any(dst.iterdir()) and not overwrite:
        raise SystemExit(f"Target exists and is not empty: {dst}\nUse --overwrite to replace template files.")
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in {"node_modules", "data", "reports"}:
            continue
        target = dst / item.name
        if item.is_dir():
            if target.exists() and overwrite:
                shutil.rmtree(target)
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an OpenClaw-friendly LanceDB knowledge index project.")
    parser.add_argument("--target", default="~/.openclaw/workspace/knowledge-lancedb", help="Install target directory")
    parser.add_argument("--workspace", default="~/.openclaw/workspace", help="OpenClaw workspace path")
    parser.add_argument("--backup-root", default="", help="Discord/channel backup root containing summary/ markdown")
    parser.add_argument("--project-root", default="", help="Client/project docs root to index")
    parser.add_argument("--project-name", default="ClientProject", help="Project label stored in LanceDB rows")
    parser.add_argument("--google-gemini", action="store_true", help="Use Google Gemini embeddings instead of local hash embeddings")
    parser.add_argument("--approved-by", default="", help="Required note when enabling external embeddings")
    parser.add_argument("--npm-install", action="store_true", help="Run npm install after copying files")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing template files in target")
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parents[1]
    template = skill_dir / "assets" / "knowledge-lancedb-template"
    if not template.exists():
        raise SystemExit(f"Template not found: {template}")

    target = Path(args.target).expanduser().resolve()
    workspace = Path(args.workspace).expanduser().resolve()
    backup_root = Path(args.backup_root).expanduser().resolve() if args.backup_root else Path("__DISCORD_BACKUP_ROOT__")
    project_root = Path(args.project_root).expanduser().resolve() if args.project_root else Path("__PROJECT_DOC_ROOT__")

    if args.google_gemini and not args.approved_by:
        raise SystemExit("--approved-by is required with --google-gemini because private chunks leave the machine for embedding.")

    copytree(template, target, args.overwrite)
    (target / "data").mkdir(exist_ok=True)
    (target / "reports" / "cron-logs").mkdir(parents=True, exist_ok=True)

    example_cfg = target / "config" / "source-map.example.json"
    cfg = json.loads(example_cfg.read_text())
    for src in cfg["sources"]:
        if src["root"] == "__OPENCLAW_WORKSPACE__/memory":
            src["root"] = str(workspace / "memory")
        elif src["root"] == "__DISCORD_BACKUP_ROOT__":
            src["root"] = str(backup_root)
        elif src["root"] == "__PROJECT_DOC_ROOT__":
            src["root"] = str(project_root)
            src["project"] = args.project_name

    if args.google_gemini:
        cfg["embedding"] = {
            "provider": "google-gemini",
            "model": "gemini-embedding-001",
            "dimensions": 768,
            "documentTaskType": "RETRIEVAL_DOCUMENT",
            "queryTaskType": "RETRIEVAL_QUERY",
            "batchSize": 40,
            "throttleMs": 250,
            "cachePath": "./data/embedding-cache/google-gemini-embedding-001-768.jsonl",
            "privacyApprovedAt": datetime.now(timezone.utc).isoformat(),
            "privacyApprovedBy": args.approved_by,
        }

    (target / "config" / "source-map.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")

    if args.npm_install:
        subprocess.run(["npm", "install"], cwd=target, check=True)

    print(json.dumps({
        "ok": True,
        "target": str(target),
        "config": str(target / "config" / "source-map.json"),
        "next": [
            "cd " + str(target),
            "npm install" if not args.npm_install else "npm test",
            "npm run scan",
            "npm run index",
            "npm run search -- \"project status\" -- --limit 5",
        ]
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
