import { spawn } from "child_process";
import { z } from "zod";
import { getTargetRepo } from "../utils/file_utils.js";
import { createLogger } from "../utils/logging.js";

const logger = createLogger("run_tests");

export const RunTestsSchema = z.object({
  command: z.string().min(1, "command must not be empty"),
});

export interface RunTestsResult {
  exit_code: number;
  stdout: string;
  stderr: string;
}

// ---------------------------------------------------------------------------
// Fixed execution parameters — never overridden by external input.
// ---------------------------------------------------------------------------

/**
 * The only pytest invocation this tool will ever run.
 * External callers cannot append, remove, or replace any of these flags.
 */
const PYTEST_FLAGS: readonly string[] = [
  "-m",
  "pytest",
  "-q",
  "--disable-warnings",
  "--maxfail=1",
];

const TIMEOUT_MS = 60_000;

// ---------------------------------------------------------------------------
// Command validation
// ---------------------------------------------------------------------------

/**
 * Exact set of accepted command strings.
 * Only bare invocations are permitted — no additional arguments allowed.
 */
const ALLOWED_COMMANDS = new Set([
  "pytest",
  "python -m pytest",
  "python3 -m pytest",
]);

/**
 * Validates that `command` is one of the exact allowed strings.
 * Any extra arguments (e.g. "pytest tests/") are rejected.
 */
function validateCommand(command: string): void {
  const normalized = command.trim().replace(/\s+/g, " ");
  if (!ALLOWED_COMMANDS.has(normalized)) {
    throw new Error(
      `Command not allowed: "${command}". ` +
        `Accepted (no extra arguments): ${[...ALLOWED_COMMANDS].join(" | ")}`,
    );
  }
}

// ---------------------------------------------------------------------------
// Python binary resolution
// ---------------------------------------------------------------------------

/**
 * Returns the Python binary to use.
 * Reads PYTHON_BIN from the server environment; defaults to "python".
 * Rejects values that contain whitespace to prevent argument injection.
 */
function getPythonBin(): string {
  const bin = process.env["PYTHON_BIN"];
  if (bin !== undefined && bin.trim().length > 0) {
    const trimmed = bin.trim();
    if (/\s/.test(trimmed)) {
      throw new Error(
        `PYTHON_BIN must not contain whitespace: "${trimmed}"`,
      );
    }
    return trimmed;
  }
  return "python";
}

// ---------------------------------------------------------------------------
// Spawn-based execution (no shell)
// ---------------------------------------------------------------------------

/**
 * Spawns `pythonBin PYTEST_FLAGS` in `cwd` without a shell.
 * Always resolves — never rejects.
 */
function spawnPytest(
  pythonBin: string,
  cwd: string,
): Promise<RunTestsResult> {
  return new Promise((resolve) => {
    const child = spawn(pythonBin, [...PYTEST_FLAGS], {
      cwd,
      shell: false,
      env: process.env,
    });

    let stdout = "";
    let stderr = "";
    let settled = false;

    const settle = (result: RunTestsResult): void => {
      if (!settled) {
        settled = true;
        resolve(result);
      }
    };

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8");
    });

    // Hard timeout: resolve immediately and then kill the child.
    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      settle({
        exit_code: 1,
        stdout,
        stderr: `${stderr}[Timeout: process killed after ${TIMEOUT_MS}ms]`,
      });
    }, TIMEOUT_MS);

    child.on("close", (code) => {
      clearTimeout(timer);
      settle({ exit_code: code ?? 1, stdout, stderr });
    });

    child.on("error", (err) => {
      clearTimeout(timer);
      settle({ exit_code: 1, stdout, stderr: stderr || err.message });
    });
  });
}

// ---------------------------------------------------------------------------
// Tool entry point
// ---------------------------------------------------------------------------

export async function runTests(rawArgs: unknown): Promise<RunTestsResult> {
  const args = RunTestsSchema.parse(rawArgs);
  // Validate the caller's command string; the value itself is not forwarded.
  validateCommand(args.command);
  const pythonBin = getPythonBin();
  const cwd = getTargetRepo();

  const start = Date.now();
  const result = await spawnPytest(pythonBin, cwd);
  logger.log(args, Date.now() - start, JSON.stringify(result), true);
  return result;
}
