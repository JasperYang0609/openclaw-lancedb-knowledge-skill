#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "openclaw-lancedb-knowledge" / "scripts" / "bootstrap_openclaw_lancedb.py"


def make_fake_npm(bin_dir: Path, log_path: Path) -> Path:
    npm = bin_dir / "npm"
    npm.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" > {str(log_path)!r}\n"
        f"printf 'cwd=%s\\n' \"$PWD\" >> {str(log_path)!r}\n"
        f"printf 'ignore_scripts=%s\\n' \"${{npm_config_ignore_scripts-}}\" >> {str(log_path)!r}\n",
        encoding="utf-8",
    )
    npm.chmod(0o755)
    return npm


def run_bootstrap(
    target: Path,
    env: dict[str, str],
    *extra: str,
    include_approval: bool = True,
) -> subprocess.CompletedProcess[str]:
    approval = ["--approved-by", "automated bootstrap fixture approval"] if include_approval else []
    return subprocess.run(
        [
            sys.executable,
            str(BOOTSTRAP),
            "--target",
            str(target),
            "--workspace",
            str(target.parent / "workspace"),
            *approval,
            *extra,
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="lancedb-bootstrap-security-") as tmp_dir:
        tmp = Path(tmp_dir)
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        env = {
            "PATH": str(bin_dir),
            "HOME": str(tmp / "home"),
            "TMPDIR": str(tmp),
        }

        default_log = tmp / "npm-default.log"
        fake_npm = make_fake_npm(bin_dir, default_log)
        default_target = tmp / "default-install"
        result = run_bootstrap(default_target, env, "--npm-install")
        assert result.returncode == 0, result.stderr
        default_args = default_log.read_text(encoding="utf-8").splitlines()
        assert default_args[:2] == ["ci", "--ignore-scripts"]
        assert default_args[2] == f"cwd={default_target}"
        assert default_args[3] == "ignore_scripts=true"
        payload = json.loads(result.stdout)
        assert payload["install_command"] == [str(fake_npm.resolve()), "ci", "--ignore-scripts"]
        default_config = json.loads((default_target / "config/source-map.json").read_text(encoding="utf-8"))
        assert all(source.get("sourceType") != "discord_raw" for source in default_config["sources"])
        assert default_config["embedding"]["provider"] == "google-gemini"
        assert default_config["embedding"]["model"] == "gemini-embedding-001"
        assert default_config["embedding"]["dimensions"] == 768
        assert default_config["embedding"]["privacyApprovedBy"] == "automated bootstrap fixture approval"

        raw_target = tmp / "raw-install"
        result = run_bootstrap(
            raw_target,
            env,
            "--backup-root",
            str(tmp / "discord-backup"),
            "--include-discord-raw",
        )
        assert result.returncode == 0, result.stderr
        raw_config = json.loads((raw_target / "config/source-map.json").read_text(encoding="utf-8"))
        raw_sources = [source for source in raw_config["sources"] if source.get("sourceType") == "discord_raw"]
        assert len(raw_sources) == 1
        assert raw_sources[0]["include"] == ["**/raw/**/*.md"]
        assert raw_sources[0]["root"] == str((tmp / "discord-backup").resolve())
        assert raw_config["privacy"]["discordRawApproval"] == "APPROVED_EXTERNAL"

        allow_log = tmp / "npm-allow.log"
        make_fake_npm(bin_dir, allow_log)
        allow_target = tmp / "allow-install"
        result = run_bootstrap(
            allow_target,
            env,
            "--npm-install",
            "--allow-package-scripts",
        )
        assert result.returncode == 0, result.stderr
        allow_args = allow_log.read_text(encoding="utf-8").splitlines()
        assert allow_args[0] == "ci"
        assert "--ignore-scripts" not in allow_args
        assert allow_args[-1] == "ignore_scripts="

        result = run_bootstrap(tmp / "invalid-flags", env, "--allow-package-scripts")
        assert result.returncode != 0
        assert "requires --npm-install" in (result.stderr + result.stdout)

        no_npm_env = {"PATH": str(tmp / "empty-bin"), "HOME": str(tmp / "home")}
        (tmp / "empty-bin").mkdir()
        result = run_bootstrap(tmp / "no-npm", no_npm_env, "--npm-install")
        assert result.returncode != 0
        assert "npm executable not found" in (result.stderr + result.stdout)

        result = run_bootstrap(tmp / "missing-approval", env, include_approval=False)
        assert result.returncode != 0
        assert "--approved-by is required" in (result.stderr + result.stdout)

        result = run_bootstrap(tmp / "workspace", env)
        assert result.returncode != 0
        assert "protected" in (result.stderr + result.stdout)

        result = run_bootstrap(tmp / "home", env)
        assert result.returncode != 0
        assert "protected" in (result.stderr + result.stdout)

        result = run_bootstrap(ROOT, env, "--overwrite")
        assert result.returncode != 0
        assert "repository" in (result.stderr + result.stdout)

        unmanaged = tmp / "unmanaged-target"
        (unmanaged / "src").mkdir(parents=True)
        sentinel = unmanaged / "src" / "sentinel.txt"
        sentinel.write_text("must survive", encoding="utf-8")
        result = run_bootstrap(unmanaged, env, "--overwrite")
        assert result.returncode != 0
        assert "not a recognized managed" in (result.stderr + result.stdout)
        assert sentinel.read_text(encoding="utf-8") == "must survive"

        linked_parent = tmp / "linked-parent"
        linked_parent.symlink_to(tmp / "real-parent", target_is_directory=True)
        (tmp / "real-parent").mkdir()
        result = run_bootstrap(linked_parent / "knowledge-lancedb", env)
        assert result.returncode != 0
        assert "symbolic links" in (result.stderr + result.stdout)

        # A bootstrap-created marker authorizes a later overwrite at the exact managed target.
        result = run_bootstrap(default_target, env, "--overwrite")
        assert result.returncode == 0, result.stderr
        marker = json.loads((default_target / ".openclaw-lancedb-install.json").read_text(encoding="utf-8"))
        assert marker["product"] == "openclaw-lancedb-knowledge-gemini"

        legacy_gemini = tmp / "legacy-gemini"
        (legacy_gemini / "src").mkdir(parents=True)
        (legacy_gemini / "config").mkdir()
        (legacy_gemini / "package.json").write_text(json.dumps({"name": "knowledge-lancedb"}), encoding="utf-8")
        (legacy_gemini / "src/cli.js").write_text("// legacy Gemini CLI\n", encoding="utf-8")
        (legacy_gemini / "config/source-map.json").write_text(json.dumps({
            "embedding": {"provider": "google-gemini", "model": "gemini-embedding-001"}
        }), encoding="utf-8")
        result = run_bootstrap(legacy_gemini, env, "--overwrite")
        assert result.returncode == 0, result.stderr

        local_edition = tmp / "local-edition"
        (local_edition / "src").mkdir(parents=True)
        (local_edition / "config").mkdir()
        (local_edition / "package.json").write_text(json.dumps({"name": "knowledge-lancedb"}), encoding="utf-8")
        local_sentinel = local_edition / "src/local-cli-sentinel.js"
        local_sentinel.write_text("must survive", encoding="utf-8")
        (local_edition / "src/cli.js").write_text("// local edition CLI\n", encoding="utf-8")
        (local_edition / "config/source-map.json").write_text(json.dumps({
            "embedding": {"provider": "qwen-local", "model": "Qwen3-Embedding-4B-Q5_K_M"}
        }), encoding="utf-8")
        result = run_bootstrap(local_edition, env, "--overwrite")
        assert result.returncode != 0
        assert "not a recognized managed" in (result.stderr + result.stdout)
        assert local_sentinel.read_text(encoding="utf-8") == "must survive"

    print("PASS test_bootstrap_security")


if __name__ == "__main__":
    main()
