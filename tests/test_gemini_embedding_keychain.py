from __future__ import annotations

import importlib.util
import io
import subprocess
import urllib.error
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "openclaw-lancedb-knowledge"
    / "assets"
    / "knowledge-lancedb-template"
    / "scripts"
    / "gemini_embedding_keychain.py"
)
SPEC = importlib.util.spec_from_file_location("gemini_embedding_keychain", SCRIPT)
assert SPEC and SPEC.loader
KEYCHAIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(KEYCHAIN)


def completed(*, returncode: int = 0, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


def test_store_command_uses_fixed_identity_and_native_hidden_prompt() -> None:
    command = KEYCHAIN.store_command()
    assert command[0] == "/usr/bin/security"
    assert command[-1] == "-w"
    assert command[command.index("-a") + 1] == KEYCHAIN.KEYCHAIN_ACCOUNT
    assert command[command.index("-s") + 1] == KEYCHAIN.KEYCHAIN_SERVICE
    assert not any("test-only-secret-value" in argument for argument in command)


@pytest.mark.parametrize(
    "value",
    ["", "short", "a" * 513, "a" * 19, "valid-but has-space", "valid-key\nwith-newline"],
)
def test_validate_key_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(KEYCHAIN.KeychainError):
        KEYCHAIN.validate_key(value)


def test_read_key_uses_fixed_command_and_keeps_secret_in_memory() -> None:
    secret = "test-only-dedicated-secret-value"
    seen: dict[str, object] = {}

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen["command"] = command
        seen["kwargs"] = kwargs
        return completed(stdout=secret + "\n")

    assert KEYCHAIN.read_key(runner) == secret
    assert seen["command"] == KEYCHAIN.key_read_command()
    assert secret not in seen["command"]
    assert seen["kwargs"] == {"check": False, "capture_output": True, "text": True}


def test_presence_check_suppresses_keychain_output() -> None:
    seen: dict[str, object] = {}

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen["command"] = command
        seen["kwargs"] = kwargs
        return completed()

    assert KEYCHAIN.check_key_presence(runner)
    assert seen["command"] == KEYCHAIN.key_presence_command()
    assert seen["kwargs"] == {
        "check": False,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "text": True,
    }


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["status"],
        ["search", "--api-key", "secret"],
        ["search", "--google-api-key=secret"],
        ["search", "--gemini-api-key=secret"],
        ["search", "query\x00suffix"],
    ],
)
def test_validate_cli_args_rejects_unapproved_or_secret_inputs(arguments: list[str]) -> None:
    with pytest.raises(KEYCHAIN.KeychainError):
        KEYCHAIN.validate_cli_args(arguments)


def test_node_command_preserves_metacharacters_as_one_argument_without_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = "literal $(touch never) ; echo never"
    monkeypatch.setenv("PATH", "/tmp/attacker-controlled-path")
    command, project_root = KEYCHAIN.node_command(["search", query, "--limit", "5"])
    assert command[-3:] == [query, "--limit", "5"]
    assert command[1] == str(project_root / "src" / "cli.js")
    assert command[0] != "/bin/sh"
    assert not command[0].startswith("/tmp/")


def test_child_environment_removes_inherited_secret_and_loader_injection() -> None:
    environment = KEYCHAIN.child_environment(
        {
            "PATH": "/usr/bin:/bin",
            "GOOGLE_API_KEY": "old-google",
            "GEMINI_API_KEY": "old-gemini",
            "NODE_OPTIONS": "--require attacker.js",
            "NODE_PATH": "/tmp/attacker",
            "DYLD_INSERT_LIBRARIES": "/tmp/attacker.dylib",
            "LD_PRELOAD": "/tmp/attacker.so",
        },
        "new-dedicated-secret-value",
    )
    assert environment["GOOGLE_API_KEY"] == "new-dedicated-secret-value"
    assert environment["OPENCLAW_GEMINI_KEY_SOURCE"] == KEYCHAIN.KEYCHAIN_SERVICE
    assert "GEMINI_API_KEY" not in environment
    assert "NODE_OPTIONS" not in environment
    assert "NODE_PATH" not in environment
    assert "DYLD_INSERT_LIBRARIES" not in environment
    assert "LD_PRELOAD" not in environment


def test_canary_payload_requires_finite_nonzero_768_vector() -> None:
    KEYCHAIN.validate_canary_payload({"embedding": {"values": [1.0] * 768}})
    with pytest.raises(KEYCHAIN.KeychainError, match="dimension"):
        KEYCHAIN.validate_canary_payload({"embedding": {"values": [1.0] * 767}})
    with pytest.raises(KEYCHAIN.KeychainError, match="non-finite"):
        KEYCHAIN.validate_canary_payload({"embedding": {"values": [float("nan")] * 768}})
    with pytest.raises(KEYCHAIN.KeychainError, match="zero-norm"):
        KEYCHAIN.validate_canary_payload({"embedding": {"values": [0.0] * 768}})


def test_canary_http_error_never_reads_or_reports_response_body() -> None:
    secret_body = b"provider body with secret SHOULD_NOT_APPEAR"

    def opener(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.HTTPError(
            "https://example.invalid",
            403,
            "forbidden",
            {},
            io.BytesIO(secret_body),
        )

    with pytest.raises(KEYCHAIN.KeychainError) as caught:
        KEYCHAIN.run_canary("test-only-dedicated-secret-value", opener)
    assert "SHOULD_NOT_APPEAR" not in str(caught.value)
    assert "test-only-dedicated-secret-value" not in str(caught.value)
    assert "HTTP 403" in str(caught.value)
