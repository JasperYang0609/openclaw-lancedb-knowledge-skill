from pathlib import Path


SCRIPT = Path(__file__).parents[1] / (
    "openclaw-lancedb-knowledge/assets/knowledge-lancedb-template/"
    "scripts/knowledge_snapshot_daily.sh"
)


def test_daily_snapshot_wrapper_is_fail_closed_and_verifies_restore():
    text = SCRIPT.read_text()
    assert "OPENCLAW_LANCEDB_SNAPSHOT_ROOT:?" in text
    assert '[[ "$SNAPSHOT_ROOT" != /* ]]' in text
    assert 'mkdir "$LOCK_DIR"' in text
    assert "exit 75" in text
    assert "--restore-canary" in text
    assert "--verify-db" in text
    assert "--expected-row-count" in text
    assert "--retention-days 30" in text
    assert "incremental-manifest.latest.json" in text
    assert "google-gemini" in text
    assert "--reuse-existing" in text
    assert "--stale-fallback-name" in text
    assert "--require-after" in text
    assert "repair-$TODAY-post-index-" in text
