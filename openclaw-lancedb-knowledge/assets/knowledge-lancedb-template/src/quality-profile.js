const GEMINI_MODEL = 'gemini-embedding-001';

function cachePathForDimensions(cachePath, dimensions) {
  if (!cachePath) return cachePath;
  if (/[-_]\d+\.jsonl$/i.test(cachePath)) return cachePath.replace(/([-_])\d+(\.jsonl)$/i, `$1${dimensions}$2`);
  if (/\.jsonl$/i.test(cachePath)) return cachePath.replace(/\.jsonl$/i, `-${dimensions}.jsonl`);
  return `${cachePath}-${dimensions}.jsonl`;
}

export function resolveEmbeddingProfile(embedding = {}) {
  const provider = embedding.provider || 'local-hash-v1';
  const model = embedding.model || (provider === 'google-gemini' ? GEMINI_MODEL : provider);
  let profile = embedding.profile;
  let dimensions = Number(embedding.dimensions) || 0;
  if (!profile && dimensions) profile = 'custom';
  if (!profile) profile = 'balanced';
  if (!['balanced', 'high-quality', 'custom'].includes(profile)) throw new Error(`Unknown embedding profile: ${profile}`);
  if (profile === 'balanced') dimensions = provider === 'google-gemini' ? 768 : (dimensions || 384);
  if (profile === 'high-quality') dimensions = provider === 'google-gemini' ? 3072 : (dimensions || 768);
  if (profile === 'custom' && !dimensions) throw new Error('Custom embedding profile requires dimensions');
  let cachePath = embedding.cachePath;
  if (provider === 'google-gemini' && cachePath) {
    const encodedDimension = cachePath.match(/[-_](\d+)\.jsonl$/i)?.[1];
    if (encodedDimension && Number(encodedDimension) !== dimensions) cachePath = cachePathForDimensions(cachePath, dimensions);
  }
  if (!cachePath && provider === 'google-gemini') cachePath = `./data/embedding-cache/${model}-${dimensions}.jsonl`;
  return { ...embedding, provider, model, profile, dimensions, ...(cachePath ? { cachePath } : {}) };
}

export function resolveQualityConfig(config = {}) {
  return {
    ...config,
    embedding: resolveEmbeddingProfile(config.embedding || {}),
    chunking: {
      maxChars: config.chunking?.maxChars || (config.embedding?.profile === 'high-quality' ? 2800 : 3600),
      overlapChars: config.chunking?.overlapChars ?? 350,
      ...config.chunking
    }
  };
}
