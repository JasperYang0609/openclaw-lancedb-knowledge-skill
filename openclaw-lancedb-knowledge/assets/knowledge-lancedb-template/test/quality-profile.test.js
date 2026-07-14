import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveEmbeddingProfile } from '../src/quality-profile.js';

test('balanced Gemini profile keeps the stable 768-dimensional default', () => {
  const cfg = resolveEmbeddingProfile({ provider: 'google-gemini', model: 'gemini-embedding-001', profile: 'balanced' });
  assert.equal(cfg.dimensions, 768);
  assert.match(cfg.cachePath, /-768\.jsonl$/);
});

test('high-quality Gemini profile opts into 3072 dimensions and a separate cache', () => {
  const cfg = resolveEmbeddingProfile({ provider: 'google-gemini', model: 'gemini-embedding-001', profile: 'high-quality' });
  assert.equal(cfg.dimensions, 3072);
  assert.match(cfg.cachePath, /-3072\.jsonl$/);
});

test('explicit dimensions remain authoritative unless profile requests a migration', () => {
  const cfg = resolveEmbeddingProfile({ provider: 'google-gemini', model: 'gemini-embedding-001', dimensions: 1536 });
  assert.equal(cfg.dimensions, 1536);
  assert.equal(cfg.profile, 'custom');
});

test('high-quality profile retargets an existing dimensional cache instead of mixing vectors', () => {
  const embedding = resolveEmbeddingProfile({
    provider: 'google-gemini',
    model: 'gemini-embedding-001',
    profile: 'high-quality',
    dimensions: 768,
    cachePath: './data/embedding-cache/google-gemini-embedding-001-768.jsonl'
  });
  assert.equal(embedding.dimensions, 3072);
  assert.equal(embedding.cachePath, './data/embedding-cache/google-gemini-embedding-001-3072.jsonl');
});

test('unknown profiles fail closed', () => {
  assert.throws(() => resolveEmbeddingProfile({ provider: 'google-gemini', profile: 'maximum-ish' }), /Unknown embedding profile/);
});
