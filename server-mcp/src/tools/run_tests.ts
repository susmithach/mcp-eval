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
