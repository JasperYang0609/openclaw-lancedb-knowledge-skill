#!/usr/bin/env bash
set -euo pipefail
ROOT="${OPENCLAW_LANCEDB_ROOT:-$HOME/.openclaw/workspace/knowledge-lancedb}"
LOG_DIR="$ROOT/reports/cron-logs"
LOCK_DIR="$ROOT/data/index.lock"
mkdir -p "$LOG_DIR" "$ROOT/data"
STAMP="$(TZ=${TZ:-Asia/Taipei} date +%Y%m%d-%H%M%S)"
LOG="$LOG_DIR/incremental-$STAMP.log"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "[knowledge-index] another indexing run is active; skip" | tee "$LOG"
  exit 0
fi
cleanup() { rmdir "$LOCK_DIR" 2>/dev/null || true; }
trap cleanup EXIT
cd "$ROOT"
{
  echo "[knowledge-index] started_at=$(date +%Y-%m-%dT%H:%M:%S%z)"
  npm run incremental
  echo "[knowledge-index] finished_at=$(date +%Y-%m-%dT%H:%M:%S%z)"
} 2>&1 | tee "$LOG"
