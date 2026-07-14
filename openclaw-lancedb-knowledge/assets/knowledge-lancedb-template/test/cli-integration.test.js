import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import * as lancedb from '@lancedb/lancedb';

const cli = path.resolve('src/cli.js');

function run(cwd, args) {
  const result = spawnSync(process.execPath, [cli, ...args], { cwd, encoding: 'utf8' });
  assert.equal(result.status, 0, `${args.join(' ')} failed:\n${result.stderr}\n${result.stdout}`);
  return result.stdout;
}

test('CLI indexes deterministic metadata, validates optional enrichment, and passes a 20-case benchmark', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'knowledge-cli-integration-'));
  const docs = path.join(root, 'docs');
  fs.mkdirSync(path.join(root, 'config'), { recursive: true });
  fs.mkdirSync(docs, { recursive: true });
  fs.writeFileSync(path.join(docs, 'decision.md'), '# Release decision\n\nDecision: use the stable launch plan. Action: run release verification.');
  fs.writeFileSync(path.join(docs, 'risk.md'), '# Security risk\n\nRisk: credential exposure. Procedure: rotate tokens and verify audit logs.');
  fs.writeFileSync(path.join(docs, 'status.md'), '# Current status\n\nStatus: migration complete. Next step: monitor production.');
  const config = {
    version: 1,
    dbPath: './data/lancedb',
    tableName: 'knowledge_chunks',
    embedding: { provider: 'local-hash-v1', model: 'local-hash-v1', dimensions: 64 },
    chunking: { maxChars: 500, overlapChars: 0 },
    enrichment: { enabled: false, inputPath: './data/enrichment/validated.jsonl', minConfidence: 0.75 },
    sources: [{ id: 'fixture', project: 'FixtureProject', sourceType: 'project_doc', root: docs, include: ['**/*.md'], exclude: [] }]
  };
  fs.writeFileSync(path.join(root, 'config/source-map.json'), JSON.stringify(config, null, 2));

  run(root, ['index']);
  const status = JSON.parse(run(root, ['status']));
  assert.equal(status.ok, true);
  assert.equal(status.rows, 3);

  const enrichmentInput = path.join(root, 'data/enrichment/input.jsonl');
  run(root, ['prepare-enrichment', '--output', enrichmentInput]);
  const prepared = fs.readFileSync(enrichmentInput, 'utf8').split(/\r?\n/).filter(Boolean).map(JSON.parse);
  assert.equal(prepared.length, 3);
  const decision = prepared.find((row) => row.authoritative.title === 'Release decision');
  assert.ok(decision);

  const modelOutput = path.join(root, 'data/enrichment/model-output.jsonl');
  fs.writeFileSync(modelOutput, JSON.stringify({
    id: decision.id,
    doc_type: 'decision',
    tags: ['release', 'verification'],
    importance: 4,
    summary: 'Use the stable launch plan and verify the release.',
    decisions: ['Use the stable launch plan.'],
    risks: [],
    action_items: ['Run release verification.'],
    confidence: 0.9,
    model: 'fixture-model',
    schema_version: 1
  }) + '\n');
  const validated = path.join(root, 'data/enrichment/validated.jsonl');
  run(root, ['validate-enrichment', '--input', modelOutput, '--output', validated]);
  config.enrichment.enabled = true;
  config.enrichment.inputPath = validated;
  config.enrichment.privacyApprovedAt = '2026-07-14T00:00:00Z';
  config.enrichment.privacyApprovedBy = 'integration test fixture';
  fs.writeFileSync(path.join(root, 'config/source-map.json'), JSON.stringify(config, null, 2));
  run(root, ['index']);

  const db = await lancedb.connect(path.join(root, 'data/lancedb'));
  const table = await db.openTable('knowledge_chunks');
  const rows = await table.query().toArray();
  const enriched = rows.find((row) => row.id === decision.id);
  assert.equal(enriched.project, 'FixtureProject');
  assert.equal(enriched.deterministic_doc_type, 'decision');
  assert.equal(enriched.ai_enrichment_status, 'valid');
  assert.equal(enriched.ai_doc_type, 'decision');
  assert.equal(rows.filter((row) => row.ai_enrichment_status === 'missing').length, 2);

  const benchmark = {
    k: 3,
    minHitRate: 1,
    minMrr: 1,
    cases: Array.from({ length: 20 }, (_, i) => ({
      id: `release-${i + 1}`,
      query: 'stable launch plan release verification decision',
      expected: { project: 'FixtureProject', sourcePathIncludes: 'decision.md' }
    }))
  };
  const benchmarkPath = path.join(root, 'config/benchmark.json');
  fs.writeFileSync(benchmarkPath, JSON.stringify(benchmark, null, 2));
  run(root, ['benchmark', '--file', benchmarkPath, '--release-gate']);
  const report = JSON.parse(fs.readFileSync(path.join(root, 'reports/benchmark.latest.json'), 'utf8'));
  assert.equal(report.passed, true);
  assert.equal(report.total, 20);
  assert.equal(report.hitRate, 1);
});
