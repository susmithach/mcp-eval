export interface RagChunk {
  id: string;
  path: string;
  startLine: number;
  endLine: number;
  text: string;
}

export interface RagIndex {
  chunks: RagChunk[];
}

export interface RetrievedChunk {
  chunk: RagChunk;
  score: number;
}

export interface ChunkingOptions {
  chunkSize: number;
  overlap: number;
}

export interface RetrievalOptions {
  topK: number;
}
