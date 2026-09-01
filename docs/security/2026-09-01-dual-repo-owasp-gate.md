# Dual Repository OWASP Top 10:2025 Gate

Date: 2026-09-01

Status: `PASS_PRE_MERGE`

This register is complete only when both the Gemini and local repositories have exact-commit evidence. A scanner-only result is insufficient.

## Shared Security Scope

- Data: source documents and chunks are D1/D2; credentials, private keys, raw secrets, models, vectors, caches, and private logs must not enter Git.
- Trust boundaries: public GitHub source, dependencies, Gemini API or official Qwen/llama.cpp artifacts, local filesystem, embedding runtime, LanceDB, and source corpus.
- Roles: public maintainer and local installer/operator; no new remote login or tenant system.
- AI overlay: documents are embedding input only, never executable instructions; embedding outputs are schema-validated numeric vectors without tool authority.

## Evidence Register

| OWASP 2025 | Gemini repository required evidence | Local repository required evidence | Status |
| --- | --- | --- | --- |
| A01 Broken Access Control | bootstrap target/cache boundaries and external approval | managed-root and Production-path negatives; manifest-bound stop/uninstall | PASS |
| A02 Security Misconfiguration | Gemini-only provider default; privacy notice; no local runtime entry | loopback-only, Web UI off, no cloud fallback, restricted files | PASS |
| A03 Supply Chain Failures | lockfile audit, archive parity, immutable CI actions | immutable model/runtime revisions, checksums, inventory, licenses, audits | PASS |
| A04 Cryptographic Failures | API key in header only and never logged/committed; HTTPS provider | CSPRNG local credential, mode 0600, HTTPS artifacts, no custom crypto | PASS |
| A05 Injection | CLI/path/config validation; no shell interpolation | URL/path/tar/CLI validation, `shell=False`, malicious fixture tests | PASS |
| A06 Insecure Design | pinned provider fingerprint and full-reindex boundary | separate identity/index, atomic/idempotent install, no cutover | PASS |
| A07 Authentication Failures | N/A with evidence: no product login/session | N/A with evidence: no product login/session | NOT_APPLICABLE_WITH_EVIDENCE |
| A08 Integrity Failures | numeric/finite/nonzero vector validation, cache/index/archive integrity | artifact/file hashes, manifest identity, corruption/rollback tests | PASS |
| A09 Logging Failures | redacted run/error evidence, no corpus/vector/secret logs | redacted phase/status/receipt, no corpus/vector/secret logs | PASS |
| A10 Exceptional Conditions | API/cache failure, managed overwrite, cross-edition and retry tests | interrupted download, range anomaly, disk/port/PID/staging/cleanup tests | PASS |

## Business Logic Abuse Cases

- Installing or documenting the wrong edition.
- Mixing Gemini and Qwen fingerprints, tables, caches, or states.
- Re-running install/index/uninstall to create duplicates or destroy unmanaged data.
- Injecting Production, home, workspace, symlink, or traversal paths.
- Forging manifests, replacing artifacts, exhausting disk, or leaving partial success marked complete.
- Removing the Gemini Qwen entry before the local replacement is demonstrably installable.

## ASVS Decision

`NOT_APPLICABLE_WITH_EVIDENCE`: neither repository introduces a public Web application, remote product API, authentication, or session boundary. Equivalent CLI, supply-chain, process, filesystem, privacy, and data-integrity controls remain mandatory.

## Exact-Commit Evidence

- Local edition reviewed implementation: `953c4fe85081286d58d660518c8c4926dbfc01fd`; merged public `main`: `7c946d1f86b3c078d5ee5dac99bcc6403055a70f`.
- Gemini edition reviewed implementation: `027ff7f14d04863e46bff0cbab105086d9bd9178`.
- Independent Gemini verdict: `MATCHING_PASS`, P0/P1/P2/P3 = `0/0/0/0`.
- Gemini gates: Node `40/40`, Python `8/8`, bootstrap overwrite/cross-edition negatives, snapshot, dangerous-exec, postrun, deterministic archive parity (`35` files), complete executable-surface allowlists, changed-file secret scan, and `npm audit` with `0` vulnerabilities.
- Attacker regressions: local-edition legacy overwrite is rejected without changing its sentinel; adding an unknown runtime script makes the product-boundary checker fail closed.
- Local gates: one-click CLI and installer lifecycle, official artifact resume/checksum, safe extraction, loopback-only runtime, uninstall/restore, archive parity, dependency, secret, and cloud-boundary checks passed before public merge.

## Release Rule

Every row must end as `PASS`, `BLOCKED`, or `NOT_APPLICABLE_WITH_EVIDENCE`, with reproducible evidence paths and exact commits for both repositories. Any OPEN/FAIL, P0/P1, secret finding, cross-provider product path, or unexplained artifact drift blocks merge and release.
