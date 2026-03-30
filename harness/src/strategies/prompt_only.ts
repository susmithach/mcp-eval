import { McpHarnessClient } from "../mcp/client.js";
import type { ResultSchema } from "../runner/result_schema.js";
import type { Strategy, StrategyContext } from "./strategy.js";

export class PromptOnlyStrategy implements Strategy {
  async run(ctx: StrategyContext): Promise<ResultSchema> {
    // Placeholder: LLM call will be implemented here in a later step.
    // No MCP tools are invoked by the LLM — the harness captures the final
    // diff directly after the strategy completes.
    ctx.metrics.incrementIterations();

    const client = new McpHarnessClient();
    try {
      await client.connect();
      const diff = await client.gitDiff();
      ctx.metrics.setFinalDiff(diff.diff);
    } catch {
      // Non-fatal: missing diff does not affect success determination
    } finally {
      await client.close();
    }

    return ctx.metrics.finish(ctx.task_type, false);
  }
}
