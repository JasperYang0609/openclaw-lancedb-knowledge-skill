#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";

const root = path.resolve(new URL("..", import.meta.url).pathname);
const checks = [];

function record(name, ok, detail = "") {
  checks.push({ name, ok, detail });
}

async function exists(rel) {
  try {
    await fs.access(path.join(root, rel));
    return true;
  } catch {
    return false;
  }
}

async function readJson(rel) {
  return JSON.parse(await fs.readFile(path.join(root, rel), "utf8"));
}

record("required files exist", await exists("src/cli.js") && await exists("src/security.js") && await exists("config/source-map.example.json"));

const pkg = await readJson("package.json");
record("package exposes post-run check", pkg.scripts?.["postrun:check"] === "node scripts/post_run_check.mjs");
record("core scripts present", ["scan", "index", "search", "status", "test", "incremental", "sync-state", "compact-cache"].every((key) => pkg.scripts?.[key]));

const sourceMap = await readJson("config/source-map.example.json");
record("source map has sources", Array.isArray(sourceMap.sources) && sourceMap.sources.length > 0);
record("source map excludes common secret paths", JSON.stringify(sourceMap).includes("secret") && JSON.stringify(sourceMap).includes(".env"));

const wrapper = await fs.readFile(path.join(root, "scripts/knowledge_index_incremental.sh"), "utf8");
record("incremental wrapper uses lock", wrapper.includes("index.lock") && wrapper.includes("mkdir \"$LOCK_DIR\""));
record("incremental wrapper rotates reports", wrapper.includes("rotate_reports"));

const tests = spawnSync("npm", ["test"], { cwd: root, encoding: "utf8" });
record("template tests pass", tests.status === 0, tests.status === 0 ? "" : (tests.stderr || tests.stdout).slice(-1200));

const failed = checks.filter((check) => !check.ok);
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}${check.detail ? ` - ${check.detail}` : ""}`);
}

if (failed.length) {
  console.error(`post-run check failed: ${failed.length} issue(s)`);
  process.exit(1);
}

console.log("post-run check passed");
