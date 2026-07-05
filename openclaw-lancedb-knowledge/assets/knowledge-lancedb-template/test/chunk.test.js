import test from 'node:test';
import assert from 'node:assert/strict';
import { chunkMarkdown } from '../src/chunk.js';
import { l2Normalize } from '../src/embed-google.js';

const content = '# 標題\n\n' + '內容'.repeat(60);

test('chunkMarkdown respects source.project when provided', () => {
  const chunks = chunkMarkdown({
    source: { id: 's1', project: 'AnsaiBrand', sourceType: 'project_doc' },
    absPath: '/Users/x/.openclaw/workspace/memory/project_ansai_brand.md',
    relPath: 'project_ansai_brand.md',
    content
  });
  assert.ok(chunks.length > 0);
  assert.equal(chunks[0].project, 'AnsaiBrand');
});

test('heuristic uses relPath only and word-bounded ig', () => {
  // absPath containing .openclaw segments must not affect inference; config/insight must not
  // match IGResearch.
  const chunks = chunkMarkdown({
    source: { id: 's2', sourceType: 'project_doc' },
    absPath: '/Users/x/.openclaw/workspace/config/insight.md',
    relPath: 'config/insight.md',
    content
  });
  assert.ok(chunks.length > 0);
  assert.equal(chunks[0].project, 'General');
});

test('brand heuristic is reachable before ops fallback', () => {
  const chunks = chunkMarkdown({
    source: { id: 's3', sourceType: 'project_doc' },
    absPath: '/Users/x/docs/品牌backup筆記.md',
    relPath: '品牌backup筆記.md',
    content
  });
  assert.equal(chunks[0].project, 'AnsaiBrand');
});

test('l2Normalize returns unit vectors and guards zero vectors', () => {
  const v = l2Normalize([3, 4]);
  assert.ok(Math.abs(Math.sqrt(v[0] * v[0] + v[1] * v[1]) - 1) < 1e-12);
  assert.deepEqual(l2Normalize([0, 0, 0]), [0, 0, 0]);
});
