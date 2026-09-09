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
MANIFEST_FIELDS="$(node -e '
const fs = require("fs");
const row = JSON.parse(fs.readFileSync("reports/incremental-manifest.latest.json", "utf8"));
const indexedAt = row.indexedAt;
const rows = row.rowsAfter;
const chunks = row.chunksAvailable;
const embedding = row.embedding || {};
if (row.mode !== "incremental" || embedding.provider !== "google-gemini" || embedding.model !== "gemini-embedding-001") process.exit(2);
if (typeof indexedAt !== "string" || !Number.isFinite(Date.parse(indexedAt)) || !/(Z|[+-][0-9]{2}:[0-9]{2})$/.test(indexedAt)) process.exit(3);
if (!Number.isInteger(rows) || rows < 1 || chunks !== rows) process.exit(4);
const stamp = new Date(indexedAt).toISOString().replace(/[-:.]/g, "").replace("000Z", "Z");
process.stdout.write([indexedAt, String(rows), stamp].join("\t"));
')"
IFS=$'\t' read -r INDEXED_AT MANIFEST_ROWS SNAPSHOT_STAMP <<< "$MANIFEST_FIELDS"
if [[ "$MANIFEST_ROWS" != "$ROW_COUNT" ]]; then
  echo "[knowledge-snapshot] Gemini manifest and live index row counts differ" >&2
  exit 65
fi

TODAY="$(TZ="$TIMEZONE" date +%F)"
SNAPSHOT_OVERRIDE="${OPENCLAW_LANCEDB_SNAPSHOT_NAME:-}"
FALLBACK_ARGS=()
if [[ -n "$SNAPSHOT_OVERRIDE" ]]; then
  if [[ ! "$SNAPSHOT_OVERRIDE" =~ ^(repair|incident)-[0-9]{4}-[0-9]{2}-[0-9]{2}(-[A-Za-z0-9._-]+)?$ ]]; then
    echo "[knowledge-snapshot] manual snapshot names must use repair-* or incident-*" >&2
    exit 64
  fi
  SNAPSHOT_NAME="$SNAPSHOT_OVERRIDE"
else
  SNAPSHOT_NAME="daily-$TODAY"
  FALLBACK_ARGS=(--stale-fallback-name "repair-$TODAY-post-index-$SNAPSHOT_STAMP")
fi

python3 scripts/snapshot_knowledge_assets.py \
  --backup-root "$SNAPSHOT_ROOT" \
  --snapshot-name "$SNAPSHOT_NAME" \
  --reuse-existing \
  "${FALLBACK_ARGS[@]}" \
  --require-after "$INDEXED_AT" \
  --restore-canary \
  --verify-db \
  --table-name knowledge_chunks \
  --expected-row-count "$ROW_COUNT" \
  --retention-days 30 \
  --retention-reference-date "$TODAY" \
  --transient-retention-days 14 \
  --transient-max-count 8
