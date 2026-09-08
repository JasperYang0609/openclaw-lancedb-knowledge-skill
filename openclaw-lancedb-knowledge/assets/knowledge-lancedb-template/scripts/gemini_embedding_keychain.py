#!/usr/bin/env python3
"""Store and use the dedicated Gemini embedding key without persisting it in files."""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


KEYCHAIN_SERVICE = "com.ansai.openclaw.gemini-embedding"
KEYCHAIN_ACCOUNT = "embedding-api-key"
SECURITY_BIN = Path("/usr/bin/security")
ALLOWED_CLI_ACTIONS = {"index", "incremental", "search", "benchmark"}
FORBIDDEN_ARGUMENTS = {
    "--api-key",
    "--google-api-key",
    "--gemini-api-key",
    "-w",
    "--password",
}
CANARY_MODEL = "gemini-embedding-001"
CANARY_DIMENSIONS = 768
TRUSTED_NODE_CANDIDATES = (
    Path("/opt/homebrew/opt/node@22/bin/node"),
    Path("/opt/homebrew/bin/node"),
    Path("/usr/local/bin/node"),
    Path("/usr/bin/node"),
)
TRUSTED_NODE_ROOTS = (
    Path("/opt/homebrew/Cellar"),
    Path("/usr/local/Cellar"),
    Path("/usr/bin"),
)


class KeychainError(RuntimeError):
    """A safe, non-secret-bearing Keychain failure."""


def store_command() -> list[str]:
    """Return a fixed command whose final bare -w makes security prompt via TTY."""
    return [
        str(SECURITY_BIN),
        "add-generic-password",
        "-U",
        "-a",
        KEYCHAIN_ACCOUNT,
        "-s",
        KEYCHAIN_SERVICE,
        "-D",
        "application password",
        "-j",
        "Dedicated Google Gemini embedding API key for OpenClaw LanceDB",
        "-T",
        str(SECURITY_BIN),
        "-w",
    ]


def key_presence_command() -> list[str]:
    return [
        str(SECURITY_BIN),
        "find-generic-password",
        "-a",
        KEYCHAIN_ACCOUNT,
        "-s",
        KEYCHAIN_SERVICE,
    ]


def key_read_command() -> list[str]:
    return [*key_presence_command(), "-w"]


def validate_key(value: str) -> str:
    key = value.rstrip("\r\n")
    if not 20 <= len(key) <= 512:
        raise KeychainError("Stored Gemini embedding key has an invalid length; update the Keychain item.")
    if any(character.isspace() or ord(character) < 33 or ord(character) > 126 for character in key):
        raise KeychainError("Stored Gemini embedding key has invalid characters; update the Keychain item.")
    return key


