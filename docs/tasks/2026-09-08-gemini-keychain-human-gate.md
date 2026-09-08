# Task: Gemini Embedding Keychain Human Gate

Status: READY_FOR_HUMAN_GATE

## Background

Jasper approved the cold-standby design and authorized preparation of a secure terminal prompt for a new embedding-only Gemini API key. The key must never be pasted into Discord or stored in project configuration.

## Scope

- Add a macOS Keychain store/check/run/canary utility with fixed service and account identities.
- Store through the native hidden prompt; reject any secret passed as a command-line value.
- Permit secret injection only into the repository's fixed Gemini CLI and a fixed, non-sensitive API canary.
- Update the packaged incremental and search launchers to use the utility.
- Preserve Qwen, live cron, existing Gemini data/cache, and active search routing.

## Acceptance criteria

- Store command contains no secret value and ends in native `security ... -w` prompt mode.
- Check output reveals only presence/absence.
- Missing or malformed secrets fail closed.
- Unknown child commands are rejected; no shell execution is used.
- Existing `GOOGLE_API_KEY` and `GEMINI_API_KEY` values cannot override the dedicated Keychain item.
- Errors never echo the key or raw provider body.
- Full Python/Node tests, product boundary, archive parity, dangerous-exec, dependency and secret scans pass.
- Reviewed commit is pushed; Jasper can use the reviewed repository tool to store the fixed Keychain item before any managed-target cutover.

## Stop conditions

- Any dirty or unrecognized target.
- Any evidence of secret persistence outside Keychain.
- Any requirement to call Gemini, enable cron, stop Qwen, or rebuild the index before Jasper enters the key.

## Delivery status

- Implementation: complete in reviewed repository candidate
- Tests: PASS — Python 27/27; Node 42/42; Keychain targeted 19/19
- Review: PASS — fixed Keychain identity, trusted Node paths, no shell, dedicated-source marker, fail-closed provider behavior
- Commit/push: PASS — implementation commit `020479ef3a18c2fbc5da71e3f13cbc800eda3476`, remote divergence 0/0
- Managed install: deferred until the post-key cutover phase, preserving Qwen and live routing
- Human key gate: ready

## Verification evidence

- Deterministic Skill archive: PASS, 36 files
- Gemini-only product boundary: PASS, 16 production files plus packaged archive
- Dangerous-exec isolation: PASS, 16 production files
- Post-run contract: PASS
- Dependency audit: 0 vulnerabilities
- Secret-pattern and syntax checks: PASS
- Live Gemini requests, index rebuild, cron changes, and Qwen changes: not executed in this phase
