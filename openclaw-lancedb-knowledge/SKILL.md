---
name: openclaw-lancedb-knowledge
description: Build, operate, troubleshoot, or replicate Jasper/Ansai-style OpenClaw knowledge search using local LanceDB, Markdown source maps, secret redaction, incremental indexing, Google Gemini or local-hash embeddings, and source-cited retrieval for project memory, Discord/channel backup summaries, Obsidian-style vaults, handoff files, and client documentation. Use when asked to install or create an OpenClaw LanceDB knowledge base, search historical project context, index OpenClaw memory/backups, configure embeddings, run incremental indexing/cron, or package this workflow for a client.
---

# OpenClaw LanceDB Knowledge

Use this skill to create and operate an OpenClaw-first semantic knowledge layer. Write and preserve instructions so they are readable by general LLM agents, especially Claude Opus-class client agents, not only by this specific OpenClaw instance: use plain imperative steps, explicit paths/commands, minimal local jargon, and source-cited output rules.

```
OpenClaw memory / backup summaries / project docs / Obsidian-style markdown
  -> source-map filters
  -> secret redaction
  -> markdown heading chunks
  -> embeddings
  -> local LanceDB table
  -> source-cited search answers
```

## LLM compatibility rule

Design every client-facing instruction so a general LLM can follow it without knowing this workspace's private habits:

- Use plain English operational steps; avoid unexplained Ansai-only shorthand.
- Keep commands copy-pasteable and parameterized (`--workspace`, `--backup-root`, `--project-root`) instead of hard-coding Jasper's machine paths.
- State privacy gates explicitly before external embeddings.
- Prefer deterministic scripts for fragile steps, but document the script's purpose in natural language.
- Assume many clients will use Claude Opus or another capable LLM to read the skill; make the workflow model-agnostic and source-grounded.
- Keep OpenClaw-specific behavior named as OpenClaw-specific, and provide a generic fallback when possible.

## Default workflow

1. **Confirm scope and privacy.** Identify the workspace, backup summary root, and project-doc roots. If using external embeddings, get explicit approval because redacted private chunks leave the machine.
2. **Bootstrap or inspect the project.** Use `scripts/bootstrap_openclaw_lancedb.py` for a new install, or inspect an existing `knowledge-lancedb/` folder.
3. **Edit `config/source-map.json`.** Prefer summary/project/handoff markdown first; add raw chat or code only when needed.
4. **Run gates.** Run `npm install`, `npm test`, `npm run scan`, then `npm run index` or `npm run incremental`.
5. **Search before answering historical/project-state questions.** Use project filters when possible and cite source paths in the answer.
6. **Set daily incremental indexing** after OpenClaw backup jobs, using the bundled `knowledge_index_incremental.sh` wrapper or the platform's cron mechanism.

## Bootstrap command

From the installed skill folder:

```bash
python3 scripts/bootstrap_openclaw_lancedb.py \
  --target ~/.openclaw/workspace/knowledge-lancedb \
  --workspace ~/.openclaw/workspace \
  --backup-root "$HOME/Desktop/安賽小助手備份/頻道紀錄" \
  --project-root "$HOME/Desktop/Client_Project" \
  --project-name ClientProject \
  --npm-install
```

Use local-only embeddings by default. To enable Google Gemini embeddings:

```bash
python3 scripts/bootstrap_openclaw_lancedb.py \
  --google-gemini \
  --approved-by "Client approved external embeddings on YYYY-MM-DD" \
  --overwrite
```

## Commands after bootstrap

```bash
cd ~/.openclaw/workspace/knowledge-lancedb
npm run scan
npm run index
npm run status
npm run search -- "VASO 文件中心做到哪" -- --project VASO --limit 5
npm run incremental
```

## Answer pattern after retrieval

For user-facing answers, keep it short and source-grounded:

- Conclusion / current state
- Evidence from top retrieved chunks
- Source path(s)
- Recommended next step

If retrieval is weak, say so and run a narrower search with project/channel/date terms before concluding.

## Safety rules

- Do not index secrets intentionally. Keep `**/*secret*`, `**/*token*`, `.env`, `.git`, `node_modules`, builds, and media out by default.
- Secret redaction is a guardrail, not permission to ingest credentials.
- External embedding providers require explicit approval per client/project.
- Changing embedding model or dimensions requires full reindex.
- Do not index raw Discord/chat backups first unless summaries are insufficient; raw data is noisy and privacy-heavy.

## Memory index health and provider migration

Use this section when OpenClaw memory/vector search reports `index metadata is missing`, `vector search paused`, `Dirty: yes`, `Index identity: missing`, or `0 chunks` after files exist.

Diagnosis:
1. Run the platform memory index status command for the affected agent, e.g. `openclaw memory status --index --agent main` when available.
2. Identify the configured embedding provider/model and dimensions.
3. Check whether the index was created with a different provider/model or has missing metadata.
4. Treat provider/model/dimension changes as a migration requiring full reindex.

Repair:
1. Confirm privacy before using external embeddings; private chunks may leave the machine.
2. Fix the desired embedding provider/model in config or project docs.
3. Force rebuild the index, e.g. `openclaw memory index --force --agent main` when available.
4. Verify status shows indexed files/chunks and no paused vector search.
5. Run sample searches for: people/permissions, project decisions, and recent tasks.

Prevention:
- Do not silently switch embedding provider/model on client deployments.
- Record provider/model choice in the client handoff.
- Add daily or weekly index status checks for client knowledge bases.
- If status is broken, prefer repair/reindex before answering memory-dependent questions.

## Bundled resources

- `scripts/bootstrap_openclaw_lancedb.py` — creates a portable `knowledge-lancedb` project from the bundled template.
- `assets/knowledge-lancedb-template/` — Node + LanceDB CLI template copied by the bootstrap script.
- `references/architecture.md` — detailed architecture, schema, ranking, and operations notes.
- `references/source-map-patterns.md` — source-map examples for OpenClaw memory, backup summaries, Obsidian vaults, project docs, and code docs.
