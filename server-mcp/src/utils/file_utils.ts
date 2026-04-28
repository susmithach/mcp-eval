import * as fs from "fs";
import * as path from "path";

export const MAX_FILE_SIZE = 200 * 1024; // 200 KB
const IGNORED_DIRECTORIES = new Set([
  ".git",
  ".pytest_cache",
  ".venv",
  "__pycache__",
  "node_modules",
]);
const IGNORED_FILE_SUFFIXES = [".pyc", ".pyo"];

/**
 * Returns the absolute path of the sandboxed target repository.
 * Controlled by TARGET_REPO env var; defaults to ../target-repo
 * relative to the server-mcp working directory.
 */
export function getTargetRepo(): string {
  const env = process.env.TARGET_REPO;
  if (env) {
    return path.resolve(env);
  }
  return path.resolve(process.cwd(), "../target-repo");
}

/**
 * Resolves `userPath` relative to `base` and throws if the result
 * escapes the sandbox.
 */
export function resolveSafe(base: string, userPath: string): string {
  const normalBase = path.resolve(base);
  const resolved = path.resolve(normalBase, userPath);
  const rel = path.relative(normalBase, resolved);
  // If the relative path starts with ".." or is absolute, it's outside
  if (rel.startsWith("..") || path.isAbsolute(rel)) {
    throw new Error(
      `Path traversal detected: "${userPath}" escapes sandbox boundary`
    );
  }
  return resolved;
}

export function assertExists(resolvedPath: string): void {
  if (!fs.existsSync(resolvedPath)) {
    throw new Error(`Path does not exist: "${resolvedPath}"`);
  }
}

export function assertIsFile(resolvedPath: string): void {
  const stat = fs.statSync(resolvedPath);
  if (!stat.isFile()) {
    throw new Error(`Path is not a file: "${resolvedPath}"`);
  }
}

export function assertIsDirectory(resolvedPath: string): void {
  const stat = fs.statSync(resolvedPath);
  if (!stat.isDirectory()) {
    throw new Error(`Path is not a directory: "${resolvedPath}"`);
  }
}

export function getFileSize(resolvedPath: string): number {
  return fs.statSync(resolvedPath).size;
}

/**
 * Recursively yield all file paths under `dir`.
 * Skips entries that cannot be read.
 */
export function* walkFiles(dir: string): Generator<string> {
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (IGNORED_DIRECTORIES.has(entry.name)) {
      continue;
    }
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walkFiles(full);
    } else if (
      entry.isFile() &&
      !IGNORED_FILE_SUFFIXES.some((suffix) => entry.name.endsWith(suffix))
    ) {
      yield full;
    }
  }
}
