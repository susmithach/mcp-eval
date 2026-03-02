// =============================================================================
// FULL SERVER SNAPSHOT
// PyServiceLab MCP Server — complete source listing
// Generated: 2026-03-01
// =============================================================================
//
// File index:
//   src/index.ts                    — entry point, server + tool dispatch
//   src/utils/logging.ts            — JSON structured logging
//   src/utils/file_utils.ts         — sandbox guard, file helpers, walkFiles
//   src/utils/process_utils.ts      — runProcess with timeout
//   src/utils/git_utils.ts          — getGitDiff, applyGitPatch
//   src/tools/list_files.ts         — list_files tool
//   src/tools/read_file.ts          — read_file tool
//   src/tools/search_in_files.ts    — search_in_files tool
//   src/tools/run_tests.ts          — run_tests tool
//   src/tools/apply_patch.ts        — apply_patch tool
//   src/tools/git_diff.ts           — git_diff tool
// =============================================================================


// =============================================================================
// FILE: src/index.ts
// =============================================================================

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from "@modelcontextprotocol/sdk/types.js";
import { ZodError } from "zod";

import { applyPatch } from "./tools/apply_patch.js";
import { gitDiff } from "./tools/git_diff.js";
import { listFiles } from "./tools/list_files.js";
import { readFile } from "./tools/read_file.js";
import { runTests } from "./tools/run_tests.js";
import { searchInFiles } from "./tools/search_in_files.js";

// ---------------------------------------------------------------------------
// Server instance
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "server-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } },
);

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "list_files",
      description:
        "List files and directories at the given path inside the target repository.",
      inputSchema: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description:
              'Relative path inside the target repository (e.g. "." or "src/").',
          },
        },
        required: ["path"],
        additionalProperties: false,
      },
    },
    {
      name: "read_file",
      description:
        "Read the content of a file inside the target repository (max 200 KB).",
      inputSchema: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description:
              "Relative path to the file inside the target repository.",
          },
        },
        required: ["path"],
        additionalProperties: false,
      },
    },
    {
      name: "search_in_files",
      description:
        "Search for a text query across all files under the given path.",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: "Text to search for." },
          path: {
            type: "string",
            description: "Root path to search under (relative to target-repo).",
          },
          limit: {
            type: "number",
            description:
              "Maximum number of matches to return (1–500, default 50).",
          },
        },
        required: ["query", "path"],
        additionalProperties: false,
      },
    },
    {
      name: "run_tests",
      description:
        "Run pytest inside the target repository. Only pytest / python -m pytest commands are allowed.",
      inputSchema: {
        type: "object",
        properties: {
          command: {
            type: "string",
            description:
              'Test command to run, e.g. "pytest" or "python -m pytest tests/".',
          },
        },
        required: ["command"],
        additionalProperties: false,
      },
    },
    {
      name: "apply_patch",
      description:
        "Apply a unified diff patch to the target repository using git apply.",
      inputSchema: {
        type: "object",
        properties: {
          patch: {
            type: "string",
            description: "Unified diff patch content.",
          },
        },
        required: ["patch"],
        additionalProperties: false,
      },
    },
    {
      name: "git_diff",
      description:
        "Return the current git diff (unstaged changes) of the target repository.",
      inputSchema: {
        type: "object",
        properties: {},
        additionalProperties: false,
      },
    },
  ],
}));

