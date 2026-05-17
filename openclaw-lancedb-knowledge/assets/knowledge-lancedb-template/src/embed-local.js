import crypto from 'node:crypto';

export const LOCAL_HASH_DIMENSIONS = 384;

function hashInt(s) {
  const h = crypto.createHash('sha256').update(s).digest();
  return h.readUInt32BE(0);
}

function normalizeText(text) {
  return text
    .toLowerCase()
    .replace(/[\u200B-\u200D\uFEFF]/g, '')
    .replace(/[`*_#>\[\](){}]/g, ' ')
    .replace(/https?:\/\/\S+/g, ' URL ')
    .replace(/\s+/g, ' ')
    .trim();
}

function tokens(text) {
  const t = normalizeText(text);
  const out = [];
  const latin = t.match(/[a-z0-9_\-]{2,}/g) || [];
  out.push(...latin);
  const cjk = Array.from(t.match(/[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/gu) || []);
  for (let i = 0; i < cjk.length; i++) {
    out.push(cjk[i]);
    if (i + 1 < cjk.length) out.push(cjk[i] + cjk[i + 1]);
    if (i + 2 < cjk.length) out.push(cjk[i] + cjk[i + 1] + cjk[i + 2]);
  }
  // Add short phrase shingles for mixed Chinese/English project terms.
  const words = t.split(/\s+/).filter(Boolean);
  for (let i = 0; i + 1 < words.length; i++) out.push(words[i] + ' ' + words[i + 1]);
  return out;
}

export function embedLocalHash(text, dimensions = LOCAL_HASH_DIMENSIONS) {
  const vector = new Array(dimensions).fill(0);
  for (const token of tokens(text)) {
    const h = hashInt(token);
    const idx = h % dimensions;
    const sign = (h & 1) === 0 ? 1 : -1;
    // sqrt dampening through repeated token accumulation is enough for this POC.
    vector[idx] += sign;
  }
  let norm = Math.sqrt(vector.reduce((a, b) => a + b * b, 0));
  if (!norm) norm = 1;
  return vector.map((v) => v / norm);
}
