import { McpHarnessClient } from "../mcp/client.js";
import { createLlmProvider } from "../llm/provider.js";
import type { LlmConversationMessage } from "../llm/types.js";
import { loadPrompt } from "../runner/prompt_loader.js";
import type { ResultSchema } from "../runner/result_schema.js";
import type { Strategy, StrategyContext } from "./strategy.js";
import { MCP_TOOL_DEFINITIONS, dispatchTool } from "./mcp_tools.js";

const MAX_TOKENS = 8096;
const MAX_ITERATIONS = 20;

export class McpStrategy implements Strategy {
  async run(ctx: StrategyContext): Promise<ResultSchema> {
    const client = new McpHarnessClient();
    let testsPassed = false;
    let runError: string | undefined;

    try {
      await client.connect();

      const systemPrompt = await loadPrompt(ctx.task_type, ctx.task_id);
      const { provider } = createLlmProvider();

      const messages: LlmConversationMessage[] = [
        {
          role: "user",
          kind: "text",
          text:
            "Please begin. Use run_tests to see what is currently failing, then read the relevant source files and fix the code.",
        },
      ];

      let iterations = 0;

      while (iterations < MAX_ITERATIONS) {
        ctx.metrics.incrementIterations();
        iterations++;

        const response = await provider.createToolResponse({
          systemPrompt,
          messages,
          tools: MCP_TOOL_DEFINITIONS,
          maxTokens: MAX_TOKENS,
        });

        ctx.metrics.addTokens(
          response.usage.inputTokens,
          response.usage.outputTokens,
        );

        messages.push({
          role: "assistant",
          kind: "assistant",
          text: response.text,
          toolCalls: response.toolCalls,
        });

        if (response.toolCalls.length === 0) break;

        const toolResults = await Promise.all(
          response.toolCalls.map(async (toolCall) => {
            ctx.metrics.recordToolCall(toolCall.name);
            const content = await dispatchTool(
              client,
              toolCall.name,
              toolCall.input,
            );
            return {
              toolCallId: toolCall.id,
              content,
            };
          }),
        );

        messages.push({
          role: "user",
          kind: "tool_results",
          results: toolResults,
        });
      }

      // Ground-truth success check — independent of what Claude claims
      const finalTests = await client.runTests();
      ctx.metrics.recordToolCall("run_tests");
      testsPassed = finalTests.passed;

      // Capture what changed
      const diff = await client.gitDiff();
      ctx.metrics.recordToolCall("git_diff");
      ctx.metrics.setFinalDiff(diff.diff);
    } catch (err) {
      runError = err instanceof Error ? err.message : String(err);
    } finally {
      await client.close();
    }

    return ctx.metrics.finish(
      ctx.task_type,
      runError === undefined ? testsPassed : false,
      runError,
    );
  }
}
