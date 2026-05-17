#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import * as lancedb from '@lancedb/lancedb';
import { loadConfig, buildChunks } from './sources.js';
import { embedLocalHash } from './embed-local.js';
import { getEmbedder } from './embed-google.js';

function arg(name, fallback = undefined) {
  const idx = process.argv.indexOf(`--${name}`);
  if (idx >= 0 && idx + 1 < process.argv.length) return process.argv[idx + 1];
  return fallback;
}
function flag(name) { return process.argv.includes(`--${name}`); }
function ensureDir(p) { fs.mkdirSync(p, { recursive: true }); }
function nowStamp() { return new Date().toISOString().replace(/[:.]/g, '-'); }

function statePath() { return path.resolve('data/index-state.json'); }
function loadIndexState() {
  const p = statePath();
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}
function writeIndexState(config, built, extra = {}) {
  ensureDir(path.dirname(statePath()));
  const files = {};
  for (const c of built.chunks) {
    if (!files[c.source_path]) {
      files[c.source_path] = {
        source_path: c.source_path,
        rel_path: c.rel_path,
        source_id: c.source_id,
        source_type: c.source_type,
        project: c.project,
        channel: c.channel,
        file_sha256: c.file_sha256,
        file_mtime_ms: c.file_mtime_ms,
        file_bytes: c.file_bytes,
        chunk_ids: [],
        chunks: 0
      };
    }
    files[c.source_path].chunk_ids.push(c.id);
    files[c.source_path].chunks += 1;
  }
  const state = {
    version: 1,
    updatedAt: new Date().toISOString(),
    tableName: config.tableName || 'knowledge_chunks',
    dbPath: path.resolve(config.dbPath || './data/lancedb'),
    embedding: config.embedding,
    docs: built.docs.length,
    chunks: built.chunks.length,
    files,
    ...extra
  };
  fs.writeFileSync(statePath(), JSON.stringify(state, null, 2));
  return state;
}
function groupChunksByPath(chunks) {
  const map = new Map();
  for (const c of chunks) {
    if (!map.has(c.source_path)) map.set(c.source_path, []);
    map.get(c.source_path).push(c);
  }
  return map;
}
function sqlString(s) { return String(s).replaceAll("'", "''"); }
async function deleteSourcePaths(table, paths) {
  const list = [...paths];
  const chunkSize = 25;
  for (let i = 0; i < list.length; i += chunkSize) {
    const pred = list.slice(i, i + chunkSize).map((p) => `source_path = '${sqlString(p)}'`).join(' OR ');
    if (pred) await table.delete(pred);
  }
}
async function rowsForChunks(config, chunks) {
  const dims = config.embedding?.dimensions || 384;
  let vectors;
  let embeddingProvider = config.embedding?.provider || 'local-hash-v1';
  if (embeddingProvider === 'google-gemini') {
    const embedder = getEmbedder(config.embedding);
    vectors = await embedder.embedDocuments(
      chunks.map((c) => `${c.project}
${c.title}
${c.heading}
${c.chunk_text}`),
      (p) => {
        if (p.phase === 'cache') console.error(`[embedding] cache hit ${p.cached}/${p.total}; remote ${p.missing}`);
        if (p.phase === 'remote') console.error(`[embedding] remote embedded ${p.done}/${p.total} (+${p.batchSize})`);
      }
    );
  } else {
    embeddingProvider = 'local-hash-v1';
    vectors = chunks.map((c) => embedLocalHash(`${c.project}
${c.title}
${c.heading}
${c.chunk_text}`, dims));
  }
  return chunks.map((c, i) => ({
    ...c,
    embedding_provider: embeddingProvider,
    embedding_model: config.embedding?.model || embeddingProvider,
    embedding_dimensions: dims,
    vector: vectors[i]
  }));
}


async function openDb(config) {
  const dbPath = path.resolve(config.dbPath || './data/lancedb');
  ensureDir(dbPath);
  return lancedb.connect(dbPath);
}

