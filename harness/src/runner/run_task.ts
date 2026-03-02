import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { Strategy } from "../strategies/strategy.js";
import { MetricsTracker } from "./metrics.js";
import type { ResultSchema } from "./result_schema.js";
import { applyTask, resetRepo } from "./repo.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
// dist/runner/ → ../../ = harness root (where results/ lives)
const HARNESS_ROOT = resolve(__dirname, "../..");

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RunTaskParams {
  task_id: string;
  task_patch_file: string;
  strategy_name: string;
  run_id: string;
  strategy: Strategy;
}

// ---------------------------------------------------------------------------
// Pipeline
// ---------------------------------------------------------------------------

export async function runTask(params: RunTaskParams): Promise<ResultSchema> {
  const { task_id, task_patch_file, strategy_name, run_id, strategy } = params;
  const metrics = new MetricsTracker();

  // 1–2) Repo setup — short-circuit with error result if this fails
  try {
    await resetRepo();
    await applyTask(task_patch_file);
  } catch (err) {
    const result = metrics.finish(
      false,
      err instanceof Error ? err.message : String(err),
    );
    await saveResult(task_id, strategy_name, run_id, result);
    return result;
  }

  // 3–5) Delegate to strategy — strategy owns its own error handling
  //      and calls metrics.finish() exactly once before returning
  const result = await strategy.run({ task_id, metrics });

  // 6) Persist result
  await saveResult(task_id, strategy_name, run_id, result);
  return result;
}

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------

async function saveResult(
  task_id: string,
  strategy_name: string,
  run_id: string,
  result: ResultSchema,
): Promise<void> {
  const dir = resolve(HARNESS_ROOT, "results", task_id, strategy_name);
  await mkdir(dir, { recursive: true });
  const file = resolve(dir, `${run_id}.json`);
  await writeFile(file, JSON.stringify(result, null, 2) + "\n", "utf8");
}
