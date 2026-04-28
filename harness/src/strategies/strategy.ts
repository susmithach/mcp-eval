import type { MetricsTracker } from "../runner/metrics.js";
import type { ResultSchema, TaskType } from "../runner/result_schema.js";

export interface StrategyContext {
  task_id: string;
  task_type: TaskType;
  expected_failing_tests: string[];
  metrics: MetricsTracker;
}

export interface Strategy {
  run(ctx: StrategyContext): Promise<ResultSchema>;
}
