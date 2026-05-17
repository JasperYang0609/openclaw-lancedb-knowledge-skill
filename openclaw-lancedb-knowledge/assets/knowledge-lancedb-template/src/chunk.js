import path from 'node:path';
import crypto from 'node:crypto';

function sha256(text) {
  return crypto.createHash('sha256').update(text).digest('hex');
}

function estimateTokens(text) {
  // CJK-heavy text is underestimated by whitespace split; char/3 is a safer rough bound.
  return Math.max(text.split(/\s+/).filter(Boolean).length, Math.ceil([...text].length / 3));
}

function splitOversized(text, maxChars = 3600, overlapChars = 350) {
  if (text.length <= maxChars) return [text];
  const chunks = [];
  let i = 0;
  while (i < text.length) {
    const end = Math.min(text.length, i + maxChars);
    chunks.push(text.slice(i, end));
    if (end === text.length) break;
    i = Math.max(0, end - overlapChars);
  }
  return chunks;
}

function inferTitle(relPath, content) {
  const h1 = content.match(/^#\s+(.+)$/m);
  if (h1) return h1[1].trim().slice(0, 160);
  return path.basename(relPath, path.extname(relPath));
}

function inferDate(relPath, content) {
  const m = (relPath + '\n' + content.slice(0, 2000)).match(/(20\d{2}[-/]\d{2}[-/]\d{2})/);
  return m ? m[1].replaceAll('/', '-') : '';
}

function inferChannel(absPath) {
  const marker = '/頻道紀錄/';
  const idx = absPath.indexOf(marker);
  if (idx < 0) return '';
  const rest = absPath.slice(idx + marker.length).split('/');
  return rest[0] || '';
}

function inferProject(source, relPath, absPath) {
  if (source.project && source.project !== 'DiscordBackups' && source.project !== 'GlobalMemory') return source.project;
  const s = (relPath + ' ' + absPath).toLowerCase();
  if (/vaso|documentcenter|documentdetail|flutterflow/.test(s)) return 'VASO';
  if (/beango|咖啡|cafe/.test(s)) return 'BeanGo';
  if (/新人|trainee/.test(s)) return 'TraineeApp';
  if (/股票|stock|anan-stock|安安股票/.test(s)) return 'StockMonitor';
  if (/ig|instagram/.test(s)) return 'IGResearch';
  if (/openclaw|backup|cron|memory|heartbeat/.test(s)) return 'OpenClawOps';
  if (/品牌|brand|ansai/.test(s)) return 'AnsaiBrand';
  return source.project || 'General';
}

export function chunkMarkdown({ source, absPath, relPath, content }) {
  const title = inferTitle(relPath, content);
  const date = inferDate(relPath, content);
  const channel = inferChannel(absPath);
  const project = inferProject(source, relPath, absPath);
  const sections = [];
  const lines = content.split(/\r?\n/);
  let currentHeading = title;
  let buf = [];

  function flush() {
    const text = buf.join('\n').trim();
    if (text.length >= 40) sections.push({ heading: currentHeading, text });
    buf = [];
  }

  for (const line of lines) {
    const hm = line.match(/^(#{1,4})\s+(.+)$/);
    if (hm && buf.length > 0) {
      flush();
      currentHeading = hm[2].trim();
      buf.push(line);
    } else {
      if (hm) currentHeading = hm[2].trim();
      buf.push(line);
    }
  }
  flush();

  const chunks = [];
  let chunkIndex = 0;
  for (const section of sections.length ? sections : [{ heading: title, text: content }]) {
    for (const part of splitOversized(section.text)) {
      const trimmed = part.trim();
      if (trimmed.length < 40) continue;
      chunks.push({
        id: sha256(`${absPath}\n${chunkIndex}\n${sha256(trimmed)}`),
        source_id: source.id,
        source_path: absPath,
        rel_path: relPath,
        source_type: source.sourceType,
        project,
        channel,
        title,
        heading: section.heading || title,
        date,
        chunk_index: chunkIndex++,
        chunk_text: trimmed,
        token_estimate: estimateTokens(trimmed),
        content_sha256: sha256(trimmed)
      });
    }
  }
  return chunks;
}
