import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { walkFiles, matchAny } from './glob-lite.js';
import { looksBinary, redactSecrets } from './security.js';
import { chunkMarkdown } from './chunk.js';

export function loadConfig() {
  const cfgPath = path.resolve('config/source-map.json');
  return JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
}

function fileSha256(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

export function collectFiles(config) {
  const docs = [];
  const seen = new Set();
  const skipped = [];
  for (const source of config.sources) {
    const root = source.root;
    const files = walkFiles(root);
    for (const absPath of files) {
      const rel = path.relative(root, absPath).split(path.sep).join('/');
      if (!matchAny(rel, source.include || ['**/*.md'])) continue;
      if (matchAny(rel, source.exclude || [])) continue;
      if (!absPath.toLowerCase().endsWith('.md')) continue;
      if (seen.has(absPath)) continue;
      seen.add(absPath);
      let st;
      try { st = fs.statSync(absPath); } catch { continue; }
      if (st.size > (config.maxFileBytes || 1_200_000)) {
        skipped.push({ source: source.id, path: absPath, reason: 'file_too_large', bytes: st.size });
        continue;
      }
      let buf;
      try { buf = fs.readFileSync(absPath); } catch { continue; }
      if (looksBinary(buf)) {
        skipped.push({ source: source.id, path: absPath, reason: 'binary' });
        continue;
      }
      docs.push({ source, absPath, relPath: rel, bytes: st.size, mtimeMs: st.mtimeMs, fileSha256: fileSha256(buf), raw: buf.toString('utf8') });
    }
  }
  return { docs, skipped };
}

export function buildChunks(config) {
  const { docs, skipped } = collectFiles(config);
  const chunks = [];
  const secretHits = [];
  for (const doc of docs) {
    const red = redactSecrets(doc.raw);
    if (red.hits.length) secretHits.push({ path: doc.absPath, hits: red.hits });
    const docChunks = chunkMarkdown({ ...doc, content: red.text });
    for (const c of docChunks) {
      chunks.push({
        ...c,
        file_sha256: doc.fileSha256,
        file_mtime_ms: doc.mtimeMs,
        file_bytes: doc.bytes,
        secret_redactions: red.hits.reduce((a, h) => a + h.count, 0)
      });
    }
  }
  return { docs, chunks, skipped, secretHits };
}