def read_key(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    result = runner(
        key_read_command(),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise KeychainError(
            "Dedicated Gemini embedding key is not available in macOS Keychain; run the store command first."
        )
    return validate_key(result.stdout)


def check_key_presence(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> bool:
    result = runner(
        key_presence_command(),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.returncode == 0


def validate_cli_args(arguments: list[str]) -> list[str]:
    if not arguments:
        raise KeychainError("A Gemini CLI action is required.")
    if arguments[0] not in ALLOWED_CLI_ACTIONS:
        raise KeychainError(f"Gemini CLI action is not allowed: {arguments[0]}")
    for index, argument in enumerate(arguments):
        lowered = argument.lower()
        if lowered in FORBIDDEN_ARGUMENTS or any(
            lowered.startswith(prefix + "=") for prefix in FORBIDDEN_ARGUMENTS if prefix.startswith("--")
        ):
            raise KeychainError(f"Secret-bearing CLI arguments are forbidden at position {index}.")
        if "\x00" in argument:
            raise KeychainError("CLI arguments must not contain NUL bytes.")
    return arguments


def child_environment(source: dict[str, str], key: str) -> dict[str, str]:
    environment = dict(source)
    for name in list(environment):
        if name in {"GOOGLE_API_KEY", "GEMINI_API_KEY", "NODE_OPTIONS", "NODE_PATH"}:
            environment.pop(name, None)
        elif name.startswith("DYLD_") or name.startswith("LD_PRELOAD"):
            environment.pop(name, None)
    environment["GOOGLE_API_KEY"] = key
    environment["OPENCLAW_GEMINI_KEY_SOURCE"] = KEYCHAIN_SERVICE
    return environment


def node_command(arguments: list[str]) -> tuple[list[str], Path]:
    validated = validate_cli_args(arguments)
    project_root = Path(__file__).resolve().parents[1]
    cli = project_root / "src" / "cli.js"
    if cli.is_symlink() or not cli.is_file():
        raise KeychainError("Managed Gemini CLI is missing or unsafe.")
    resolved_node: Path | None = None
    for candidate in TRUSTED_NODE_CANDIDATES:
        if not candidate.exists():
            continue
        resolved = candidate.resolve()
        if resolved.is_file() and any(resolved.is_relative_to(root) for root in TRUSTED_NODE_ROOTS):
            resolved_node = resolved
            break
    if resolved_node is None:
        raise KeychainError("A trusted system or Homebrew Node.js executable was not found.")
    return [str(resolved_node), str(cli), *validated], project_root


def validate_canary_payload(payload: Any) -> None:
    vector = payload.get("embedding", {}).get("values") if isinstance(payload, dict) else None
    if not isinstance(vector, list) or len(vector) != CANARY_DIMENSIONS:
        raise KeychainError("Gemini canary returned an unexpected embedding dimension.")
    if not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        for value in vector
    ):
        raise KeychainError("Gemini canary returned a non-finite embedding vector.")
    if sum(value * value for value in vector) <= 0:
        raise KeychainError("Gemini canary returned a zero-norm embedding vector.")


def run_canary(
    key: str,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> None:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{CANARY_MODEL}:embedContent"
    body = json.dumps({
        "model": f"models/{CANARY_MODEL}",
        "content": {"parts": [{"text": "OpenClaw Gemini embedding connectivity canary"}]},
        "taskType": "RETRIEVAL_QUERY",
        "outputDimensionality": CANARY_DIMENSIONS,
    }).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with opener(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise KeychainError(f"Gemini canary failed with HTTP {exc.code}; the response body was not logged.") from None
    except (urllib.error.URLError, TimeoutError):
        raise KeychainError("Gemini canary could not reach Google within the allowed time.") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise KeychainError("Gemini canary returned an invalid response; the response body was not logged.") from None
    validate_canary_payload(payload)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage the dedicated Gemini embedding API key in macOS Keychain."
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("store", help="Open the native hidden Keychain password prompt")
    subparsers.add_parser("check", help="Report only whether the Keychain item exists")
    subparsers.add_parser("canary", help="Run one fixed Gemini embedding connectivity check")
    run_parser = subparsers.add_parser("run", help="Run a fixed Gemini CLI action with the Keychain value")
    run_parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    try:
        if args.action == "store":
            if not SECURITY_BIN.is_file():
                raise KeychainError("macOS security executable was not found.")
            print("Enter the dedicated Gemini embedding API key at the native hidden prompt.", flush=True)
            os.execv(str(SECURITY_BIN), store_command())
            raise AssertionError("os.execv unexpectedly returned")

        if args.action == "check":
            present = check_key_presence()
            print(json.dumps({
                "ok": present,
                "service": KEYCHAIN_SERVICE,
                "account": KEYCHAIN_ACCOUNT,
                "secretDisplayed": False,
            }))
            return 0 if present else 2

        key = read_key()
        if args.action == "canary":
            run_canary(key)
            print(json.dumps({
                "ok": True,
                "provider": "google-gemini",
                "model": CANARY_MODEL,
                "dimensions": CANARY_DIMENSIONS,
                "secretDisplayed": False,
            }))
            return 0

        arguments = list(args.arguments)
        if arguments and arguments[0] == "--":
            arguments = arguments[1:]
        command, project_root = node_command(arguments)
        os.chdir(project_root)
        os.execve(command[0], command, child_environment(os.environ, key))
        raise AssertionError("os.execve unexpectedly returned")
    except KeychainError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
