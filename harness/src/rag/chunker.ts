import type { ChunkingOptions, RagChunk } from "./types.js";

export const DEFAULT_CHUNKING_OPTIONS: ChunkingOptions = {
  chunkSize: 120,
  overlap: 20,
};

function normalizeOptions(
  options: Partial<ChunkingOptions> | undefined,
): ChunkingOptions {
  const chunkSize = options?.chunkSize ?? DEFAULT_CHUNKING_OPTIONS.chunkSize;
  const overlap = options?.overlap ?? DEFAULT_CHUNKING_OPTIONS.overlap;

  if (chunkSize < 1) {
    throw new Error("chunkSize must be at least 1");
  }
  if (overlap < 0) {
    throw new Error("overlap must be non-negative");
  }
  if (overlap >= chunkSize) {
    throw new Error("overlap must be smaller than chunkSize");
  }

  return { chunkSize, overlap };
}

export function chunkFile(
  path: string,
  content: string,
  options?: Partial<ChunkingOptions>,
): RagChunk[] {
  const normalized = normalizeOptions(options);
  const lines = content.split("\n");

  if (lines.length === 0) {
    return [];
  }

  const chunks: RagChunk[] = [];
  const step = normalized.chunkSize - normalized.overlap;

  for (let start = 0; start < lines.length; start += step) {
    const endExclusive = Math.min(start + normalized.chunkSize, lines.length);
    const chunkLines = lines.slice(start, endExclusive);
    const text = chunkLines.join("\n").trimEnd();

    if (text.trim().length === 0) {
      continue;
    }

    chunks.push({
      id: `${path}:${start + 1}-${endExclusive}`,
      path,
      startLine: start + 1,
      endLine: endExclusive,
      text,
    });

    if (endExclusive >= lines.length) {
      break;
    }
  }

  return chunks;
}
