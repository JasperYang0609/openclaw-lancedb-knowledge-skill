# Gemini Repository Cleanup Task Spec

Date: 2026-09-01

Status: `APPROVED_WAITING_FOR_LOCAL_REPO_GATE`

## Background

`JasperYang0609/openclaw-lancedb-knowledge-skill` currently contains the original Gemini product and a later Qwen shadow candidate. Jasper approved splitting the product into two public repositories. This repository must return to a Gemini `embedding-001` product boundary without rewriting public history.

## Goal

Make the existing repository the stable Gemini cloud-embedding edition while preserving its URL, Git history, bootstrap workflow, privacy approval gate, search behavior, archive format, and client upgrade path.

## Start Gate

Do not start runtime cleanup until `JasperYang0609/openclaw-lancedb-knowledge-embedding-local` has passed its local test/security Gate and has an installable candidate on a reviewed feature branch. This avoids removing the only public Qwen candidate before the replacement exists.

## In Scope

- Remove Qwen runtime provider, sidecar, installer, shadow runner, customer CLI, product commands, tests, and packaged payload.
- Make `google-gemini` with model `gemini-embedding-001` the only production embedding provider.
- Keep deterministic embedding mocks only inside tests if needed; do not expose local-hash as a product provider.
- Preserve the external-data approval requirement and Gemini cache behavior.
- Update README, SKILL, architecture, CI, archive builder, tests, repository description, topics, and cross-link to the local repository.
- Add negative scans proving no Qwen product entry remains in runtime, bootstrap, README first screen, or distribution archive.

## Out of Scope

- No Production provider switch, reindex, cache deletion, schedule change, or live data mutation.
- No Git history rewrite, force-push, repository rename, or release deletion.
- No Gemini model upgrade beyond `gemini-embedding-001`.
- No shared-core third repository.

## Acceptance Criteria

- Existing repository URL and skill id remain stable.
- Fresh bootstrap requires an explicit external-embedding approval note and produces a 768-dimensional `gemini-embedding-001` config.
- Index, query, cache, incremental, audit, snapshot, postrun, archive parity, dangerous-exec, dependency, secret, and CI tests pass.
- Production sources and packaged archive contain no Qwen provider, sidecar, installer, shadow command, or local customer CLI.
- README first screen identifies this as the Gemini cloud edition and links to the local edition.
- Independent reviewer returns PASS with P0/P1=0 before merge.

## Stop Conditions

- Local replacement Gate is not PASS.
- Unknown dirty changes exist.
- Cleanup breaks existing Gemini bootstrap, privacy approval, cache, index, search, or archive compatibility.
- Any required change would reduce the approved security, privacy, quality, rollback, or evidence standard.
- A secret, model, corpus, vector, cache, or sensitive log is staged for Git.

## Required Closeout

Report changed files, local test logs, OWASP A01-A10 evidence, reviewer verdict, PR, CI run, merge commit, remaining blockers, local/remote HEAD equality, and clean worktree status.
