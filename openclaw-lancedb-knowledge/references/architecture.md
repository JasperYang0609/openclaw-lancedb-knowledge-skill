# OpenClaw LanceDB Architecture

## Universal LLM readability

This skill may be consumed by OpenClaw, Claude Opus, Codex, Cursor, or another client-side agent. Keep all reusable instructions model-agnostic:

- Explain intent before commands.
- Use stable file names and obvious configuration keys.
- Avoid relying on hidden memory, private channel conventions, or model-specific tool names.
- When an action depends on OpenClaw, label it as such and include the underlying shell/project command when safe.
- Require source citation in answers so any LLM can ground its output in retrieved paths.

## Purpose

Create a local semantic retrieval layer for OpenClaw so old decisions, project progress, backup summaries, and handoff notes can be found after session reset or context loss.

## Proven Ansai setup

- Project: `knowledge-lancedb`
- DB: local LanceDB file store at `data/lancedb`
- Table: `knowledge_chunks`
- Primary command: `node src/cli.js`
- Commands: `scan`, `index`, `incremental`, `sync-state`, `status`, `search`
- Default source types: `memory`, `backup_summary`, `project_doc`, `ops_doc`
- Production embedding used by Ansai after Jasper approval: Google Gemini `gemini-embedding-001`, 768 dimensions
- Safe default for new clients: `local-hash-v1`, 384 dimensions, no external API calls

## Data flow

1. `config/source-map.json` declares roots, includes, excludes, project labels, and source types.
2. Files are collected from markdown-only sources, skipping binaries and large files.
3. Text is redacted by `src/security.js` before chunking/embedding.
4. Markdown is split by headings; oversized sections are split with overlap.
5. Rows are embedded and written to LanceDB.
6. Incremental indexing compares `source_path + file_sha256 + embedding config`.
7. Search embeds the query, fetches vector candidates, then reranks with keyword overlap, recency, and progress-document boosts.

## Row schema

Each chunk row stores:

- `id`: stable hash of path, chunk index, and content hash
- `source_id`, `source_path`, `rel_path`, `source_type`
- `project`, `channel`, `title`, `heading`, `date`
- `chunk_index`, `chunk_text`, `token_estimate`
- `file_sha256`, `file_mtime_ms`, `file_bytes`, `content_sha256`
- `secret_redactions`
- `embedding_provider`, `embedding_model`, `embedding_dimensions`
- `vector`

## Embedding modes

### local-hash-v1

Use for proof-of-concept, private data, and installs before approval. It is deterministic and offline, but retrieval quality is weaker than production embeddings.

### google-gemini

Use after explicit privacy approval. It supports multilingual retrieval better and matches the Ansai formal setup:

```json
{
  "provider": "google-gemini",
  "model": "gemini-embedding-001",
  "dimensions": 768,
  "documentTaskType": "RETRIEVAL_DOCUMENT",
  "queryTaskType": "RETRIEVAL_QUERY",
  "batchSize": 40,
  "throttleMs": 250,
  "cachePath": "./data/embedding-cache/google-gemini-embedding-001-768.jsonl"
}
```

API key resolution order in the template:

1. `GOOGLE_API_KEY`
2. `GEMINI_API_KEY`
3. `OPENCLAW_CONFIG_PATH`
4. `~/.openclaw/openclaw.json`
5. `~/.openclaw/config.json`

## Incremental indexing

Use `npm run incremental` after backup jobs. The wrapper script creates a lock directory at `data/index.lock` to prevent overlapping runs and writes logs under `reports/cron-logs/`.

If the table or state file is missing, incremental falls back to a full index.

## Search behavior

Use:

```bash
npm run search -- "query" -- --project ProjectName --limit 5
```

The template fetches more vector candidates than needed, then reranks with:

- vector similarity
- Chinese/English keyword overlap
- recency for progress/status queries
- boosts for handoff/current/progress files

## OpenClaw answer rule

When answering historical or project-state questions, search first, then cite source paths. Do not present retrieved content as guaranteed latest truth if the source is old; state the source date/path and recommend checking live state when needed.
