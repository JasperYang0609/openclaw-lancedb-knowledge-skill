import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import * as lancedb from '@lancedb/lancedb';
import { applyIncrementalReplacement, replaceSourcePathsSafely, sqlString } from '../src/cli.js';

function predicatePaths(predicate) {
  return [...predicate.matchAll(/source_path = '([^']*)'/g)].map((match) => match[1].replaceAll("''", "'"));
}

class FakeTable {
  constructor(rows) {
    this.rows = structuredClone(rows);
    this.queryCalls = 0;
    this.deleteCalls = 0;
    this.addCalls = 0;
    this.failFirstAddPartially = false;
  }
  query() {
    this.queryCalls += 1;
    return {
      where: (predicate) => ({
        toArray: async () => {
          const paths = new Set(predicatePaths(predicate));
          return structuredClone(this.rows.filter((row) => paths.has(row.source_path)));
        }
      })
    };
  }
  async delete(predicate) {
    this.deleteCalls += 1;
    const paths = new Set(predicatePaths(predicate));
    this.rows = this.rows.filter((row) => !paths.has(row.source_path));
  }
  async add(rows) {
    this.addCalls += 1;
    if (this.failFirstAddPartially) {
      this.failFirstAddPartially = false;
      if (rows.length) this.rows.push(structuredClone(rows[0]));
      throw new Error('simulated partial add failure');
    }
    this.rows.push(...structuredClone(rows));
  }
}

test('embedding failure occurs before any table mutation', async () => {
  const table = new FakeTable([{ id: 'old-a', source_path: '/a.md' }]);
  await assert.rejects(
    applyIncrementalReplacement({
      table,
      config: {},
      changedChunks: [{ id: 'new-a', source_path: '/a.md' }],
      deletePaths: ['/a.md'],
      rowsBuilder: async () => { throw new Error('simulated Gemini failure'); }
    }),
    /simulated Gemini failure/
  );
  assert.equal(table.queryCalls, 0);
  assert.equal(table.deleteCalls, 0);
  assert.equal(table.addCalls, 0);
  assert.deepEqual(table.rows, [{ id: 'old-a', source_path: '/a.md' }]);
});

test('partial add failure removes partial rows and restores the previous rows', async () => {
  const original = [
    { id: 'old-a', source_path: '/a.md', vector: [1, 0] },
    { id: 'keep-b', source_path: '/b.md', vector: [0, 1] }
  ];
  const table = new FakeTable(original);
  table.failFirstAddPartially = true;
  await assert.rejects(
    replaceSourcePathsSafely(table, ['/a.md'], [{ id: 'new-a', source_path: '/a.md', vector: [0.5, 0.5] }]),
    /previous rows restored/
  );
  assert.deepEqual(table.rows.sort((a, b) => a.id.localeCompare(b.id)), original.sort((a, b) => a.id.localeCompare(b.id)));
  assert.equal(table.deleteCalls, 2);
  assert.equal(table.addCalls, 2);
});

test('successful replacement changes only targeted paths', async () => {
  const table = new FakeTable([
    { id: 'old-a', source_path: '/a.md' },
    { id: 'removed-c', source_path: '/c.md' },
    { id: 'keep-b', source_path: '/b.md' }
  ]);
  const result = await replaceSourcePathsSafely(
    table,
    ['/a.md', '/c.md'],
    [{ id: 'new-a', source_path: '/a.md' }]
  );
  assert.deepEqual(table.rows.sort((a, b) => a.id.localeCompare(b.id)), [
    { id: 'keep-b', source_path: '/b.md' },
    { id: 'new-a', source_path: '/a.md' }
  ]);
  assert.equal(result.previousRows, 2);
  assert.equal(result.addedRows, 1);
});

test('source path predicates escape SQL quote characters', () => {
  assert.equal(sqlString("/tmp/client's-file.md' OR 1=1 --"), "/tmp/client''s-file.md'' OR 1=1 --");
});

test('replacement rejects rows outside the explicitly targeted paths', async () => {
  const table = new FakeTable([{ id: 'old-a', source_path: '/a.md' }]);
  await assert.rejects(
    replaceSourcePathsSafely(table, ['/a.md'], [{ id: 'other', source_path: '/other.md' }]),
    /explicitly targeted/
  );
  assert.equal(table.queryCalls, 0);
  assert.equal(table.deleteCalls, 0);
  assert.equal(table.addCalls, 0);
});

test('real LanceDB rows are restored after a partial add failure', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'incremental-rollback-lancedb-'));
  const db = await lancedb.connect(root);
  const original = [
    { id: 'old-a', source_path: '/a.md', chunk_text: 'old content', vector: [1, 0] },
    { id: 'keep-b', source_path: '/b.md', chunk_text: 'untouched', vector: [0, 1] }
  ];
  const table = await db.createTable('chunks', original);
  let failFirstAdd = true;
  const flakyTable = {
    query: () => table.query(),
    delete: (predicate) => table.delete(predicate),
    add: async (rows) => {
      if (failFirstAdd) {
        failFirstAdd = false;
        await table.add([rows[0]]);
        throw new Error('simulated real LanceDB partial add failure');
      }
      return table.add(rows);
    }
  };
  await assert.rejects(
    replaceSourcePathsSafely(flakyTable, ['/a.md'], [
      { id: 'new-a', source_path: '/a.md', chunk_text: 'new content', vector: [0.5, 0.5] }
    ]),
    /previous rows restored/
  );
  const reopened = await db.openTable('chunks');
  const rows = await reopened.query().toArray();
  assert.deepEqual(
    rows.map((row) => ({ id: row.id, source_path: row.source_path, chunk_text: row.chunk_text })).sort((a, b) => a.id.localeCompare(b.id)),
    original.map(({ id, source_path, chunk_text }) => ({ id, source_path, chunk_text })).sort((a, b) => a.id.localeCompare(b.id))
  );
});
