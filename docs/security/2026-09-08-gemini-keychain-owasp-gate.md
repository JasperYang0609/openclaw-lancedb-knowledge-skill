# Gemini Keychain Human Gate — OWASP Top 10:2025 Gate

Date: 2026-09-08
Status: PASS_FOR_HUMAN_KEY_GATE

## SECURITY_SCOPE

- Data classification: Gemini embedding API key is secret; indexed text remains private/internal and is out of scope until the post-key phase.
- Trust boundaries: terminal TTY, macOS Keychain, fixed Python wrapper, fixed Node Gemini CLI, and later Google Gemini API.
- Roles/tenants: single local macOS user; no Web or multi-tenant interface.
- External services/costs: no external call in this phase; the post-key canary is a separately invoked fixed request.
- AI tools/write capabilities: none in the key-storage path.

## THREAT_MODEL

- Secret disclosure through Discord, shell history, argv, logs, exception bodies, config files, environment inheritance, or Git.
- Command substitution or arbitrary child execution that receives the key.
- An old general-purpose Google provider key silently overriding the dedicated embedding key.
- Partial installation that changes launchers without installing the key wrapper.

## BUSINESS_LOGIC_ABUSE_CASES

- Passing a secret as an extra CLI argument must be impossible by interface design.
- Unknown child commands and shell metacharacters must not create a shell execution path.
- Missing/malformed Keychain items must fail closed and must not fall back to OpenClaw provider configuration.
- Re-running store updates the exact fixed item, not a caller-selected service/account.

## AI_SECURITY_OVERLAY

Not applicable with evidence: the storage/check path does not invoke a model or process untrusted model output. Post-key embedding content controls remain governed by the approved cold-standby design.

## ASVS v5.0.0

Not applicable with evidence: this is a local CLI utility without a Web/API surface. Equivalent controls are OWASP A01–A10, fixed-command tests, secret scanning, and macOS Keychain access control.

## OWASP_2025_MATRIX

- A01 Broken Access Control: PASS — fixed Keychain identity, fixed CLI action allowlist, and trusted Node executable paths are tested.
- A02 Security Misconfiguration: PASS — general provider configuration and inherited environment keys fail closed; wrapper/archive parity passes.
- A03 Supply Chain: PASS — deterministic archive parity passes and `npm audit --omit=dev` reports 0 vulnerabilities.
- A04 Cryptographic Failures: PASS — the secret is persisted only in macOS Keychain; tests verify no secret in argv, status output, or provider error text.
- A05 Injection: PASS — fixed `execve` command, no shell, secret-argument rejection, loader-variable removal, and metacharacter negative tests pass.
- A06 Insecure Design: PASS — pre-key phase cannot call Gemini by default, mutate live routing, or fall back to a general key; human gate is explicit.
- A07 Authentication Failures: NOT_APPLICABLE_WITH_EVIDENCE — no user authentication system; Keychain uses the logged-in macOS security boundary.
- A08 Integrity Failures: PASS — deterministic archive, executable-mode identity, product boundary, and post-run contract checks pass. Managed-target installation is deferred to the post-key phase.
- A09 Logging Failures: PASS — presence output is metadata-only and provider error bodies are never logged by the canary.
- A10 Exceptional Conditions: PASS — missing/malformed key, Keychain failure, timeout, HTTP error, wrong dimension, non-finite vector, and zero-norm vector fail closed.

## SECURITY_CLOSEOUT

- OWASP A01–A10 status: PASS / NOT_APPLICABLE_WITH_EVIDENCE as recorded above
- Open P0/P1/P2/P3: 0 / 0 / 0 / 0
- Evidence: Python 27/27; Node 42/42; Keychain targeted 19/19; Skill archive 36 files; Gemini product boundary 16 production files plus archive; dangerous-exec 16 files; post-run PASS; dependency audit 0 vulnerabilities; secret-pattern and syntax checks PASS.
- Residual risk: Keychain authorizes `/usr/bin/security` for unattended access under the logged-in macOS account; host compromise or same-account compromise remains outside this utility's protection.
- Release decision: PASS for commit/push and the human key gate. Live Gemini calls, managed installation, index rebuild, cron cutover, and Qwen cold-standby transition remain BLOCKED until Jasper stores the dedicated key and the post-key gates pass.
