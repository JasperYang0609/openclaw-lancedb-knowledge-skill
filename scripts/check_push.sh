#!/bin/sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$repo_root"

python3 -m py_compile \
  openclaw-lancedb-knowledge/scripts/bootstrap_openclaw_lancedb.py \
  openclaw-lancedb-knowledge/assets/knowledge-lancedb-template/scripts/snapshot_knowledge_assets.py \
  scripts/check_dangerous_exec.py \
  scripts/build_skill_archive.py \
  tests/test_ci_workflow_contract.py

(
  cd openclaw-lancedb-knowledge/assets/knowledge-lancedb-template
  npm ci --ignore-scripts
  npm test
  npm run postrun:check
)

python3 scripts/check_dangerous_exec.py
python3 tests/test_skill_archive.py
python3 scripts/build_skill_archive.py --check
python3 tests/test_ci_workflow_contract.py
