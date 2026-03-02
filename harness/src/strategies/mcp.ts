import { McpHarnessClient } from "../mcp/client.js";
import type { ResultSchema } from "../runner/result_schema.js";
import type { Strategy, StrategyContext } from "./strategy.js";

export class McpStrategy implements Strategy {
  async run(ctx: StrategyContext): Promise<ResultSchema> {
    const client = new McpHarnessClient();
    let testsPassed = false;
    let runError: string | undefined;

    try {
      await client.connect();
      try {
        // Iteration 1: run tests, record outcome
        ctx.metrics.incrementIterations();
        const tests = await client.runTests();
        ctx.metrics.recordToolCall("run_tests");
        testsPassed = tests.passed;

        // Iteration 2: inspect diff
        ctx.metrics.incrementIterations();
        await client.gitDiff();
        ctx.metrics.recordToolCall("git_diff");
      } finally {
        await client.close();
      }
    } catch (err) {
      runError = err instanceof Error ? err.message : String(err);
    }

    return ctx.metrics.finish(
      runError === undefined ? testsPassed : false,
      runError,
    );
  }
}