// ---------------------------------------------------------------------------
// Tool dispatch
// ---------------------------------------------------------------------------

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result: unknown;

    switch (name) {
      case "list_files":
        result = await listFiles(args);
        break;
      case "read_file":
        result = await readFile(args);
        break;
      case "search_in_files":
        result = await searchInFiles(args);
        break;
      case "run_tests":
        result = await runTests(args);
        break;
      case "apply_patch":
        result = await applyPatch(args);
        break;
      case "git_diff":
        result = await gitDiff(args);
        break;
      default:
        throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: "${name}"`);
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  } catch (err) {
    // Re-throw McpErrors as-is (they carry the correct error code)
    if (err instanceof McpError) throw err;

    // Zod validation errors → InvalidParams
    if (err instanceof ZodError) {
      throw new McpError(
        ErrorCode.InvalidParams,
        `Invalid arguments: ${err.errors.map((e) => `${e.path.join(".")}: ${e.message}`).join("; ")}`,
      );
    }

    // All other errors → InternalError (never crash the server)
    throw new McpError(
      ErrorCode.InternalError,
      err instanceof Error ? err.message : String(err),
    );
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // Do NOT write to stdout — it is used by the MCP protocol.
  // Use the log file (logs/mcp.log) for diagnostics.
}

main().catch((err) => {
  // Last-resort: write to stderr and exit
  process.stderr.write(
    `Fatal error: ${err instanceof Error ? err.message : String(err)}\n`,
  );
  process.exit(1);
});


// =============================================================================
// FILE: src/utils/logging.ts
// =============================================================================

import * as fs from "fs";
import * as path from "path";

// Always relative to the process working directory (server-mcp/)
const LOG_DIR = path.resolve(process.cwd(), "logs");
const LOG_FILE = path.join(LOG_DIR, "mcp.log");

const MAX_ARG_LENGTH = 200;

function ensureLogDir(): void {
  fs.mkdirSync(LOG_DIR, { recursive: true });
}

function truncate(value: unknown, maxLength = MAX_ARG_LENGTH): string {
  const str =
    typeof value === "string" ? value : JSON.stringify(value) ?? "";
  if (str.length <= maxLength) return str;
  return `${str.slice(0, maxLength)}…[${str.length - maxLength} chars truncated]`;
}

interface LogEntry {
  timestamp: string;
  tool: string;
  args: string;
  durationMs: number;
  success: boolean;
  bytesReturned: number;
  error?: string;
}

function writeLog(entry: LogEntry): void {
  try {
    ensureLogDir();
    fs.appendFileSync(LOG_FILE, JSON.stringify(entry) + "\n", "utf8");
  } catch {
    // Never crash the server due to a logging failure
  }
}

export interface Logger {
  log(
    args: unknown,
    durationMs: number,
    resultStr: string,
    success: boolean,
    error?: string
  ): void;
}

export function createLogger(toolName: string): Logger {
  return {
    log(args, durationMs, resultStr, success, error) {
      writeLog({
        timestamp: new Date().toISOString(),
        tool: toolName,
        args: truncate(args),
        durationMs,
        success,
        bytesReturned: resultStr.length,
        error,
      });
    },
  };
}


// =============================================================================
// FILE: src/utils/file_utils.ts
// =============================================================================

import * as fs from "fs";
import * as path from "path";

export const MAX_FILE_SIZE = 200 * 1024; // 200 KB

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
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walkFiles(full);
    } else if (entry.isFile()) {
      yield full;
    }
  }
}


// =============================================================================
// FILE: src/utils/process_utils.ts
// =============================================================================

import { execFile } from "child_process";

export interface ProcessResult {
  exitCode: number;
  stdout: string;
  stderr: string;
}

/**
 * Runs a command (no shell) with a hard timeout and cwd restriction.
 * Always resolves — never rejects.
 */
export async function runProcess(
  command: string,
  args: string[],
  cwd: string,
  timeoutMs = 30_000
): Promise<ProcessResult> {
  return new Promise((resolve) => {
    execFile(
      command,
      args,
      {
        cwd,
        timeout: timeoutMs,
        maxBuffer: 2 * 1024 * 1024, // 2 MB
        shell: false,
      },
      (error, stdout, stderr) => {
        if (error) {
          resolve({
            exitCode: (error as NodeJS.ErrnoException & { code?: number }).code
              ?? 1,
            stdout: stdout ?? "",
            stderr: stderr || error.message,
          });
        } else {
          resolve({ exitCode: 0, stdout, stderr });
        }
      }
    );
  });
}


// =============================================================================
// FILE: src/utils/git_utils.ts
// =============================================================================

import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { runProcess } from "./process_utils.js";

export async function getGitDiff(repoPath: string): Promise<string> {
  const result = await runProcess("git", ["diff"], repoPath, 10_000);
  return result.stdout;
}

export async function applyGitPatch(
  repoPath: string,
  patchContent: string
): Promise<{ applied: boolean; error: string | null }> {
  const tmpFile = path.join(
    os.tmpdir(),
    `mcp_patch_${Date.now()}.patch`
  );
  try {
    fs.writeFileSync(tmpFile, patchContent, "utf8");
    const result = await runProcess(
      "git",
      ["apply", tmpFile],
      repoPath,
      10_000
    );
    if (result.exitCode === 0) {
      return { applied: true, error: null };
    }
    return {
      applied: false,
      error: result.stderr || result.stdout || "git apply failed",
    };
  } catch (err) {
    return {
      applied: false,
      error: err instanceof Error ? err.message : String(err),
    };
  } finally {
    try {
      fs.unlinkSync(tmpFile);
    } catch {
      // Temp file cleanup is best-effort
    }
  }
}


// =============================================================================
// FILE: src/tools/list_files.ts
// =============================================================================

import * as fs from "fs";
import { z } from "zod";
import {
  assertExists,
  assertIsDirectory,
  getTargetRepo,
  resolveSafe,
} from "../utils/file_utils.js";
import { createLogger } from "../utils/logging.js";

const logger = createLogger("list_files");

export const ListFilesSchema = z.object({
  path: z.string().min(1, "path must not be empty"),
});

export interface ListFilesResult {
  files: string[];
  directories: string[];
}

export async function listFiles(rawArgs: unknown): Promise<ListFilesResult> {
  const args = ListFilesSchema.parse(rawArgs);
  const base = getTargetRepo();
  const resolved = resolveSafe(base, args.path);

  const start = Date.now();
  try {
    assertExists(resolved);
    assertIsDirectory(resolved);

    const entries = fs.readdirSync(resolved, { withFileTypes: true });
    const result: ListFilesResult = {
      files: entries.filter((e) => e.isFile()).map((e) => e.name).sort(),
      directories: entries.filter((e) => e.isDirectory()).map((e) => e.name).sort(),
    };

    logger.log(args, Date.now() - start, JSON.stringify(result), true);
    return result;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.log(args, Date.now() - start, "", false, msg);
    throw err;
  }
}


// =============================================================================
// FILE: src/tools/read_file.ts
// =============================================================================

import * as fs from "fs";
import { z } from "zod";
import {
  assertExists,
  assertIsFile,
  getFileSize,
  getTargetRepo,
  MAX_FILE_SIZE,
  resolveSafe,
} from "../utils/file_utils.js";
import { createLogger } from "../utils/logging.js";

const logger = createLogger("read_file");

export const ReadFileSchema = z.object({
  path: z.string().min(1, "path must not be empty"),
});

export interface ReadFileResult {
  content: string;
  size: number;
}

export async function readFile(rawArgs: unknown): Promise<ReadFileResult> {
  const args = ReadFileSchema.parse(rawArgs);
  const base = getTargetRepo();
  const resolved = resolveSafe(base, args.path);

  const start = Date.now();
  try {
    assertExists(resolved);
    assertIsFile(resolved);

    const size = getFileSize(resolved);
    if (size > MAX_FILE_SIZE) {
      throw new Error(
        `File too large: ${size} bytes (limit ${MAX_FILE_SIZE} bytes / 200 KB)`
      );
    }

    const content = fs.readFileSync(resolved, "utf8");
    const result: ReadFileResult = { content, size };

    logger.log(args, Date.now() - start, JSON.stringify(result), true);
    return result;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.log(args, Date.now() - start, "", false, msg);
    throw err;
  }
}


// =============================================================================
// FILE: src/tools/search_in_files.ts
// =============================================================================

import * as fs from "fs";
import { z } from "zod";
import {
  assertExists,
  getTargetRepo,
  resolveSafe,
  walkFiles,
} from "../utils/file_utils.js";
import { createLogger } from "../utils/logging.js";

const logger = createLogger("search_in_files");

export const SearchInFilesSchema = z.object({
  query: z.string().min(1, "query must not be empty"),
  path: z.string().min(1, "path must not be empty"),
  limit: z.number().int().min(1).max(500).default(50),
});

export interface SearchMatch {
  file: string;
  line: number;
  content: string;
}

export interface SearchInFilesResult {
  matches: SearchMatch[];
}

const MAX_FILE_READ = 200 * 1024; // 200 KB — skip larger files

export async function searchInFiles(
  rawArgs: unknown
): Promise<SearchInFilesResult> {
  const args = SearchInFilesSchema.parse(rawArgs);
  const base = getTargetRepo();
  const resolved = resolveSafe(base, args.path);

  const start = Date.now();
  try {
    assertExists(resolved);

    const matches: SearchMatch[] = [];
    const query = args.query;

    outer: for (const filePath of walkFiles(resolved)) {
      // Skip binary / oversized files
      let raw: string;
      try {
        const stat = fs.statSync(filePath);
        if (stat.size > MAX_FILE_READ) continue;
        raw = fs.readFileSync(filePath, "utf8");
      } catch {
        continue;
      }

      const lines = raw.split("\n");
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes(query)) {
          matches.push({
            file: filePath,
            line: i + 1,
            content: lines[i].trim(),
          });
          if (matches.length >= args.limit) break outer;
        }
      }
    }

    const result: SearchInFilesResult = { matches };
    logger.log(args, Date.now() - start, JSON.stringify(result), true);
    return result;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.log(args, Date.now() - start, "", false, msg);
    throw err;
  }
}


// =============================================================================
// FILE: src/tools/run_tests.ts
// =============================================================================

import { z } from "zod";
import { getTargetRepo } from "../utils/file_utils.js";
import { createLogger } from "../utils/logging.js";
import { runProcess } from "../utils/process_utils.js";

const logger = createLogger("run_tests");

export const RunTestsSchema = z.object({
  command: z.string().min(1, "command must not be empty"),
});

export interface RunTestsResult {
  exit_code: number;
  stdout: string;
  stderr: string;
}

/**
 * Whitelist of allowed base commands.
 * Prevents arbitrary shell execution.
 */
const ALLOWED_BASES = new Set(["pytest", "python", "python3"]);

/**
 * Parses and validates the command string.
 * Only pytest / python -m pytest invocations are allowed.
 */
function parseCommand(command: string): { cmd: string; args: string[] } {
  const parts = command.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    throw new Error("Empty command");
  }

  const cmd = parts[0];
  const rest = parts.slice(1);

  if (!ALLOWED_BASES.has(cmd)) {
    throw new Error(
      `Command not allowed: "${cmd}". ` +
        `Allowed: pytest, python -m pytest, python3 -m pytest`
    );
  }

  // python / python3 must be followed by "-m" "pytest" (optionally + args)
  if (cmd === "python" || cmd === "python3") {
    if (rest[0] !== "-m" || rest[1] !== "pytest") {
      throw new Error(
        `Only "python -m pytest" invocations are allowed, got: "${command}"`
      );
    }
  }

  return { cmd, args: rest };
}

export async function runTests(rawArgs: unknown): Promise<RunTestsResult> {
  const args = RunTestsSchema.parse(rawArgs);
  const { cmd, args: cmdArgs } = parseCommand(args.command);
  const cwd = getTargetRepo();

  const start = Date.now();
  try {
    const proc = await runProcess(cmd, cmdArgs, cwd, 60_000);
    const result: RunTestsResult = {
      exit_code: proc.exitCode,
      stdout: proc.stdout,
      stderr: proc.stderr,
    };
    logger.log(args, Date.now() - start, JSON.stringify(result), true);
    return result;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.log(args, Date.now() - start, "", false, msg);
    throw err;
  }
}


// =============================================================================
// FILE: src/tools/apply_patch.ts
// =============================================================================

import { z } from "zod";
import { getTargetRepo } from "../utils/file_utils.js";
import { applyGitPatch } from "../utils/git_utils.js";
import { createLogger } from "../utils/logging.js";

const logger = createLogger("apply_patch");

export const ApplyPatchSchema = z.object({
  patch: z.string().min(1, "patch must not be empty"),
});

export interface ApplyPatchResult {
  applied: boolean;
  error: string | null;
}

export async function applyPatch(rawArgs: unknown): Promise<ApplyPatchResult> {
  const args = ApplyPatchSchema.parse(rawArgs);
  const repoPath = getTargetRepo();

  const start = Date.now();
  try {
    const patchBytes = Buffer.byteLength(args.patch, "utf8");
    const result = await applyGitPatch(repoPath, args.patch);

    logger.log(
      { patchSizeBytes: patchBytes },
      Date.now() - start,
      JSON.stringify(result),
      result.applied
    );
    return result;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.log(args, Date.now() - start, "", false, msg);
    throw err;
  }
}


// =============================================================================
// FILE: src/tools/git_diff.ts
// =============================================================================

import { z } from "zod";
import { getTargetRepo } from "../utils/file_utils.js";
import { getGitDiff } from "../utils/git_utils.js";
import { createLogger } from "../utils/logging.js";

const logger = createLogger("git_diff");

// No required inputs — empty schema with no required fields
export const GitDiffSchema = z.object({}).strict();

export interface GitDiffResult {
  diff: string;
}

export async function gitDiff(rawArgs: unknown): Promise<GitDiffResult> {
  const _args = GitDiffSchema.parse(rawArgs);
  const repoPath = getTargetRepo();

  const start = Date.now();
  try {
    const diff = await getGitDiff(repoPath);
    const result: GitDiffResult = { diff };

    logger.log({}, Date.now() - start, JSON.stringify(result), true);
    return result;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.log({}, Date.now() - start, "", false, msg);
    throw err;
  }
}
