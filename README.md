# OpenClaw LanceDB Knowledge Skill — Gemini Edition

This public repository is the Google Gemini cloud-embedding edition of the OpenClaw LanceDB knowledge skill. It is pinned to `gemini-embedding-001`; the database and cache stay local, while redacted document chunks are sent to Google for embedding only after explicit approval.

Need an offline edition with no cloud embedding API? Use [openclaw-lancedb-knowledge-embedding-local](https://github.com/JasperYang0609/openclaw-lancedb-knowledge-embedding-local).

## Install

```bash
npx skills add JasperYang0609/openclaw-lancedb-knowledge-skill@openclaw-lancedb-knowledge -g
```

If your installer expects a packaged skill file, download:

```text
https://github.com/JasperYang0609/openclaw-lancedb-knowledge-skill/raw/main/dist/openclaw-lancedb-knowledge.skill
```

## What it includes

- Model-agnostic / Opus-readable skill instructions
- OpenClaw-specific LanceDB workflow instructions
- Portable `knowledge-lancedb` Node template using `@lancedb/lancedb`
- Google Gemini `gemini-embedding-001` after explicit privacy approval, with L2-normalized vectors and a local embedding cache
- Stable `balanced` Gemini profile (768 dimensions) plus an opt-in `high-quality` profile (3072 dimensions, separate cache, full-reindex guard)
- Paragraph-aware chunking and deterministic semantic metadata (`doc_type`, tags, importance) that never depends on an LLM
- Model-agnostic, opt-in AI enrichment via a strict JSONL contract; AI fields are auxiliary, confidence-gated, and cannot overwrite authoritative source metadata
- A source-grounded retrieval benchmark with Hit@K/MRR metrics and a 20-case release gate
- Secret redaction before embedding/indexing, covering common API keys, cloud/chat platform tokens, PEM blocks, URL credentials, and Chinese credential labels
- Incremental indexing and cron wrapper, with embedding-cache compaction and report/log rotation
- Source-map examples for memory, backup summaries, opt-in Discord raw history, project docs, and Obsidian-style vaults
- A read-only exact coverage audit for source chunks, metadata/tags, and embedding identity
- Checksummed restore snapshots containing LanceDB, index state, embedding cache, tag rules, enrichment, and config
- Safe rolling retention for 30-day daily snapshots plus a combined 7-day/10-copy `incident-*` and `repair-*` set; unrelated manual snapshots are never pruned
- Post-closeout snapshot gates for absolute-path verification, freshness, isolated restore, LanceDB open, and row-count readback
- Explicit Discord raw privacy states and real-date summary validation that rejects synthetic inventory indexes
- Cron preflight that rejects legacy `payload.toolsAllow`, requires `--clear-tools`, and verifies GPT/Codex shell access with a temporary isolated canary
- Supply-chain-safe bootstrap: fixed `npm ci --ignore-scripts` by default, explicit lifecycle-script opt-in, and a non-executing post-run checker

## Quality and safety defaults

- Bootstrap fails closed until `--approved-by` records who approved sending redacted chunks to Google Gemini.
- Gemini uses 768 dimensions by default. Choose `--embedding-profile high-quality` only when you accept a one-time 3072-dimensional rebuild.
- AI enrichment is disabled by default and no bundled command uploads private chunks. `enrich:prepare` creates a local redacted JSONL file; a human-approved model workflow produces output; `enrich:validate` rejects malformed rows and attempted core-field overrides.
- Copy `config/benchmark.example.json` to `config/benchmark.json`, replace the 20 examples with corpus-specific ground truth, and run `npm run benchmark -- --release-gate` before claiming a quality improvement.

Example bootstrap:

```bash
python3 openclaw-lancedb-knowledge/scripts/bootstrap_openclaw_lancedb.py \
  --target ~/.openclaw/workspace/knowledge-lancedb \
  --workspace ~/.openclaw/workspace \
  --approved-by "Client approved Google embeddings on YYYY-MM-DD"
```

## Maintainer use of Codex

This project is maintained as part of the OpenClaw ecosystem. We plan to use Codex to review pull requests, improve LanceDB/OpenClaw compatibility, generate tests for indexing and retrieval behavior, and keep installation and source-map documentation current.

API-assisted maintenance should focus on reusable open-source workflows: issue triage, regression checks, documentation updates, and release notes. Codex should not be used to index or inspect private customer memories, transcripts, backups, or project documents.
