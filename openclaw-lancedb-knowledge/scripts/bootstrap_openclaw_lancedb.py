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


PRODUCT_ID = "openclaw-lancedb-knowledge-gemini"
INSTALL_MARKER = ".openclaw-lancedb-install.json"


def _is_regular_file(path: Path) -> bool:
    return path.exists() and path.is_file() and not path.is_symlink()


def _is_managed_target(target: Path) -> bool:
    marker = target / INSTALL_MARKER
    if _is_regular_file(marker):
        try:
            payload = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return payload.get("product") == PRODUCT_ID and payload.get("schemaVersion") == 1

    # Forward-compatible upgrade path for installations created before the marker existed.
    package = target / "package.json"
    cli = target / "src" / "cli.js"
    source_map = target / "config" / "source-map.json"
    if not all(_is_regular_file(path) for path in (package, cli, source_map)):
        return False
    try:
        return json.loads(package.read_text(encoding="utf-8")).get("name") == "knowledge-lancedb"
    except (OSError, json.JSONDecodeError):
        return False


def validate_target(target: Path, *, workspace: Path, skill_dir: Path, overwrite: bool) -> None:
    if target == Path(target.anchor) or len(target.parts) < 4:
        raise SystemExit("Target must be a specific managed directory, not a filesystem root.")

    home = Path.home().resolve()
    protected = {
        Path("/"),
        home,
        (home / ".openclaw").resolve(strict=False),
        workspace.resolve(strict=False),
        skill_dir.resolve(strict=False),
        skill_dir.parent.resolve(strict=False),
    }
    resolved = target.resolve(strict=False)
    if resolved in protected:
        raise SystemExit("Target overlaps a protected home, workspace, repository, or OpenClaw root.")
    repository_root = skill_dir.parent.resolve(strict=False)
    if repository_root in resolved.parents or resolved in repository_root.parents:
        raise SystemExit("Target must not be inside, or contain, the source repository.")

    for component in (target, *target.parents):
        if component.is_symlink():
            raise SystemExit("Target path must not contain symbolic links.")

    nearest_existing = next((component for component in (target, *target.parents) if component.exists()), None)
    if nearest_existing is None or not nearest_existing.is_dir():
        raise SystemExit("Target parent must be an existing directory.")
    if hasattr(os, "getuid") and nearest_existing.stat().st_uid != os.getuid():
        raise SystemExit("Target parent must be owned by the current user.")

    if target.exists() and not target.is_dir():
        raise SystemExit("Target must be a directory.")
    if target.exists() and any(target.iterdir()) and overwrite and not _is_managed_target(target):
        raise SystemExit("Refusing --overwrite: target is not a recognized managed knowledge-lancedb installation.")


