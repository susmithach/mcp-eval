import { readdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chunkFile, DEFAULT_CHUNKING_OPTIONS } from "./chunker.js";
import type { ChunkingOptions, RagChunk, RagIndex } from "./types.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const TARGET_REPO_ROOT = resolve(__dirname, "../../../target-repo");

const INCLUDED_ROOTS = ["pyservicelab", "tests"];
const SKIPPED_DIRECTORIES = new Set([
  ".git",
  ".venv",
  ".pytest_cache",
  "__pycache__",
  "node_modules",
]);

async function walkPythonFiles(dir: string): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true });
  const paths: string[] = [];

  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (entry.isDirectory()) {
      if (SKIPPED_DIRECTORIES.has(entry.name)) {
        continue;
      }
      paths.push(...(await walkPythonFiles(resolve(dir, entry.name))));
      continue;
    }

    if (!entry.isFile()) {
      continue;
    }
    if (!entry.name.endsWith(".py")) {
      continue;
    }

    paths.push(resolve(dir, entry.name));
  }

  return paths;
}

function toRepoRelativePath(absolutePath: string): string {
  const prefix = `${TARGET_REPO_ROOT}/`;
  return absolutePath.startsWith(prefix)
    ? absolutePath.slice(prefix.length)
    : absolutePath;
}

export async function buildRagIndex(
  options?: Partial<ChunkingOptions>,
): Promise<RagIndex> {
  const normalized = {
    ...DEFAULT_CHUNKING_OPTIONS,
    ...options,
  };

  const allChunks: RagChunk[] = [];

  for (const root of INCLUDED_ROOTS) {
    const absoluteRoot = resolve(TARGET_REPO_ROOT, root);
    const files = await walkPythonFiles(absoluteRoot);

    for (const file of files) {
      const content = await readFile(file, "utf8");
      const relativePath = toRepoRelativePath(file);
      const chunks = chunkFile(relativePath, content, normalized);
      allChunks.push(...chunks);
    }
  }

  return { chunks: allChunks };
}
