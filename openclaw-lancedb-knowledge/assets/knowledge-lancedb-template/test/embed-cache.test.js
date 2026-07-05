import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { cacheKey, compactEmbeddingCache } from '../src/embed-google.js';

const MODEL = 'gemini-embedding-001';
const DIMS = 8;

function makeRow({ text, taskType, model = MODEL, dimensions = DIMS }) {
  const key = cacheKey({ text, model, dimensions, taskType });
  return { key, row: { key, vector: [1, 2, 3], model, dimensions, taskType, cachedAt: '2026-07-06T00:00:00.000Z' } };
}

test('compactEmbeddingCache keeps query rows via keepQueryMeta and drops stale ones', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'embed-cache-test-'));
  const cachePath = path.join(dir, 'cache.jsonl');

  const docKeep = makeRow({ text: 'doc-still-indexed', taskType: 'RETRIEVAL_DOCUMENT' });
  const docStale = makeRow({ text: 'doc-removed', taskType: 'RETRIEVAL_DOCUMENT' });
  const queryCurrent = makeRow({ text: 'some user query', taskType: 'RETRIEVAL_QUERY' });
  const queryOldModel = makeRow({ text: 'old model query', taskType: 'RETRIEVAL_QUERY', model: 'old-model' });
  const queryOldDims = makeRow({ text: 'old dims query', taskType: 'RETRIEVAL_QUERY', dimensions: 4 });

  fs.writeFileSync(
    cachePath,
    [docKeep, docStale, queryCurrent, queryOldModel, queryOldDims].map((r) => JSON.stringify(r.row) + '\n').join('')
  );

  const result = compactEmbeddingCache({
    cachePath,
    keepKeys: new Set([docKeep.key]),
    keepQueryMeta: { taskType: 'RETRIEVAL_QUERY', model: MODEL, dimensions: DIMS }
  });
  assert.equal(result.before, 5);
  assert.equal(result.kept, 2);
  assert.equal(result.keptQueryRows, 1);
  assert.equal(result.removed, 3);

  const keys = fs.readFileSync(cachePath, 'utf8').split(/\r?\n/).filter(Boolean).map((l) => JSON.parse(l).key);
  // Document rows still indexed and query rows matching the current model/dimensions are kept;
  // everything else (including old-model/old-dims query rows) is removed.
  assert.deepEqual(new Set(keys), new Set([docKeep.key, queryCurrent.key]));
});

test('compactEmbeddingCache without keepQueryMeta keeps only keepKeys', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'embed-cache-test-'));
  const cachePath = path.join(dir, 'cache.jsonl');

  const docKeep = makeRow({ text: 'doc-still-indexed', taskType: 'RETRIEVAL_DOCUMENT' });
  const queryRow = makeRow({ text: 'some user query', taskType: 'RETRIEVAL_QUERY' });
  fs.writeFileSync(cachePath, [docKeep, queryRow].map((r) => JSON.stringify(r.row) + '\n').join(''));

  const result = compactEmbeddingCache({ cachePath, keepKeys: new Set([docKeep.key]) });
  assert.equal(result.kept, 1);
  assert.equal(result.keptQueryRows, 0);

  const keys = fs.readFileSync(cachePath, 'utf8').split(/\r?\n/).filter(Boolean).map((l) => JSON.parse(l).key);
  assert.deepEqual(keys, [docKeep.key]);
});
