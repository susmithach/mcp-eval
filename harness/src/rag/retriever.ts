import type { RagChunk, RagIndex, RetrievalOptions, RetrievedChunk } from "./types.js";

export const DEFAULT_RETRIEVAL_OPTIONS: RetrievalOptions = {
  topK: 6,
  sourceBoostFactor: 1.0,
  deduplicatePerFile: false,
};

const TOKEN_PATTERN = /[a-zA-Z0-9_]+/g;
const STOP_TOKENS = new Set([
  "a",
  "an",
  "and",
  "are",
  "as",
  "at",
  "be",
  "by",
  "file",
  "for",
  "from",
  "in",
  "is",
  "it",
  "of",
  "on",
  "or",
  "package",
  "path",
  "py",
  "task",
  "tests",
  "test",
  "that",
  "the",
  "this",
  "to",
  "with",
]);
const MIN_CHUNK_TOKENS = 8;

export function tokenize(text: string): string[] {
  const matches = text.toLowerCase().match(TOKEN_PATTERN) ?? [];
  return matches.filter((token) => token.length >= 2 && !STOP_TOKENS.has(token));
}

function tokenFrequency(tokens: string[]): Map<string, number> {
  const frequencies = new Map<string, number>();
  for (const token of tokens) {
    frequencies.set(token, (frequencies.get(token) ?? 0) + 1);
  }
  return frequencies;
}

// Fix 1 (source boost) + Fix 3 (BM25 IDF): score each chunk using IDF-weighted
// token matching; multiply final score for pyservicelab/ source files.
function scoreChunk(
  queryTokens: string[],
  chunk: RagChunk,
  idf: Map<string, number>,
  sourceBoostFactor: number,
): number {
  const chunkTokens = tokenize(chunk.text);
  if (chunkTokens.length < MIN_CHUNK_TOKENS || queryTokens.length === 0) {
    return 0;
  }

  const chunkFreq = tokenFrequency(chunkTokens);
  const uniqueQueryTokens = new Set(queryTokens);
  const pathTokens = new Set(tokenize(chunk.path.replaceAll("/", " ")));

  let matchedIdfSum = 0;
  let totalIdfSum = 0;
  let weightedMatches = 0;
  let pathBoostSum = 0;

  for (const token of uniqueQueryTokens) {
    // Default IDF of 1.0 for tokens absent from the corpus (treat as moderately rare).
    const tokenIdf = idf.get(token) ?? 1.0;
    totalIdfSum += tokenIdf;

    const frequency = chunkFreq.get(token);
    if (!frequency) {
      if (pathTokens.has(token)) {
        pathBoostSum += tokenIdf;
      }
      continue;
    }
    matchedIdfSum += tokenIdf;
    weightedMatches += frequency * tokenIdf;
    if (pathTokens.has(token)) {
      pathBoostSum += tokenIdf;
    }
  }

  if (matchedIdfSum === 0 && pathBoostSum === 0) {
    return 0;
  }

  const denominator = totalIdfSum > 0 ? totalIdfSum : 1;
  const coverageScore = matchedIdfSum / denominator;
  const densityScore = weightedMatches / chunkTokens.length;
  const pathBoost = pathBoostSum / denominator;

  const rawScore = coverageScore + densityScore + pathBoost;
  const isSource = chunk.path.startsWith("pyservicelab/");
  return isSource ? rawScore * sourceBoostFactor : rawScore;
}

export function retrieveRelevantChunks(
  index: RagIndex,
  query: string,
  options?: Partial<RetrievalOptions>,
): RetrievedChunk[] {
  const topK = options?.topK ?? DEFAULT_RETRIEVAL_OPTIONS.topK;
  const sourceBoostFactor =
    options?.sourceBoostFactor ?? DEFAULT_RETRIEVAL_OPTIONS.sourceBoostFactor;
  const deduplicatePerFile =
    options?.deduplicatePerFile ?? DEFAULT_RETRIEVAL_OPTIONS.deduplicatePerFile;

  if (topK < 1) {
    throw new Error("topK must be at least 1");
  }

  const queryTokens = tokenize(query);
  const scored = index.chunks
    .map((chunk) => ({
      chunk,
      score: scoreChunk(queryTokens, chunk, index.idf, sourceBoostFactor),
    }))
    .filter((item) => item.score > 0)
    .sort((a, b) => {
      if (b.score !== a.score) {
        return b.score - a.score;
      }
      return a.chunk.id.localeCompare(b.chunk.id);
    });

  // Fix 2: keep only the single highest-scoring chunk per file so that
  // overlapping 120-line windows from the same file don't consume multiple
  // slots and confuse the LLM with near-duplicate content.
  if (!deduplicatePerFile) {
    return scored.slice(0, topK);
  }

  const seen = new Set<string>();
  const deduplicated: Array<{ chunk: RagChunk; score: number }> = [];
  for (const item of scored) {
    if (!seen.has(item.chunk.path)) {
      seen.add(item.chunk.path);
      deduplicated.push(item);
    }
    if (deduplicated.length >= topK) break;
  }
  return deduplicated;
}
