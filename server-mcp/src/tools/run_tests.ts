import { spawn } from "child_process";
import { z } from "zod";
import { getTargetRepo } from "../utils/file_utils.js";
import { createLogger } from "../utils/logging.js";

const logger = createLogger("run_tests");

export const RunTestsSchema = z.object({
  command: z.string().min(1, "command must not be empty"),
  tests: z.array(z.string().min(1)).optional(),
});

export interface RunTestsResult {
  exit_code: number;
  stdout: string;
  stderr: string;
}

// these flags are hardcoded — callers can't add or change them
const PYTEST_FLAGS: readonly string[] = [
  "-m",
  "pytest",
  "-q",
  "--disable-warnings",
  "--maxfail=1",
];

const TIMEOUT_MS = 60_000;

// only bare invocations — no extra args
const ALLOWED_COMMANDS = new Set([
  "pytest",
  "python -m pytest",
  "python3 -m pytest",
]);

function validateCommand(command: string): void {
  const normalized = command.trim().replace(/\s+/g, " ");
  if (!ALLOWED_COMMANDS.has(normalized)) {
    throw new Error(
      `Command not allowed: "${command}". ` +
        `Accepted (no extra arguments): ${[...ALLOWED_COMMANDS].join(" | ")}`,
    );
  }
}

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

function validateTestNodeIds(tests: string[] | undefined): string[] {
  if (!tests) return [];
  return tests.map((test) => {
    const trimmed = test.trim();
    if (trimmed.length === 0) {
      throw new Error("Test node ids must not be empty");
    }
    if (trimmed.startsWith("-")) {
      throw new Error(`Test node id must not start with '-': "${trimmed}"`);
    }
    if (/\s/.test(trimmed)) {
      throw new Error(`Test node id must not contain whitespace: "${trimmed}"`);
    }
    return trimmed;
  });
}

function spawnPytest(
  pythonBin: string,
  cwd: string,
  testNodeIds: string[],
): Promise<RunTestsResult> {
  return new Promise((resolve) => {
    const child = spawn(pythonBin, [...PYTEST_FLAGS, ...testNodeIds], {
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

export async function runTests(rawArgs: unknown): Promise<RunTestsResult> {
  const args = RunTestsSchema.parse(rawArgs);
  validateCommand(args.command);
  const pythonBin = getPythonBin();
  const cwd = getTargetRepo();
  const testNodeIds = validateTestNodeIds(args.tests);

  const start = Date.now();
  const result = await spawnPytest(pythonBin, cwd, testNodeIds);
  logger.log(args, Date.now() - start, JSON.stringify(result), true);
  return result;
}
