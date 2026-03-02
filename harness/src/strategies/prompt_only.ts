import type { ResultSchema } from "../runner/result_schema.js";
import type { Strategy, StrategyContext } from "./strategy.js";

export class PromptOnlyStrategy implements Strategy {
  async run(ctx: StrategyContext): Promise<ResultSchema> {
    // Placeholder: LLM call will be implemented here in a later step.
    // No MCP tools are invoked.
    ctx.metrics.incrementIterations();
    return ctx.metrics.finish(false);
  }
}
