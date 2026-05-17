import test from 'node:test';
import assert from 'node:assert/strict';
import { redactSecrets } from '../src/security.js';
import { embedLocalHash } from '../src/embed-local.js';

test('redacts common secret-like tokens before embedding/indexing', () => {
  const notionLike = 'ntn_' + 'abcdefghijklmnopqrstuvwxyz123456';
  const openaiLike = 'sk-' + 'proj-' + 'abcdefghijklmnopqrstuvwxyz123456';
  const input = `Token: ${notionLike} and key ${openaiLike}`;
  const out = redactSecrets(input);
  assert.match(out.text, /REDACTED/);
  assert.ok(out.hits.reduce((a, h) => a + h.count, 0) >= 2);
  assert.doesNotMatch(out.text, /sk-proj-/);
  assert.doesNotMatch(out.text, /ntn_/);
});

test('local hash embedding has stable normalized dimension', () => {
  const v1 = embedLocalHash('VASO 文件中心 簽收', 384);
  const v2 = embedLocalHash('VASO 文件中心 簽收', 384);
  assert.equal(v1.length, 384);
  assert.deepEqual(v1, v2);
  const norm = Math.sqrt(v1.reduce((a, b) => a + b * b, 0));
  assert.ok(Math.abs(norm - 1) < 1e-9);
});
