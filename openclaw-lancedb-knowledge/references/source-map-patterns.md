# Source Map Patterns

Use `config/source-map.json` to keep indexing explicit and client-safe.

## Minimum OpenClaw setup

```json
{
  "id": "workspace-memory",
  "project": "OpenClawOps",
  "sourceType": "memory",
  "root": "/path/to/.openclaw/workspace/memory",
  "include": ["**/*.md"],
  "exclude": ["**/*.bak*", "**/*secret*", "**/*token*"],
  "priority": 0
}
```

## Discord / channel backup summaries

Prefer summaries before raw messages.

```json
{
  "id": "discord-backup-summary",
  "project": "DiscordBackups",
  "sourceType": "backup_summary",
  "root": "/path/to/頻道紀錄",
  "include": ["**/summary/**/*.md", "**/*摘要*.md", "**/*summary*.md"],
  "exclude": ["**/raw/**", "**/legacy/**", "**/legacy_docs/**"],
  "priority": 0
}
```

## Project docs / handoff files

```json
{
  "id": "client-project-docs",
  "project": "ClientProject",
  "sourceType": "project_doc",
  "root": "/path/to/client/project",
  "include": ["*.md", "session_summaries/**/*.md", "docs/**/*.md", "handoff/**/*.md"],
  "exclude": ["**/node_modules/**", "**/build/**", "**/.git/**", "**/dist/**"],
  "priority": 1
}
```

## Obsidian-style vault

```json
{
  "id": "obsidian-vault",
  "project": "ClientVault",
  "sourceType": "obsidian_note",
  "root": "/path/to/vault",
  "include": ["**/*.md"],
  "exclude": [".obsidian/**", "**/.trash/**", "**/templates/**", "**/*secret*", "**/*token*"],
  "priority": 1
}
```

## Code documentation only

Do not index whole code repositories by default. Start with README, schema, architecture, and handoff docs.

```json
{
  "id": "repo-docs",
  "project": "ClientApp",
  "sourceType": "code_doc",
  "root": "/path/to/repo",
  "include": ["README.md", "docs/**/*.md", "supabase/**/*.md", "architecture/**/*.md", "**/*handoff*.md"],
  "exclude": ["**/node_modules/**", "**/.git/**", "**/build/**", "**/dist/**"],
  "priority": 1
}
```

## Quality checklist

- Each source has stable `id`, useful `project`, and clear `sourceType`.
- `include` is narrow enough to avoid junk.
- `exclude` blocks credentials, generated files, dependencies, and media-heavy paths.
- Large raw chat/code sources are added only after summary/project docs prove insufficient.
