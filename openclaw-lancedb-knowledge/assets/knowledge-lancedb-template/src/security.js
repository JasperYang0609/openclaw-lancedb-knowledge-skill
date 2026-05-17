export const SECRET_PATTERNS = [
  { name: 'openai_key', re: /sk-(?:proj-)?[A-Za-z0-9_-]{20,}/g },
  { name: 'notion_token', re: /ntn_[A-Za-z0-9_-]{20,}/g },
  { name: 'google_api_key', re: /AIza[0-9A-Za-z_-]{20,}/g },
  { name: 'jwt', re: /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g },
  { name: 'bearer', re: /Bearer\s+[A-Za-z0-9._~+\/-]+=*/gi },
  { name: 'key_value_secret', re: /\b(?:service\s*role\s*key|api\s*key|secret|token|password)\b\s*[:=]\s*[^\s`'"，,;]+/gi }
];

export function redactSecrets(text) {
  let redacted = text;
  const hits = [];
  for (const p of SECRET_PATTERNS) {
    let count = 0;
    redacted = redacted.replace(p.re, () => {
      count += 1;
      return `[REDACTED_${p.name.toUpperCase()}]`;
    });
    if (count > 0) hits.push({ pattern: p.name, count });
  }
  return { text: redacted, hits };
}

export function looksBinary(buf) {
  const sample = buf.subarray(0, Math.min(buf.length, 4096));
  let zeros = 0;
  for (const b of sample) if (b === 0) zeros += 1;
  return sample.length > 0 && zeros / sample.length > 0.01;
}
