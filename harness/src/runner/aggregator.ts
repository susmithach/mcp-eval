import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import type { ResultSchema, TaskType } from "./result_schema.js";

// ---------------------------------------------------------------------------
// Summary schema
// ---------------------------------------------------------------------------

export interface RunSummary {
  task_id: string;
  task_type: TaskType;
  strategy: string;
  runs: number;
  success_rate: number;
  avg_runtime_ms: number;
  avg_iterations: number;
  avg_tool_calls_total: number;
  avg_tokens_in: number;
  avg_tokens_out: number;
}

// ---------------------------------------------------------------------------
// Computation
// ---------------------------------------------------------------------------

function avg(values: number[]): number {
  if (values.length === 0) return 0;
  return Math.round(values.reduce((s, v) => s + v, 0) / values.length);
}

export function summarise(
  task_id: string,
  task_type: TaskType,
  strategy: string,
  results: ResultSchema[],
): RunSummary {
  const n = results.length;
  return {
    task_id,
    task_type,
    strategy,
    runs: n,
    success_rate: n === 0 ? 0 : results.filter((r) => r.success).length / n,
    avg_runtime_ms: avg(results.map((r) => r.runtime_ms)),
    avg_iterations: avg(results.map((r) => r.iterations)),
    avg_tool_calls_total: avg(results.map((r) => r.tool_calls_total)),
    avg_tokens_in: avg(results.map((r) => r.tokens_in)),
    avg_tokens_out: avg(results.map((r) => r.tokens_out)),
  };
}

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------

export async function saveSummary(
  resultsDir: string,
  task_id: string,
  strategy: string,
  summary: RunSummary,
): Promise<void> {
  const dir = resolve(resultsDir, task_id, strategy);
  await mkdir(dir, { recursive: true });
  const file = resolve(resultsDir, task_id, strategy, "summary.json");
  await writeFile(file, JSON.stringify(summary, null, 2) + "\n", "utf8");
}
