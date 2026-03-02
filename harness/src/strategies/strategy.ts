import type { MetricsTracker } from "../runner/metrics.js";
import type { ResultSchema } from "../runner/result_schema.js";

export interface StrategyContext {
  task_id: string;
  metrics: MetricsTracker;
}

export interface Strategy {
  run(ctx: StrategyContext): Promise<ResultSchema>;
}