async function commandScan(config) {
  const built = buildChunks(config);
  ensureDir('reports');
  const byProject = {};
  for (const c of built.chunks) byProject[c.project] = (byProject[c.project] || 0) + 1;
  const report = {
    generatedAt: new Date().toISOString(),
    embedding: config.embedding,
    docs: built.docs.length,
    chunks: built.chunks.length,
    skipped: built.skipped,
    secretHits: built.secretHits,
    byProject
  };
  fs.writeFileSync('reports/source-scan.latest.json', JSON.stringify(report, null, 2));
  fs.writeFileSync(`reports/source-scan.${nowStamp()}.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}

async function commandIndex(config) {
  const limit = Number(arg('limit', '0')) || 0;
  const projectFilter = arg('project', '');
  const built = buildChunks(config);
  let chunks = built.chunks;
  if (projectFilter) chunks = chunks.filter((c) => c.project.toLowerCase() === projectFilter.toLowerCase());
  if (limit > 0) chunks = chunks.slice(0, limit);
  if (chunks.length === 0) throw new Error('No chunks to index');

  const rows = await rowsForChunks(config, chunks);

  const db = await openDb(config);
  const tableName = config.tableName || 'knowledge_chunks';
  const mode = flag('append') ? 'append' : 'overwrite';
  if (mode === 'overwrite') {
    await db.createTable(tableName, rows, { mode: 'overwrite' });
  } else {
    let table;
    try { table = await db.openTable(tableName); }
    catch { table = await db.createTable(tableName, rows.slice(0, 1), { mode: 'overwrite' }); rows.shift(); }
    if (rows.length) await table.add(rows);
  }

  ensureDir('reports');
  const manifest = {
    indexedAt: new Date().toISOString(),
    mode,
    tableName,
    dbPath: path.resolve(config.dbPath || './data/lancedb'),
    embedding: config.embedding,
    docs: built.docs.length,
    chunksIndexed: rows.length,
    chunksAvailable: built.chunks.length,
    projectFilter: projectFilter || null,
    limit: limit || null,
    skipped: built.skipped.length,
    secretHitFiles: built.secretHits.length
  };
  fs.writeFileSync('reports/index-manifest.latest.json', JSON.stringify(manifest, null, 2));
  fs.writeFileSync(`reports/index-manifest.${nowStamp()}.json`, JSON.stringify(manifest, null, 2));
  writeIndexState(config, { ...built, chunks }, { lastIndexMode: mode });
  console.log(JSON.stringify(manifest, null, 2));
}


async function commandSyncState(config) {
  const built = buildChunks(config);
  const state = writeIndexState(config, built, { syncedFromCurrentSourcesOnly: true });
  console.log(JSON.stringify({ ok: true, statePath: statePath(), docs: state.docs, chunks: state.chunks, files: Object.keys(state.files).length }, null, 2));
}

async function commandIncremental(config) {
  const built = buildChunks(config);
  const state = loadIndexState();
  const db = await openDb(config);
  const tableName = config.tableName || 'knowledge_chunks';
  let table;
  try { table = await db.openTable(tableName); }
  catch {
    console.error('[incremental] table missing; falling back to full index');
    return commandIndex(config);
  }

  if (!state || !state.files) {
    console.error('[incremental] state missing; falling back to one-time full index to establish baseline');
    return commandIndex(config);
  }

  const currentByPath = groupChunksByPath(built.chunks);
  const currentPaths = new Set(currentByPath.keys());
  const previousPaths = new Set(Object.keys(state.files));
  const removedPaths = [...previousPaths].filter((p) => !currentPaths.has(p));
  const changedPaths = [];
  for (const [p, chunks] of currentByPath) {
    const prev = state.files[p];
    const sha = chunks[0]?.file_sha256;
    const prevEmbedding = JSON.stringify(state.embedding || {});
    const currentEmbedding = JSON.stringify(config.embedding || {});
    if (!prev || prev.file_sha256 !== sha || prevEmbedding !== currentEmbedding) changedPaths.push(p);
  }

  const changedChunks = changedPaths.flatMap((p) => currentByPath.get(p) || []);
  const deletePaths = [...new Set([...removedPaths, ...changedPaths])];
  if (deletePaths.length) await deleteSourcePaths(table, deletePaths);
  let rows = [];
  if (changedChunks.length) {
    rows = await rowsForChunks(config, changedChunks);
    if (rows.length) await table.add(rows);
  }

  const newState = writeIndexState(config, built, { lastIndexMode: 'incremental' });
  let rowCount = null;
  try { rowCount = await table.countRows(); } catch {}
  const report = {
    mode: 'incremental',
    indexedAt: new Date().toISOString(),
    tableName,
    dbPath: path.resolve(config.dbPath || './data/lancedb'),
    embedding: config.embedding,
    docs: built.docs.length,
    chunksAvailable: built.chunks.length,
    files: Object.keys(newState.files).length,
    changedFiles: changedPaths.length,
    removedFiles: removedPaths.length,
    changedChunks: changedChunks.length,
    addedChunks: rows.length,
    deletedPaths: deletePaths.length,
    rowsAfter: rowCount,
    skipped: built.skipped.length,
    secretHitFiles: built.secretHits.length
  };
  ensureDir('reports');
  fs.writeFileSync('reports/incremental-manifest.latest.json', JSON.stringify(report, null, 2));
  fs.writeFileSync(`reports/incremental-manifest.${nowStamp()}.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}

async function commandStatus(config) {
  const db = await openDb(config);
  const tableName = config.tableName || 'knowledge_chunks';
  let count = 0;
  let ok = false;
  try {
    const table = await db.openTable(tableName);
    count = await table.countRows();
    ok = true;
  } catch {}
  const manifestPath = 'reports/index-manifest.latest.json';
  const manifest = fs.existsSync(manifestPath) ? JSON.parse(fs.readFileSync(manifestPath, 'utf8')) : null;
  console.log(JSON.stringify({ ok, tableName, rows: count, manifest }, null, 2));
}


function rankTerms(text) {
  const t = String(text || '').toLowerCase();
  const terms = new Set();
  for (const m of t.matchAll(/[a-z0-9_\-]{2,}/g)) terms.add(m[0]);
  const cjk = Array.from(t.match(/[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/gu) || []);
  for (let i = 0; i < cjk.length; i++) {
    terms.add(cjk[i]);
    if (i + 1 < cjk.length) terms.add(cjk[i] + cjk[i + 1]);
    if (i + 2 < cjk.length) terms.add(cjk[i] + cjk[i + 1] + cjk[i + 2]);
  }
  return [...terms].filter((x) => x.length > 1 || /[\p{Script=Han}]/u.test(x));
}

function isProgressQuery(query) {
  return /(現在|目前|做到哪|進度|狀態|最新|handoff|current|progress|status|next)/i.test(query);
}

function dateScore(date) {
  if (!date) return 0;
  const ts = Date.parse(date);
  if (!Number.isFinite(ts)) return 0;
  const days = Math.max(0, (Date.now() - ts) / 86400000);
  return Math.max(0, 1 - days / 120); // recent four months matter most for project state
}

function sourceProgressBoost(row) {
  const s = `${row.source_path || ''} ${row.title || ''} ${row.heading || ''}`.toLowerCase();
  let b = 0;
  if (/current_handoff|handoff|開發狀況|development_log|development_roadmap|development_schedule|project_/.test(s)) b += 0.25;
  if (/summary/.test(row.source_type || '')) b += 0.05;
  return b;
}

function rerankRows(rows, query) {
  const qTerms = rankTerms(query);
  const progress = isProgressQuery(query);
  return rows.map((r) => {
    const hay = `${r.project} ${r.title} ${r.heading} ${r.rel_path} ${r.chunk_text}`.toLowerCase();
    const overlap = qTerms.length ? qTerms.filter((t) => hay.includes(t.toLowerCase())).length / qTerms.length : 0;
    const vector = typeof r._distance === 'number' ? 1 / (1 + r._distance) : 0;
    const recency = progress ? dateScore(r.date) : 0;
    const progressBoost = progress ? sourceProgressBoost(r) : 0;
    const score = vector * 0.58 + overlap * 0.28 + recency * 0.09 + progressBoost;
    return { ...r, _rank_score: score, _keyword_overlap: overlap, _recency_score: recency };
  }).sort((a, b) => b._rank_score - a._rank_score);
}

function escapeSqlString(s) { return s.replaceAll("'", "''"); }

async function commandSearch(config) {
  const queryParts = process.argv.slice(3).filter((x, i, arr) => !arr[i - 1]?.startsWith('--') && !x.startsWith('--'));
  const query = queryParts.join(' ').trim() || arg('query', '');
  if (!query) throw new Error('Usage: npm run search -- "query" [-- --project BeanGo --limit 5]');
  const limit = Number(arg('limit', '5')) || 5;
  const project = arg('project', '');
  const dims = config.embedding?.dimensions || 384;
  let queryVector;
  const embeddingProvider = config.embedding?.provider || 'local-hash-v1';
  if (embeddingProvider === 'google-gemini') {
    const embedder = getEmbedder(config.embedding);
    queryVector = await embedder.embedOne(query, config.embedding?.queryTaskType || 'RETRIEVAL_QUERY');
  } else {
    queryVector = embedLocalHash(query, dims);
  }
  const db = await openDb(config);
  const table = await db.openTable(config.tableName || 'knowledge_chunks');
  let search = table.search(queryVector);
  if (project) search = search.where(`project = '${escapeSqlString(project)}'`);
  const fetchLimit = Math.max(limit * 20, 80);
  const rows = rerankRows(await search.limit(fetchLimit).toArray(), query).slice(0, limit);
  console.log(`# Search: ${query}\n`);
  if (project) console.log(`Project filter: ${project}\n`);
  rows.forEach((r, idx) => {
    const distance = typeof r._distance === 'number' ? r._distance.toFixed(4) : 'n/a';
    const rank = typeof r._rank_score === 'number' ? r._rank_score.toFixed(4) : 'n/a';
    console.log(`## ${idx + 1}. ${r.project} / ${r.title} / ${r.heading}`);
    console.log(`- rank: ${rank}`);
    console.log(`- distance: ${distance}`);
    console.log(`- source: ${r.source_path}`);
    if (r.date) console.log(`- date: ${r.date}`);
    if (r.channel) console.log(`- channel: ${r.channel}`);
    const snippet = String(r.chunk_text || '').replace(/\s+/g, ' ').slice(0, 700);
    console.log(`- snippet: ${snippet}${snippet.length >= 700 ? '…' : ''}\n`);
  });
}

async function main() {
  const cmd = process.argv[2] || 'help';
  const config = loadConfig();
  if (cmd === 'scan') return commandScan(config);
  if (cmd === 'index') return commandIndex(config);
  if (cmd === 'incremental') return commandIncremental(config);
  if (cmd === 'sync-state') return commandSyncState(config);
  if (cmd === 'status') return commandStatus(config);
  if (cmd === 'search') return commandSearch(config);
  console.log(`knowledge-lancedb commands:\n  scan\n  index [--limit N] [--project NAME] [--append]\n  search "query" [--project NAME] [--limit N]\n  status`);
}

main().catch((err) => {
  console.error(err.stack || String(err));
  process.exit(1);
});
