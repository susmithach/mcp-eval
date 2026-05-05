import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const TARGET_REPO = resolve(__dirname, "../../target-repo");

function repoVenvCandidates(): string[] {
  return [
    resolve(TARGET_REPO, ".venv/bin/python3"),
    resolve(TARGET_REPO, ".venv/bin/python"),
  ];
}

export function resolvePythonBin(): string {
  const envValue = process.env["PYTHON_BIN"]?.trim();
  const genericEnv = envValue === undefined || envValue === "" || envValue === "python" || envValue === "python3";

  if (genericEnv) {
    for (const candidate of repoVenvCandidates()) {
      if (existsSync(candidate)) return candidate;
    }
  }

  if (envValue && envValue.length > 0) {
    return envValue;
  }

  return "python3";
}
