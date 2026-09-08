#!/usr/bin/env bash
set -euo pipefail
ROOT="${OPENCLAW_LANCEDB_ROOT:-$HOME/.openclaw/workspace/knowledge-lancedb}"
cd "$ROOT"
python3 scripts/gemini_embedding_keychain.py run -- search "$@"
