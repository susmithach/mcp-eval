import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, "../..");
const DEFAULT_ENV_FILE = resolve(PROJECT_ROOT, ".env");

function stripWrappingQuotes(value: string): string {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

export function loadProjectEnv(envFile = DEFAULT_ENV_FILE): void {
  if (!existsSync(envFile)) return;

  const raw = readFileSync(envFile, "utf8");
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed.length === 0 || trimmed.startsWith("#")) continue;

    const separatorIndex = trimmed.indexOf("=");
    if (separatorIndex <= 0) continue;

    const key = trimmed.slice(0, separatorIndex).trim();
    if (!key) continue;

    const value = stripWrappingQuotes(trimmed.slice(separatorIndex + 1).trim());
    if (process.env[key] === undefined) {
      process.env[key] = value;
    }
  }
}
