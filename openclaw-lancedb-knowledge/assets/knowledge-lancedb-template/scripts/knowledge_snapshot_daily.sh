#!/usr/bin/env bash
set -euo pipefail

ROOT="${OPENCLAW_LANCEDB_ROOT:-${HOME}/.openclaw/workspace/knowledge-lancedb}"
SNAPSHOT_ROOT="${OPENCLAW_LANCEDB_SNAPSHOT_ROOT:?OPENCLAW_LANCEDB_SNAPSHOT_ROOT is required}"
TIMEZONE="${TZ:-Asia/Taipei}"
LOCK_DIR="$ROOT/data/index.lock"

if [[ "$SNAPSHOT_ROOT" != /* ]]; then
  echo "[knowledge-snapshot] snapshot root must be absolute" >&2
  exit 64
fi
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "[knowledge-snapshot] index lock is active; refusing an inconsistent snapshot" >&2
  exit 75
fi
cleanup() { rmdir "$LOCK_DIR" 2>/dev/null || true; }
trap cleanup EXIT

cd "$ROOT"
STATUS_JSON="$(node src/cli.js status)"
ROW_COUNT="$(printf '%s' "$STATUS_JSON" | node -e '
let input = "";
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  const status = JSON.parse(input);
  if (status.ok !== true || !Number.isInteger(status.rows) || status.rows < 1) process.exit(2);
  process.stdout.write(String(status.rows));
});
')"
SNAPSHOT_NAME="daily-$(TZ="$TIMEZONE" date +%F)"

python3 scripts/snapshot_knowledge_assets.py \
  --backup-root "$SNAPSHOT_ROOT" \
  --snapshot-name "$SNAPSHOT_NAME" \
  --restore-canary \
  --verify-db \
  --table-name knowledge_chunks \
  --expected-row-count "$ROW_COUNT" \
  --retention-days 30 \
  --retention-reference-date "$(TZ="$TIMEZONE" date +%F)"
