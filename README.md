# OpenClaw LanceDB Knowledge Skill

OpenClaw skill for building a local LanceDB semantic knowledge layer over OpenClaw memory, Discord/channel backup summaries, Obsidian-style markdown vaults, handoff files, and client project docs. The skill is written to be readable by general LLM agents, including Claude Opus-class client agents, with explicit commands, privacy gates, and source-cited answer rules.

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
- Local-only hash embedding default
- Optional Google Gemini embedding mode after explicit privacy approval
- Secret redaction before embedding/indexing
- Incremental indexing and cron wrapper
- Source-map examples for memory, backup summaries, project docs, and Obsidian-style vaults
