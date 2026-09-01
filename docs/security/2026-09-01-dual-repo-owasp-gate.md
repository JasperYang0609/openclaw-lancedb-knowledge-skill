# Dual Repository OWASP Top 10:2025 Gate

Date: 2026-09-01

Status: `OPEN`

This register is complete only when both the Gemini and local repositories have exact-commit evidence. A scanner-only result is insufficient.

## Shared Security Scope

- Data: source documents and chunks are D1/D2; credentials, private keys, raw secrets, models, vectors, caches, and private logs must not enter Git.
- Trust boundaries: public GitHub source, dependencies, Gemini API or official Qwen/llama.cpp artifacts, local filesystem, embedding runtime, LanceDB, and source corpus.
- Roles: public maintainer and local installer/operator; no new remote login or tenant system.
- AI overlay: documents are embedding input only, never executable instructions; embedding outputs are schema-validated numeric vectors without tool authority.

## Evidence Register

| OWASP 2025 | Gemini repository required evidence | Local repository required evidence | Status |
| --- | --- | --- | --- |
| A01 Broken Access Control | bootstrap target and cache boundaries; external approval required | managed-root and Production-path negatives; manifest-bound stop/uninstall | OPEN |
| A02 Security Misconfiguration | Gemini-only provider default; privacy notice; no Qwen entry | loopback-only, Web UI off, no cloud fallback, restricted files | OPEN |
| A03 Supply Chain Failures | lockfile audit, archive parity, CI action pins review | immutable model/runtime revisions, checksums, inventory, licenses, audits | OPEN |
| A04 Cryptographic Failures | API key never logged/committed; HTTPS provider | CSPRNG local credential, mode 0600, HTTPS artifacts, no custom crypto | OPEN |
| A05 Injection | CLI/path/config validation; no shell interpolation | URL/path/tar/CLI validation, `shell=False`, malicious fixture tests | OPEN |
| A06 Insecure Design | provider fingerprint and full-reindex boundary | separate identity/index, atomic/idempotent install, no cutover | OPEN |
| A07 Authentication Failures | N/A with evidence: no product login/session | N/A with evidence: no product login/session | OPEN |
| A08 Integrity Failures | cache/index/archive integrity and deterministic build | artifact/file hashes, manifest identity, corruption/rollback tests | OPEN |
| A09 Logging Failures | redacted run/error evidence, no corpus/vector/secret logs | redacted phase/status/receipt, no corpus/vector/secret logs | OPEN |
| A10 Exceptional Conditions | API/cache/index failure and retry tests | interrupted download, range anomaly, disk/port/PID/staging/cleanup tests | OPEN |

## Business Logic Abuse Cases

- Installing or documenting the wrong edition.
- Mixing Gemini and Qwen fingerprints, tables, caches, or states.
- Re-running install/index/uninstall to create duplicates or destroy unmanaged data.
- Injecting Production, home, workspace, symlink, or traversal paths.
- Forging manifests, replacing artifacts, exhausting disk, or leaving partial success marked complete.
- Removing the Gemini Qwen entry before the local replacement is demonstrably installable.

## ASVS Decision

`NOT_APPLICABLE_WITH_EVIDENCE`: neither repository introduces a public Web application, remote product API, authentication, or session boundary. Equivalent CLI, supply-chain, process, filesystem, privacy, and data-integrity controls remain mandatory.

## Release Rule

Every row must end as `PASS`, `BLOCKED`, or `NOT_APPLICABLE_WITH_EVIDENCE`, with reproducible evidence paths and exact commits for both repositories. Any OPEN/FAIL, P0/P1, secret finding, cross-provider product path, or unexplained artifact drift blocks merge and release.
