import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { Strategy } from "../strategies/strategy.js";
import { MetricsTracker } from "./metrics.js";
import type { ResultSchema, TaskType } from "./result_schema.js";
import { applyTask, resetRepo } from "./repo.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
// dist/runner/ → ../../ = harness root (where results/ lives)
const HARNESS_ROOT = resolve(__dirname, "../..");

export interface RunTaskParams {
  task_id: string;
  task_patch_file: string;
  task_type: TaskType;
  expected_failing_tests: string[];
  strategy_name: string;
  run_id: string;
  strategy: Strategy;
}

export async function runTask(params: RunTaskParams): Promise<ResultSchema> {
  const {
    task_id,
    task_patch_file,
    task_type,
    expected_failing_tests,
    strategy_name,
    run_id,
    strategy,
  } = params;
  const metrics = new MetricsTracker();

  try {
    await resetRepo();
    await applyTask(task_patch_file);
  } catch (err) {
    const result = metrics.finish(
      task_type,
      false,
      err instanceof Error ? err.message : String(err),
    );
    await saveResult(task_id, strategy_name, run_id, result);
    return result;
  }

  const result = await strategy.run({
    task_id,
    task_type,
    expected_failing_tests,
    metrics,
  });

  await saveResult(task_id, strategy_name, run_id, result);
  return result;
}

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
