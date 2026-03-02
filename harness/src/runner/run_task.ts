import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { McpHarnessClient } from "../mcp/client.js";
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
}

// ---------------------------------------------------------------------------
// Pipeline
// ---------------------------------------------------------------------------

export async function runTask(params: RunTaskParams): Promise<ResultSchema> {
  const { task_id, task_patch_file, strategy_name, run_id } = params;
  const metrics = new MetricsTracker();
  const client = new McpHarnessClient();

  let testsPassed = false;
  let runError: string | undefined;

  try {
    // 1) Reset repo to clean baseline
    await resetRepo();

    // 2) Apply the task patch
    await applyTask(task_patch_file);

    // 3–5) MCP operations — close() is guaranteed via finally
    await client.connect();
    try {
      // Iteration 1: run tests, record outcome
      metrics.incrementIterations();
      const testResult = await client.runTests();
      metrics.recordToolCall("run_tests");
      testsPassed = testResult.passed;

      // Iteration 2: inspect diff
      metrics.incrementIterations();
      await client.gitDiff();
      metrics.recordToolCall("git_diff");
    } finally {
      await client.close();
    }
  } catch (err) {
    runError = err instanceof Error ? err.message : String(err);
  }

  // 6) Persist result
  const result = metrics.finish(
    runError === undefined ? testsPassed : false,
    runError,
  );
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
