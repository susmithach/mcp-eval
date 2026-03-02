import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
// dist/runner/ → ../../../target-repo
const TARGET_REPO = resolve(__dirname, "../../../target-repo");
const PYTHON = process.env["PYTHON_BIN"] ?? "python3";

// ---------------------------------------------------------------------------
// Internal helper
// ---------------------------------------------------------------------------

function run(cmd: string, args: string[]): Promise<void> {
  return new Promise((resolveP, rejectP) => {
    const child = spawn(cmd, args, { cwd: TARGET_REPO, shell: false });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8");
    });

    child.on("close", (code) => {
      if (code === 0) {
        resolveP();
      } else {
        rejectP(
          new Error(
            `"${cmd} ${args.join(" ")}" exited ${code}\n` +
              `stdout: ${stdout.trim()}\nstderr: ${stderr.trim()}`,
          ),
        );
      }
    });

    child.on("error", (err) => {
      rejectP(new Error(`Failed to spawn "${cmd}": ${err.message}`));
    });
  });
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function resetRepo(): Promise<void> {
  await run(PYTHON, ["scripts/reset_repo.py"]);
}

/** taskPatchFile: bare task name or name with .patch suffix, e.g. "task_01_token_expiry_bypass" */
export async function applyTask(taskPatchFile: string): Promise<void> {
  await run(PYTHON, ["scripts/apply_task.py", taskPatchFile]);
}
