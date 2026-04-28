import type { RagChunk, RagIndex, RetrievalOptions, RetrievedChunk } from "./types.js";

export const DEFAULT_RETRIEVAL_OPTIONS: RetrievalOptions = {
  topK: 6,
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

function tokenize(text: string): string[] {
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

function scoreChunk(queryTokens: string[], chunk: RagChunk): number {
  const chunkTokens = tokenize(chunk.text);
  if (chunkTokens.length < MIN_CHUNK_TOKENS || queryTokens.length === 0) {
    return 0;
  }

  const chunkFreq = tokenFrequency(chunkTokens);
  const uniqueQueryTokens = new Set(queryTokens);
  const pathTokens = new Set(tokenize(chunk.path.replaceAll("/", " ")));

  let matchedTokenCount = 0;
  let weightedMatches = 0;
  let pathMatches = 0;

  for (const token of uniqueQueryTokens) {
    const frequency = chunkFreq.get(token);
    if (!frequency) {
      if (pathTokens.has(token)) {
        pathMatches++;
      }
      continue;
    }
    matchedTokenCount++;
    weightedMatches += frequency;
    if (pathTokens.has(token)) {
      pathMatches++;
    }
  }

  if (matchedTokenCount === 0 && pathMatches === 0) {
    return 0;
  }

  const coverageScore = matchedTokenCount / uniqueQueryTokens.size;
  const densityScore = weightedMatches / chunkTokens.length;
  const pathBoost = pathMatches / uniqueQueryTokens.size;

  return coverageScore + densityScore + pathBoost;
}

export function retrieveRelevantChunks(
  index: RagIndex,
  query: string,
  options?: Partial<RetrievalOptions>,
): RetrievedChunk[] {
  const topK = options?.topK ?? DEFAULT_RETRIEVAL_OPTIONS.topK;
  if (topK < 1) {
    throw new Error("topK must be at least 1");
  }

  const queryTokens = tokenize(query);
  const scored = index.chunks
    .map((chunk) => ({
      chunk,
      score: scoreChunk(queryTokens, chunk),
    }))
    .filter((item) => item.score > 0)
    .sort((a, b) => {
      if (b.score !== a.score) {
        return b.score - a.score;
      }
      return a.chunk.id.localeCompare(b.chunk.id);
    });

  return scored.slice(0, topK);
}
