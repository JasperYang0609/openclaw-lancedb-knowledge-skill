import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }
function ensureDir(p) { fs.mkdirSync(p, { recursive: true }); }
function sha256(text) { return crypto.createHash('sha256').update(text).digest('hex'); }

export function resolveGoogleApiKey() {
  if (process.env.GOOGLE_API_KEY) return process.env.GOOGLE_API_KEY;
  if (process.env.GEMINI_API_KEY) return process.env.GEMINI_API_KEY;
  const candidates = [
    process.env.OPENCLAW_CONFIG_PATH,
    path.join(process.env.HOME || '', '.openclaw', 'openclaw.json'),
    path.join(process.env.HOME || '', '.openclaw', 'config.json')
  ].filter(Boolean);
  for (const cfgPath of candidates) {
    if (!fs.existsSync(cfgPath)) continue;
    try {
      const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
      const key = cfg.models?.providers?.google?.apiKey || cfg.providers?.google?.apiKey;
      if (key) return key;
    } catch {}
  }
  throw new Error('Google API key not found. Set GOOGLE_API_KEY/GEMINI_API_KEY or configure OpenClaw Google provider.');
}

function cacheKey({ text, model, dimensions, taskType }) {
  return sha256(`${model}\n${dimensions}\n${taskType}\n${text}`);
}

export class EmbeddingCache {
  constructor(cachePath) {
    this.cachePath = path.resolve(cachePath || './data/embedding-cache/google-gemini.jsonl');
    this.map = new Map();
    ensureDir(path.dirname(this.cachePath));
    if (fs.existsSync(this.cachePath)) {
      const lines = fs.readFileSync(this.cachePath, 'utf8').split(/\r?\n/).filter(Boolean);
      for (const line of lines) {
        try {
          const row = JSON.parse(line);
          if (row.key && Array.isArray(row.vector)) this.map.set(row.key, row.vector);
        } catch {}
      }
    }
  }
  get(key) { return this.map.get(key); }
  append(key, vector, meta = {}) {
    this.map.set(key, vector);
    fs.appendFileSync(this.cachePath, JSON.stringify({ key, vector, ...meta, cachedAt: new Date().toISOString() }) + '\n');
  }
}

async function postJsonWithRetry(url, body, { maxRetries = 6 } = {}) {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const text = await r.text();
    if (r.ok) return JSON.parse(text);
    let retryAfter = Number(r.headers.get('retry-after') || '0') * 1000;
    const transient = r.status === 429 || r.status >= 500;
    if (!transient || attempt === maxRetries) {
      let msg = text.slice(0, 800);
      msg = msg.replace(/[A-Za-z0-9_-]{30,}/g, '[REDACTED_LONG_TOKEN]');
      throw new Error(`Google embedding failed: HTTP ${r.status}: ${msg}`);
    }
    if (!retryAfter) retryAfter = Math.min(60_000, 1000 * 2 ** attempt) + Math.floor(Math.random() * 500);
    await sleep(retryAfter);
  }
}

export class GoogleGeminiEmbedder {
  constructor(config = {}) {
    this.model = config.model || 'gemini-embedding-001';
    this.dimensions = config.dimensions || 768;
    this.documentTaskType = config.documentTaskType || 'RETRIEVAL_DOCUMENT';
    this.queryTaskType = config.queryTaskType || 'RETRIEVAL_QUERY';
    this.batchSize = config.batchSize || 40;
    this.throttleMs = config.throttleMs ?? 250;
    this.apiKey = resolveGoogleApiKey();
    this.cache = new EmbeddingCache(config.cachePath || './data/embedding-cache/google-gemini.jsonl');
  }

  makeRequest(text, taskType) {
    return {
      model: `models/${this.model}`,
      content: { parts: [{ text }] },
      taskType,
      outputDimensionality: this.dimensions
    };
  }

  async embedOne(text, taskType = this.queryTaskType) {
    const key = cacheKey({ text, model: this.model, dimensions: this.dimensions, taskType });
    const cached = this.cache.get(key);
    if (cached) return cached;
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${this.model}:embedContent?key=${encodeURIComponent(this.apiKey)}`;
    const data = await postJsonWithRetry(url, this.makeRequest(text, taskType));
    const vector = data.embedding?.values;
    if (!Array.isArray(vector) || vector.length !== this.dimensions) throw new Error(`Unexpected embedding dimension: ${vector?.length}`);
    this.cache.append(key, vector, { model: this.model, dimensions: this.dimensions, taskType });
    return vector;
  }

  async embedDocuments(texts, onProgress = () => {}) {
    const taskType = this.documentTaskType;
    const out = new Array(texts.length);
    const missing = [];
    for (let i = 0; i < texts.length; i++) {
      const key = cacheKey({ text: texts[i], model: this.model, dimensions: this.dimensions, taskType });
      const cached = this.cache.get(key);
      if (cached) out[i] = cached;
      else missing.push({ i, key, text: texts[i] });
    }
    onProgress({ phase: 'cache', total: texts.length, cached: texts.length - missing.length, missing: missing.length });
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${this.model}:batchEmbedContents?key=${encodeURIComponent(this.apiKey)}`;
    let done = texts.length - missing.length;
    for (let start = 0; start < missing.length; start += this.batchSize) {
      const batch = missing.slice(start, start + this.batchSize);
      const body = { requests: batch.map((x) => this.makeRequest(x.text, taskType)) };
      const data = await postJsonWithRetry(url, body);
      const embeddings = data.embeddings || [];
      if (embeddings.length !== batch.length) throw new Error(`Batch embedding count mismatch: got ${embeddings.length}, expected ${batch.length}`);
      embeddings.forEach((emb, j) => {
        const vector = emb.values;
        if (!Array.isArray(vector) || vector.length !== this.dimensions) throw new Error(`Unexpected embedding dimension in batch: ${vector?.length}`);
        const item = batch[j];
        out[item.i] = vector;
        this.cache.append(item.key, vector, { model: this.model, dimensions: this.dimensions, taskType });
      });
      done += batch.length;
      onProgress({ phase: 'remote', total: texts.length, done, batchSize: batch.length });
      if (this.throttleMs && start + this.batchSize < missing.length) await sleep(this.throttleMs);
    }
    return out;
  }
}

export function getEmbedder(config = {}) {
  if (config.provider === 'google-gemini') return new GoogleGeminiEmbedder(config);
  throw new Error(`Unsupported production embedder: ${config.provider}`);
}
