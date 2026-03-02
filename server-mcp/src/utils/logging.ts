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
