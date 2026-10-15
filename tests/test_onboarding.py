#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import stat
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "openclaw-lancedb-knowledge/scripts/onboard_openclaw_lancedb.py"
spec = importlib.util.spec_from_file_location("lancedb_onboarding", SCRIPT)
onboarding = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(onboarding)


def args_for(tmp: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "action": "plan",
        "target": str(tmp / "workspace" / "knowledge-lancedb"),
        "workspace": str(tmp / "workspace"),
        "backup_root": str(tmp / "backups"),
        "project_root": str(tmp / "project"),
        "project_name": "FixtureProject",
        "snapshot_root": str(tmp / "snapshots"),
        "approved_by": "Fixture approval on 2026-10-15",
        "include_discord_raw": False,
        "accept_gemini_cost": True,
        "install_cron": True,
        "timezone": "Asia/Taipei",
        "index_cron": "15 2 * * *",
        "snapshot_cron": "45 2 * * *",
        "test_query": "What decision is documented?",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="lancedb-onboarding-") as tmp_dir:
        tmp = Path(tmp_dir)
        args = args_for(tmp)

        plan = onboarding.plan_payload(args)
        assert plan["status"] == "PLAN"
        assert plan["provider"] == "google-gemini"
        assert plan["model"] == "gemini-embedding-001"
        assert plan["dimensions"] == 768
        assert plan["automationRequested"] is True
        assert "Gemini API key" in " ".join(plan["requiredHumanInputs"])
        assert "apiKey" not in json.dumps(plan)

        bootstrap = onboarding.bootstrap_command(
            args,
            ROOT / "openclaw-lancedb-knowledge/scripts/bootstrap_openclaw_lancedb.py",
            Path(args.target),
        )
        assert "--approved-by" in bootstrap
        assert "--npm-install" in bootstrap
        assert "--embedding-profile" in bootstrap
        assert "balanced" in bootstrap
        assert not any("api-key" in item.lower() for item in bootstrap)

        commands = onboarding.cron_commands(
            openclaw_bin="/usr/local/bin/openclaw",
            target=Path(args.target),
            snapshot_root=Path(args.snapshot_root),
            timezone_name=args.timezone,
            index_cron=args.index_cron,
            snapshot_cron=args.snapshot_cron,
        )
        assert len(commands) == 2
        keys = [key for key, _ in commands]
        assert len(set(keys)) == 2
        serialized = json.dumps(commands)
        assert "--command-argv" in serialized
        assert "--declaration-key" in serialized
        assert "--command-env" in serialized
        assert "GOOGLE_API_KEY" not in serialized
        assert "GEMINI_API_KEY" not in serialized
        assert "--tools" not in serialized

        receipt_path = tmp / "receipt.json"
        onboarding.atomic_write_json(receipt_path, {"status": "BLOCKED", "secretDisplayed": False})
        mode = stat.S_IMODE(receipt_path.stat().st_mode)
        assert mode == 0o600
        assert json.loads(receipt_path.read_text(encoding="utf-8"))["secretDisplayed"] is False

        blocked_args = args_for(tmp, approved_by="", accept_gemini_cost=False)
        blocked = onboarding.apply(blocked_args)
        assert blocked["status"] == "BLOCKED"
        assert "approval" in blocked["error"].lower()
        assert blocked["secretPersistedInReceipt"] is False
        assert onboarding.receipt_path_for(Path(blocked_args.target)).is_file()
        assert not Path(blocked_args.target).exists()

        with mock.patch.object(onboarding.platform, "system", return_value="Linux"):
            try:
                onboarding.keychain_helper(Path(args.target))
            except onboarding.OnboardingError as exc:
                assert "macOS Keychain" in str(exc)
            else:
                raise AssertionError("unsupported persistent credential platform must block")

        ready_root = tmp / "ready"
        ready_target = ready_root / "knowledge-lancedb"
        ready_target.mkdir(parents=True)
        (ready_target / onboarding.INSTALL_MARKER).write_text(json.dumps({
            "schemaVersion": 1,
            "product": onboarding.PRODUCT_ID,
        }), encoding="utf-8")
        (ready_target / "config").mkdir()
        (ready_target / "config/source-map.json").write_text(json.dumps({
            "embedding": {
                "provider": "google-gemini",
                "model": "gemini-embedding-001",
                "dimensions": 768,
                "privacyApprovedBy": "Fixture approval on 2026-10-15",
            },
            "sources": [
                {
                    "id": "workspace-memory",
                    "root": str((ready_root / "workspace" / "memory").resolve()),
                    "sourceType": "memory",
                },
                {
                    "id": "discord-backup-summary",
                    "root": str((ready_root / "backups").resolve()),
                    "sourceType": "backup_summary",
                },
                {
                    "id": "project-docs",
                    "root": str((ready_root / "project").resolve()),
                    "sourceType": "project_doc",
                },
            ],
        }), encoding="utf-8")
        ready_args = args_for(ready_root, target=str(ready_target))

        def local_gate(_target: Path, receipt: dict[str, object]) -> dict[str, object]:
            receipt["checks"]["sourceScan"] = {"ok": True, "docs": 2, "chunks": 4}
            return {"docs": 2, "chunks": 4}

        def gemini_gate(_args: argparse.Namespace, _target: Path, receipt: dict[str, object]) -> None:
            receipt["checks"]["credentialCanary"] = {"ok": True}
            receipt["checks"]["initialIndex"] = {"ok": True, "rows": 4}
            receipt["checks"]["coverageAudit"] = {"ok": True, "rows": 4}
            receipt["checks"]["naturalLanguageSearch"] = {"ok": True, "sourceCitedResults": 1}
            receipt["checks"]["incrementalBaseline"] = {"ok": True}

        def snapshot_gate(_args: argparse.Namespace, _target: Path, receipt: dict[str, object]) -> None:
            receipt["checks"]["restoreSnapshot"] = {"ok": True, "path": "/tmp/fixture-snapshot"}

        def cron_gate(_args: argparse.Namespace, _target: Path, receipt: dict[str, object]) -> None:
            receipt["checks"]["automation"] = {"ok": True, "declarationKeys": ["index", "snapshot"]}

        with (
            mock.patch.object(onboarding, "run_local_gates", side_effect=local_gate),
            mock.patch.object(onboarding, "run_gemini_gates", side_effect=gemini_gate),
            mock.patch.object(onboarding, "run_snapshot", side_effect=snapshot_gate),
            mock.patch.object(onboarding, "install_cron", side_effect=cron_gate),
        ):
            ready = onboarding.apply(ready_args)
        assert ready["status"] == "READY"
        assert (ready_target / onboarding.RECEIPT_RELATIVE_PATH).is_file()

        with (
            mock.patch.object(onboarding, "run_local_gates", side_effect=local_gate),
            mock.patch.object(onboarding, "run_gemini_gates", side_effect=gemini_gate),
            mock.patch.object(onboarding, "run_snapshot", side_effect=snapshot_gate),
            mock.patch.object(
                onboarding,
                "install_cron",
                side_effect=onboarding.OnboardingError("cron readback failed"),
            ),
        ):
            blocked_after_cron = onboarding.apply(ready_args)
        assert blocked_after_cron["status"] == "BLOCKED"
        assert "cron readback failed" in blocked_after_cron["error"]

        mismatched = args_for(ready_root, target=str(ready_target), include_discord_raw=True)
        mismatch_receipt = onboarding.apply(mismatched)
        assert mismatch_receipt["status"] == "BLOCKED"
        assert "raw-message approval differs" in mismatch_receipt["error"]

        parser = onboarding.build_parser()
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                parser.parse_args(["apply", "--api-key", "must-not-be-accepted"])
        except SystemExit as exc:
            assert exc.code != 0
        else:
            raise AssertionError("API keys must never be accepted as command arguments")

    print("PASS test_onboarding")


if __name__ == "__main__":
    main()