def write_install_marker(target: Path) -> None:
    marker = target / INSTALL_MARKER
    if marker.is_symlink() or (marker.exists() and not marker.is_file()):
        raise SystemExit("Install marker path must be a regular file.")
    temporary = target / f"{INSTALL_MARKER}.tmp"
    if temporary.exists() or temporary.is_symlink():
        raise SystemExit("Install marker staging path already exists.")
    temporary.write_text(json.dumps({
        "schemaVersion": 1,
        "product": PRODUCT_ID,
        "repository": "JasperYang0609/openclaw-lancedb-knowledge-skill",
    }, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, marker)


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
                if target.is_symlink() or not target.is_dir():
                    raise SystemExit(f"Refusing to replace unsafe managed directory: {target}")
                shutil.rmtree(target)
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


SAFE_INSTALL_ENV_KEYS = (
    "HOME",
    "PATH",
    "TMPDIR",
    "TMP",
    "TEMP",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)


def install_dependencies(target: Path, allow_package_scripts: bool = False) -> list[str]:
    """Run a fixed npm install contract without a shell or dynamic arguments."""
    npm_bin = shutil.which("npm")
    if not npm_bin:
        raise SystemExit("npm executable not found on PATH; dependencies were not installed.")
    command = [str(Path(npm_bin).resolve()), "ci"]
    env = {key: os.environ[key] for key in SAFE_INSTALL_ENV_KEYS if os.environ.get(key)}
    if not allow_package_scripts:
        command.append("--ignore-scripts")
        env["npm_config_ignore_scripts"] = "true"
    subprocess.run(command, cwd=target, check=True, shell=False, env=env)
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an OpenClaw-friendly LanceDB knowledge index project.")
    parser.add_argument("--target", default="~/.openclaw/workspace/knowledge-lancedb", help="Install target directory")
    parser.add_argument("--workspace", default="~/.openclaw/workspace", help="OpenClaw workspace path")
    parser.add_argument("--backup-root", default="", help="Discord/channel backup root containing summary/ and optional raw/ markdown")
    parser.add_argument("--include-discord-raw", action="store_true", help="Also index **/raw/**/*.md as sourceType=discord_raw; review privacy and corpus size first")
    parser.add_argument("--project-root", default="", help="Client/project docs root to index")
    parser.add_argument("--project-name", default="ClientProject", help="Project label stored in LanceDB rows")
    parser.add_argument("--embedding-profile", choices=["balanced", "high-quality"], default="balanced", help="Balanced uses 768 Gemini dimensions; high-quality uses 3072 and requires a full rebuild")
    parser.add_argument("--approved-by", default="", help="Required approval note for sending redacted chunks to Google Gemini")
    parser.add_argument("--npm-install", action="store_true", help="Run npm ci --ignore-scripts after copying files")
    parser.add_argument("--allow-package-scripts", action="store_true", help="Explicitly allow npm lifecycle scripts; requires --npm-install and dependency review")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing template files in target")
    args = parser.parse_args()
    if args.allow_package_scripts and not args.npm_install:
        raise SystemExit("--allow-package-scripts requires --npm-install.")

    skill_dir = Path(__file__).resolve().parents[1]
    template = skill_dir / "assets" / "knowledge-lancedb-template"
    if not template.exists():
        raise SystemExit(f"Template not found: {template}")

    target = Path(os.path.abspath(Path(args.target).expanduser()))
    workspace = Path(args.workspace).expanduser().resolve()
    backup_root = Path(args.backup_root).expanduser().resolve() if args.backup_root else Path("__DISCORD_BACKUP_ROOT__")
    project_root = Path(args.project_root).expanduser().resolve() if args.project_root else Path("__PROJECT_DOC_ROOT__")

    if not args.approved_by.strip():
        raise SystemExit("--approved-by is required because this Gemini edition sends redacted chunks to Google for embedding.")

    validate_target(target, workspace=workspace, skill_dir=skill_dir, overwrite=args.overwrite)
    copytree(template, target, args.overwrite)
    write_install_marker(target)
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

    if args.include_discord_raw:
        cfg["sources"].append({
            "id": "discord-backup-raw",
            "project": "DiscordBackups",
            "sourceType": "discord_raw",
            "root": str(backup_root),
            "include": ["**/raw/**/*.md"],
            "exclude": [
                "**/summary/**", "**/legacy/**", "**/legacy_docs/**",
                "**/.env*", "**/*secret*", "**/*token*",
            ],
            "priority": 1,
        })
        cfg["privacy"] = {
            "discordRawApproval": "APPROVED_EXTERNAL",
            "exactMessageIdValidation": "REQUIRED",
        }
    else:
        cfg["privacy"] = {
            "discordRawApproval": "NOT_CONFIRMED",
            "exactMessageIdValidation": "SKIPPED_PRIVACY_GATE",
        }

    dimensions = 3072 if args.embedding_profile == "high-quality" else 768
    cfg["embedding"] = {
        "provider": "google-gemini",
        "model": "gemini-embedding-001",
        "profile": args.embedding_profile,
        "dimensions": dimensions,
        "documentTaskType": "RETRIEVAL_DOCUMENT",
        "queryTaskType": "RETRIEVAL_QUERY",
        "batchSize": 40,
        "throttleMs": 250,
        "cachePath": f"./data/embedding-cache/google-gemini-embedding-001-{dimensions}.jsonl",
        "privacyApprovedAt": datetime.now(timezone.utc).isoformat(),
        "privacyApprovedBy": args.approved_by.strip(),
    }
    if args.embedding_profile == "high-quality":
        cfg["chunking"] = {"maxChars": 2800, "overlapChars": 350}

    (target / "config" / "source-map.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")

    install_command = None
    if args.npm_install:
        install_command = install_dependencies(target, args.allow_package_scripts)

    print(json.dumps({
        "ok": True,
        "target": str(target),
        "config": str(target / "config" / "source-map.json"),
        "install_command": install_command,
        "next": [
            "cd " + str(target),
            "npm ci --ignore-scripts" if not args.npm_install else "npm test",
            "npm run scan",
            "npm run index",
            "npm run search -- \"project status\" -- --limit 5",
        ]
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
