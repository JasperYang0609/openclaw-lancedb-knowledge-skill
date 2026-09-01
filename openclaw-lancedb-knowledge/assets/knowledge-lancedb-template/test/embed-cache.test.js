import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  cacheKey,
  compactEmbeddingCache,
  GoogleGeminiEmbedder,
  validateEmbeddingVector
} from '../src/embed-google.js';

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

test('Gemini cache rejects non-numeric vectors even when the cache key is valid', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'embed-cache-invalid-test-'));
  const cachePath = path.join(dir, 'cache.jsonl');
  const text = 'cached fixture';
  const key = cacheKey({ text, model: MODEL, dimensions: DIMS, taskType: 'RETRIEVAL_QUERY' });
  fs.writeFileSync(cachePath, JSON.stringify({
    key,
    vector: Array(DIMS).fill('1'),
    model: MODEL,
    dimensions: DIMS,
    taskType: 'RETRIEVAL_QUERY'
  }) + '\n');
  const previousKey = process.env.GOOGLE_API_KEY;
  process.env.GOOGLE_API_KEY = 'test-only-dummy-key';
  try {
    const embedder = new GoogleGeminiEmbedder({ model: MODEL, dimensions: DIMS, cachePath });
    await assert.rejects(embedder.embedOne(text), /finite numeric values/);
  } finally {
    if (previousKey === undefined) delete process.env.GOOGLE_API_KEY;
    else process.env.GOOGLE_API_KEY = previousKey;
  }
});

test('Gemini API key is sent in a header, never in the request URL', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'embed-header-test-'));
  const previousKey = process.env.GOOGLE_API_KEY;
  const previousFetch = globalThis.fetch;
  process.env.GOOGLE_API_KEY = 'test-only-header-key';
  globalThis.fetch = async (url, options) => {
    assert.doesNotMatch(String(url), /key=/i);
    assert.equal(options.headers['x-goog-api-key'], 'test-only-header-key');
    return { ok: true, text: async () => JSON.stringify({ embedding: { values: [3, 4] } }) };
  };
  try {
    const embedder = new GoogleGeminiEmbedder({
      model: MODEL,
      dimensions: 2,
      cachePath: path.join(dir, 'cache.jsonl')
    });
    assert.deepEqual(await embedder.embedOne('header fixture'), [0.6, 0.8]);
  } finally {
    globalThis.fetch = previousFetch;
    if (previousKey === undefined) delete process.env.GOOGLE_API_KEY;
    else process.env.GOOGLE_API_KEY = previousKey;
  }
});

test('embedding vector validation rejects zero, non-finite, and wrong-sized vectors', () => {
  assert.throws(() => validateEmbeddingVector([0, 0], 2), /non-zero norm/);
  assert.throws(() => validateEmbeddingVector([1, Number.NaN], 2), /finite numeric/);
  assert.throws(() => validateEmbeddingVector([1], 2), /dimension mismatch/);
});
