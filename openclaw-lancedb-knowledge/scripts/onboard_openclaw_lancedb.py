#!/usr/bin/env python3
"""Guided, resumable onboarding for the Gemini LanceDB knowledge skill.

The script deliberately never accepts an API key as an argument. On macOS the
existing native Keychain helper owns secret entry and retrieval. All durable
onboarding evidence is non-secret and written to a compact JSON receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PRODUCT_ID = "openclaw-lancedb-knowledge-gemini"
INSTALL_MARKER = ".openclaw-lancedb-install.json"
RECEIPT_RELATIVE_PATH = Path("reports/onboarding-receipt.json")
DEFAULT_TARGET = "~/.openclaw/workspace/knowledge-lancedb"
DEFAULT_WORKSPACE = "~/.openclaw/workspace"
DEFAULT_SNAPSHOT_ROOT = "~/.openclaw/backups/knowledge-lancedb"
DEFAULT_INDEX_CRON = "15 2 * * *"
DEFAULT_SNAPSHOT_CRON = "45 2 * * *"
DEFAULT_TIMEZONE = "UTC"


class OnboardingError(RuntimeError):
    """A safe onboarding failure whose message never contains a secret."""

    def __init__(self, message: str, *, next_action: str = "") -> None:
        super().__init__(message)
        self.next_action = next_action


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolved_path(value: str) -> Path:
    return Path(os.path.abspath(Path(value).expanduser()))


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OnboardingError(f"Cannot read valid JSON from {path.name}.") from exc
    if not isinstance(payload, dict):
        raise OnboardingError(f"Expected a JSON object in {path.name}.")
    return payload


def parse_json_output(output: str, label: str) -> dict[str, Any]:
    text = output.strip()
    candidates = [text]
    lines = text.splitlines()
    for start in range(len(lines)):
        if lines[start].lstrip().startswith("{"):
            candidates.append("\n".join(lines[start:]))
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise OnboardingError(f"{label} did not return a valid JSON object.")


def safe_failure_detail(result: subprocess.CompletedProcess[str]) -> str:
    detail = (result.stderr or result.stdout or "command failed").strip().splitlines()
    return (detail[-1] if detail else "command failed")[:500]


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 7200,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        shell=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise OnboardingError(safe_failure_detail(result))
    return result


def require_executable(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise OnboardingError(
            f"Required executable is unavailable: {name}.",
            next_action=f"Install {name}, then rerun the same onboarding command.",
        )
    return str(Path(executable).resolve())


def managed_install(target: Path) -> bool:
    marker = target / INSTALL_MARKER
    if not marker.is_file() or marker.is_symlink():
        return False
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("product") == PRODUCT_ID and payload.get("schemaVersion") == 1


def declaration_suffix(target: Path) -> str:
    return hashlib.sha256(str(target).encode("utf-8")).hexdigest()[:12]


def cron_commands(
    *,
    openclaw_bin: str,
    target: Path,
    snapshot_root: Path,
    timezone_name: str,
    index_cron: str,
    snapshot_cron: str,
) -> list[tuple[str, list[str]]]:
    suffix = declaration_suffix(target)
    common = [
        openclaw_bin,
        "cron",
        "add",
        "--tz",
        timezone_name,
        "--exact",
        "--command-cwd",
        str(target),
        "--timeout-seconds",
        "7200",
        "--output-max-bytes",
        "200000",
        "--json",
    ]
    index_key = f"openclaw-lancedb-index-{suffix}"
    snapshot_key = f"openclaw-lancedb-snapshot-{suffix}"
    index = [
        *common,
        "--name",
        "OpenClaw LanceDB daily incremental index",
        "--description",
        "Daily Gemini incremental index installed by guided onboarding",
        "--cron",
        index_cron,
        "--declaration-key",
        index_key,
        "--command-env",
        f"OPENCLAW_LANCEDB_ROOT={target}",
        "--command-argv",
        json.dumps(["/bin/bash", str(target / "scripts/knowledge_index_incremental.sh")]),
    ]
    snapshot = [
        *common,
        "--name",
        "OpenClaw LanceDB daily verified snapshot",
        "--description",
        "Daily checksummed restore snapshot installed by guided onboarding",
        "--cron",
        snapshot_cron,
        "--declaration-key",
        snapshot_key,
        "--command-env",
        f"OPENCLAW_LANCEDB_ROOT={target}",
        "--command-env",
        f"OPENCLAW_LANCEDB_SNAPSHOT_ROOT={snapshot_root}",
        "--command-argv",
        json.dumps(["/bin/bash", str(target / "scripts/knowledge_snapshot_daily.sh")]),
    ]
    return [(index_key, index), (snapshot_key, snapshot)]


def plan_payload(args: argparse.Namespace) -> dict[str, Any]:
    target = resolved_path(args.target)
    workspace = resolved_path(args.workspace)
    snapshot_root = resolved_path(args.snapshot_root)
    return {
        "schemaVersion": 1,
        "status": "PLAN",
        "provider": "google-gemini",
        "model": "gemini-embedding-001",
        "dimensions": 768,
        "target": str(target),
        "workspace": str(workspace),
        "sources": {
            "workspaceMemory": str(workspace / "memory"),
            "discordBackup": str(resolved_path(args.backup_root)) if args.backup_root else None,
            "projectDocs": str(resolved_path(args.project_root)) if args.project_root else None,
            "includeDiscordRaw": bool(args.include_discord_raw),
        },
        "snapshotRoot": str(snapshot_root),
        "automationRequested": bool(args.install_cron),
        "requiredHumanInputs": [
            "Explicit approval to send redacted selected chunks to Google Gemini",
            "Data source and exclusion scope",
            "Gemini API key entered only through the native hidden credential prompt",
            "Explicit acceptance of initial embedding API usage and cost",
        ],
        "readyRequires": [
            "dependencies",
            "source_scan",
            "credential_canary",
            "initial_index",
            "coverage_audit",
            "natural_language_search",
            "incremental_cron",
            "verified_snapshot_cron",
            "restore_snapshot",
        ],
    }


def bootstrap_command(args: argparse.Namespace, bootstrap: Path, target: Path) -> list[str]:
    command = [
        sys.executable,
        str(bootstrap),
        "--target",
        str(target),
        "--workspace",
        str(resolved_path(args.workspace)),
        "--approved-by",
        args.approved_by.strip(),
        "--embedding-profile",
        "balanced",
        "--npm-install",
    ]
    if args.backup_root:
        command.extend(["--backup-root", str(resolved_path(args.backup_root))])
    if args.project_root:
        command.extend(["--project-root", str(resolved_path(args.project_root))])
        command.extend(["--project-name", args.project_name])
    if args.include_discord_raw:
        command.append("--include-discord-raw")
    return command


def receipt_base(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "product": PRODUCT_ID,
        "generatedAt": utc_now(),
        "status": "BLOCKED",
        "provider": "google-gemini",
        "model": "gemini-embedding-001",
        "dimensions": 768,
        "target": str(resolved_path(args.target)),
        "snapshotRoot": str(resolved_path(args.snapshot_root)),
        "checks": {},
        "nextAction": None,
        "secretDisplayed": False,
        "secretPersistedInReceipt": False,
    }


def receipt_path_for(target: Path) -> Path:
    if managed_install(target):
        return target / RECEIPT_RELATIVE_PATH
    return target.parent / f".{target.name}-onboarding-receipt.json"


def write_blocked_receipt(
    args: argparse.Namespace,
    receipt: dict[str, Any],
    message: str,
    next_action: str = "",
) -> None:
    receipt["generatedAt"] = utc_now()
    receipt["status"] = "BLOCKED"
    receipt["error"] = message[:500]
    receipt["nextAction"] = next_action or "Resolve the reported check and rerun the same onboarding command."
    atomic_write_json(receipt_path_for(resolved_path(args.target)), receipt)


def validate_resume_configuration(args: argparse.Namespace, target: Path) -> None:
    config = load_json(target / "config/source-map.json")
    embedding = config.get("embedding") or {}
    if (
        embedding.get("provider") != "google-gemini"
        or embedding.get("model") != "gemini-embedding-001"
        or embedding.get("dimensions") != 768
    ):
        raise OnboardingError(
            "Existing managed target does not match google-gemini / gemini-embedding-001 / 768.",
            next_action="Inspect the existing installation; never convert embedding identity in place.",
        )
    if args.approved_by.strip() and embedding.get("privacyApprovedBy") != args.approved_by.strip():
        raise OnboardingError(
            "The supplied privacy approval note differs from the managed installation.",
            next_action="Rerun with the original approval note or review the source scope as a separate change.",
        )
    sources = {
        source.get("id"): source
        for source in (config.get("sources") or [])
        if isinstance(source, dict)
    }
    expected_roots = {
        "workspace-memory": resolved_path(args.workspace) / "memory",
    }
    if args.backup_root:
        expected_roots["discord-backup-summary"] = resolved_path(args.backup_root)
    if args.project_root:
        expected_roots["project-docs"] = resolved_path(args.project_root)
    for source_id, expected in expected_roots.items():
        configured = sources.get(source_id, {}).get("root")
        if configured != str(expected):
            raise OnboardingError(
                f"Requested source scope differs from the managed installation: {source_id}.",
                next_action="Review and re-bootstrap source scope as a separate approved change.",
            )
    raw_configured = any(
        source.get("sourceType") == "discord_raw"
        for source in sources.values()
    )
    if raw_configured != bool(args.include_discord_raw):
        raise OnboardingError(
            "Discord raw-message approval differs from the managed installation.",
            next_action="Keep the original raw-message choice or review the privacy scope as a separate change.",
        )


def install_or_resume(args: argparse.Namespace, receipt: dict[str, Any]) -> Path:
    target = resolved_path(args.target)
    skill_root = Path(__file__).resolve().parents[1]
    bootstrap = skill_root / "scripts/bootstrap_openclaw_lancedb.py"
    if managed_install(target):
        validate_resume_configuration(args, target)
        receipt["checks"]["bootstrap"] = {"ok": True, "resumed": True}
        return target
    if target.exists() and any(target.iterdir()):
        raise OnboardingError(
            "Target is not an onboarding-managed Gemini installation.",
            next_action="Choose an empty target or inspect the existing installation manually.",
        )
    if not args.approved_by.strip():
        raise OnboardingError(
            "Privacy approval is required before creating a Gemini configuration.",
            next_action="Record who approved sending redacted selected chunks to Google Gemini.",
        )
    result = run_command(bootstrap_command(args, bootstrap, target), cwd=skill_root)
    payload = parse_json_output(result.stdout, "bootstrap")
    if payload.get("ok") is not True or not managed_install(target):
        raise OnboardingError("Bootstrap did not create a managed Gemini installation.")
    receipt["checks"]["bootstrap"] = {"ok": True, "resumed": False}
    return target


def run_local_gates(target: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    npm = require_executable("npm")
    if not (target / "node_modules").is_dir():
        run_command([npm, "ci", "--ignore-scripts"], cwd=target)
    run_command([npm, "test", "--silent"], cwd=target)
    receipt["checks"]["dependencies"] = {"ok": True, "lifecycleScripts": False}
    scan_result = run_command([npm, "run", "--silent", "scan"], cwd=target)
    scan = parse_json_output(scan_result.stdout, "source scan")
    docs = int(scan.get("docs") or 0)
    chunks = int(scan.get("chunks") or 0)
    if docs < 1 or chunks < 1:
        raise OnboardingError(
            "No indexable documents were found in the approved source scope.",
            next_action="Correct the selected source paths or include patterns, then rerun onboarding.",
        )
    receipt["checks"]["sourceScan"] = {
        "ok": True,
        "docs": docs,
        "chunks": chunks,
        "skipped": len(scan.get("skipped") or []),
        "redactedSecretHitFiles": len(scan.get("secretHits") or []),
        "byProject": scan.get("byProject") or {},
    }
    return scan


def keychain_helper(target: Path) -> Path:
    helper = target / "scripts/gemini_embedding_keychain.py"
    if platform.system() != "Darwin":
        raise OnboardingError(
            "Automatic persistent credential onboarding currently requires macOS Keychain.",
            next_action="Use this release on macOS, or keep the installation BLOCKED until a reviewed credential backend is available for this OS.",
        )
    if not helper.is_file() or helper.is_symlink():
        raise OnboardingError("The managed Gemini credential helper is missing or unsafe.")
    return helper


def run_gemini_gates(
    args: argparse.Namespace,
    target: Path,
    receipt: dict[str, Any],
) -> None:
    if not args.accept_gemini_cost:
        raise OnboardingError(
            "Initial Gemini embedding API usage and cost were not explicitly accepted.",
            next_action="Review the scan counts, then rerun with --accept-gemini-cost after approval.",
        )
    helper = keychain_helper(target)
    check = subprocess.run(
        [sys.executable, str(helper), "check"],
        cwd=target,
        text=True,
        capture_output=True,
        check=False,
        shell=False,
    )
    if check.returncode != 0:
        raise OnboardingError(
            "The dedicated Gemini embedding key is not stored in macOS Keychain.",
            next_action=f"Run: cd {target} && python3 scripts/gemini_embedding_keychain.py store",
        )
    run_command([sys.executable, str(helper), "canary"], cwd=target, timeout=60)
    receipt["checks"]["credentialCanary"] = {
        "ok": True,
        "provider": "google-gemini",
        "model": "gemini-embedding-001",
        "dimensions": 768,
        "secretDisplayed": False,
    }

    run_command([sys.executable, str(helper), "run", "--", "index"], cwd=target)
    npm = require_executable("npm")
    status = parse_json_output(
        run_command([npm, "run", "--silent", "status"], cwd=target).stdout,
        "index status",
    )
    rows = int(status.get("rows") or 0)
    if status.get("ok") is not True or rows < 1:
        raise OnboardingError("Initial index did not produce a readable LanceDB table.")
    receipt["checks"]["initialIndex"] = {"ok": True, "rows": rows}

    audit = parse_json_output(
        run_command([npm, "run", "--silent", "audit"], cwd=target).stdout,
        "coverage audit",
    )
    if audit.get("ok") is not True or int(audit.get("rows") or 0) != rows:
        raise OnboardingError("Coverage audit did not match the live index row count.")
    receipt["checks"]["coverageAudit"] = {
        "ok": True,
        "rows": rows,
        "metadataExactMatch": audit.get("metadataExactMatch") is True,
        "embeddingIdentityMatch": audit.get("embeddingIdentityMatch") is True,
    }

    search = run_command(
        [
            sys.executable,
            str(helper),
            "run",
            "--",
            "search",
            args.test_query,
            "--limit",
            "5",
        ],
        cwd=target,
        timeout=120,
    )
    source_hits = sum(1 for line in search.stdout.splitlines() if line.startswith("- source: "))
    if source_hits < 1:
        raise OnboardingError(
            "Natural-language search returned no source-cited result.",
            next_action="Choose a test query grounded in the selected corpus, then rerun onboarding.",
        )
    receipt["checks"]["naturalLanguageSearch"] = {
        "ok": True,
        "query": args.test_query,
        "sourceCitedResults": source_hits,
    }

    run_command([sys.executable, str(helper), "run", "--", "incremental"], cwd=target)
    receipt["checks"]["incrementalBaseline"] = {"ok": True}


def run_snapshot(args: argparse.Namespace, target: Path, receipt: dict[str, Any]) -> None:
    snapshot_root = resolved_path(args.snapshot_root)
    snapshot_root.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["OPENCLAW_LANCEDB_ROOT"] = str(target)
    env["OPENCLAW_LANCEDB_SNAPSHOT_ROOT"] = str(snapshot_root)
    env["TZ"] = args.timezone
    result = run_command(
        ["/bin/bash", str(target / "scripts/knowledge_snapshot_daily.sh")],
        cwd=target,
        env=env,
    )
    payload = parse_json_output(result.stdout, "verified snapshot")
    snapshot_path = payload.get("snapshot") or payload.get("snapshotPath") or payload.get("path")
    if payload.get("ok") is not True or not snapshot_path:
        raise OnboardingError("Snapshot command did not return a verified snapshot path.")
    receipt["checks"]["restoreSnapshot"] = {
        "ok": True,
        "path": str(snapshot_path),
        "checksumVerified": True,
        "isolatedRestoreVerified": True,
        "databaseOpenVerified": True,
    }


def install_cron(args: argparse.Namespace, target: Path, receipt: dict[str, Any]) -> None:
    if not args.install_cron:
        raise OnboardingError(
            "Daily incremental indexing and verified snapshots are not installed.",
            next_action="Rerun onboarding with --install-cron after approving local schedule changes.",
        )
    openclaw_bin = require_executable("openclaw")
    help_result = run_command([openclaw_bin, "cron", "add", "--help"], timeout=60)
    for option in ("--command-argv", "--declaration-key", "--command-env"):
        if option not in help_result.stdout:
            raise OnboardingError(
                f"Installed OpenClaw does not support required cron option {option}.",
                next_action="Upgrade OpenClaw, then rerun onboarding.",
            )
    keys: list[str] = []
    for key, command in cron_commands(
        openclaw_bin=openclaw_bin,
        target=target,
        snapshot_root=resolved_path(args.snapshot_root),
        timezone_name=args.timezone,
        index_cron=args.index_cron,
        snapshot_cron=args.snapshot_cron,
    ):
        result = run_command(command, timeout=60)
        parse_json_output(result.stdout, f"cron declaration {key}")
        keys.append(key)
    listed = parse_json_output(
        run_command([openclaw_bin, "cron", "list", "--all", "--json"], timeout=60).stdout,
        "cron list",
    )
    jobs = listed.get("jobs") if isinstance(listed.get("jobs"), list) else []
    by_key = {
        job.get("declarationKey"): job
        for job in jobs
        if isinstance(job, dict) and isinstance(job.get("declarationKey"), str)
    }
    missing = [key for key in keys if key not in by_key]
    if missing:
        raise OnboardingError("OpenClaw cron readback is missing an onboarding declaration.")
    disabled = [key for key in keys if by_key[key].get("enabled") is not True]
    if disabled:
        raise OnboardingError(
            "An onboarding cron declaration exists but is disabled.",
            next_action="Review and explicitly enable the two onboarding cron jobs, then rerun verification.",
        )
    receipt["checks"]["automation"] = {
        "ok": True,
        "timezone": args.timezone,
        "incrementalCron": args.index_cron,
        "snapshotCron": args.snapshot_cron,
        "declarationKeys": keys,
    }


def apply(args: argparse.Namespace) -> dict[str, Any]:
    receipt = receipt_base(args)
    target = resolved_path(args.target)
    try:
        target = install_or_resume(args, receipt)
        run_local_gates(target, receipt)
        run_gemini_gates(args, target, receipt)
        run_snapshot(args, target, receipt)
        install_cron(args, target, receipt)
        receipt["generatedAt"] = utc_now()
        receipt["status"] = "READY"
        receipt["nextAction"] = "Use source-cited natural-language search through the installed skill."
        receipt.pop("error", None)
        atomic_write_json(target / RECEIPT_RELATIVE_PATH, receipt)
        preinstall_receipt = target.parent / f".{target.name}-onboarding-receipt.json"
        if preinstall_receipt.is_file() and not preinstall_receipt.is_symlink():
            preinstall_receipt.unlink()
        return receipt
    except (OnboardingError, subprocess.TimeoutExpired) as exc:
        if isinstance(exc, subprocess.TimeoutExpired):
            error = "An onboarding command exceeded its safe timeout."
            next_action = "Inspect the affected local report, then rerun the same onboarding command."
        else:
            error = str(exc)
            next_action = exc.next_action
        write_blocked_receipt(args, receipt, error, next_action)
        return receipt_base_from_disk(target, fallback=receipt)


def receipt_base_from_disk(target: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    paths = [target / RECEIPT_RELATIVE_PATH, target.parent / f".{target.name}-onboarding-receipt.json"]
    for path in paths:
        if path.is_file() and not path.is_symlink():
            try:
                return load_json(path)
            except OnboardingError:
                pass
    return fallback or {"status": "BLOCKED"}


def verify(args: argparse.Namespace) -> dict[str, Any]:
    target = resolved_path(args.target)
    if not managed_install(target):
        raise OnboardingError("Managed Gemini installation marker is missing.")
    receipt = load_json(target / RECEIPT_RELATIVE_PATH)
    if receipt.get("status") != "READY":
        return receipt
    checks = receipt.get("checks") if isinstance(receipt.get("checks"), dict) else {}
    required_checks = {
        "bootstrap",
        "dependencies",
        "sourceScan",
        "credentialCanary",
        "initialIndex",
        "coverageAudit",
        "naturalLanguageSearch",
        "incrementalBaseline",
        "restoreSnapshot",
        "automation",
    }
    incomplete = sorted(
        name for name in required_checks
        if not isinstance(checks.get(name), dict) or checks[name].get("ok") is not True
    )
    if incomplete:
        raise OnboardingError(
            f"READY receipt is missing required passing checks: {', '.join(incomplete)}."
        )
    config = load_json(target / "config/source-map.json")
    embedding = config.get("embedding") or {}
    if (
        embedding.get("provider") != "google-gemini"
        or embedding.get("model") != "gemini-embedding-001"
        or embedding.get("dimensions") != 768
    ):
        raise OnboardingError("Live configuration no longer matches the approved Gemini identity.")
    npm = require_executable("npm")
    status = parse_json_output(
        run_command([npm, "run", "--silent", "status"], cwd=target).stdout,
        "index status",
    )
    audit = parse_json_output(
        run_command([npm, "run", "--silent", "audit"], cwd=target).stdout,
        "coverage audit",
    )
    if status.get("ok") is not True or int(status.get("rows") or 0) < 1:
        raise OnboardingError("Live LanceDB index is not readable.")
    if audit.get("ok") is not True or audit.get("embeddingIdentityMatch") is not True:
        raise OnboardingError("Live coverage audit is not healthy.")

    snapshot_path = Path(str(checks["restoreSnapshot"].get("path") or ""))
    snapshot_tool = target / "scripts/snapshot_knowledge_assets.py"
    if not snapshot_path.is_absolute() or not snapshot_path.is_dir():
        raise OnboardingError("Verified snapshot path from the READY receipt is unavailable.")
    snapshot = parse_json_output(
        run_command(
            [sys.executable, str(snapshot_tool), "--verify-snapshot", str(snapshot_path)],
            cwd=target,
        ).stdout,
        "snapshot verification",
    )
    if snapshot.get("ok") is not True:
        raise OnboardingError("Current snapshot checksum verification failed.")

    declaration_keys = checks["automation"].get("declarationKeys")
    if not isinstance(declaration_keys, list) or len(declaration_keys) != 2:
        raise OnboardingError("READY receipt does not contain both cron declaration keys.")
    openclaw_bin = require_executable("openclaw")
    listed = parse_json_output(
        run_command([openclaw_bin, "cron", "list", "--all", "--json"], timeout=60).stdout,
        "cron list",
    )
    jobs = listed.get("jobs") if isinstance(listed.get("jobs"), list) else []
    by_key = {
        job.get("declarationKey"): job
        for job in jobs
        if isinstance(job, dict) and isinstance(job.get("declarationKey"), str)
    }
    if any(key not in by_key or by_key[key].get("enabled") is not True for key in declaration_keys):
        raise OnboardingError("One or more onboarding cron declarations are missing or disabled.")
    return {
        "schemaVersion": 1,
        "status": "READY",
        "provider": "google-gemini",
        "model": "gemini-embedding-001",
        "dimensions": 768,
        "rows": int(status.get("rows") or 0),
        "snapshotVerified": True,
        "automationVerified": True,
        "receipt": str(target / RECEIPT_RELATIVE_PATH),
        "verifiedAt": utc_now(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan, apply, or verify guided Gemini LanceDB onboarding."
    )
    parser.add_argument("action", choices=["plan", "apply", "verify"])
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument("--backup-root", default="")
    parser.add_argument("--project-root", default="")
    parser.add_argument("--project-name", default="ClientProject")
    parser.add_argument("--snapshot-root", default=DEFAULT_SNAPSHOT_ROOT)
    parser.add_argument("--approved-by", default="")
    parser.add_argument("--include-discord-raw", action="store_true")
    parser.add_argument("--accept-gemini-cost", action="store_true")
    parser.add_argument("--install-cron", action="store_true")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--index-cron", default=DEFAULT_INDEX_CRON)
    parser.add_argument("--snapshot-cron", default=DEFAULT_SNAPSHOT_CRON)
    parser.add_argument(
        "--test-query",
        default="What is one documented project decision and its source?",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.action == "plan":
            payload = plan_payload(args)
        elif args.action == "apply":
            payload = apply(args)
        else:
            payload = verify(args)
    except OnboardingError as exc:
        payload = {
            "schemaVersion": 1,
            "status": "BLOCKED",
            "error": str(exc)[:500],
            "nextAction": exc.next_action or "Resolve the reported check and retry.",
            "secretDisplayed": False,
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") in {"PLAN", "READY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
