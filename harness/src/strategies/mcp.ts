import Anthropic from "@anthropic-ai/sdk";
import type { MessageParam, ToolUseBlock } from "@anthropic-ai/sdk/resources/messages.js";
import { McpHarnessClient } from "../mcp/client.js";
import { loadPrompt } from "../runner/prompt_loader.js";
import type { ResultSchema } from "../runner/result_schema.js";
import type { Strategy, StrategyContext } from "./strategy.js";
import { MCP_TOOL_DEFINITIONS, dispatchTool } from "./mcp_tools.js";

const MODEL = "claude-sonnet-4-6";
const MAX_TOKENS = 8096;
const MAX_ITERATIONS = 20;

export class McpStrategy implements Strategy {
  async run(ctx: StrategyContext): Promise<ResultSchema> {
    if (!process.env["ANTHROPIC_API_KEY"]) {
      throw new Error("ANTHROPIC_API_KEY environment variable is not set");
    }

    const client = new McpHarnessClient();
    let testsPassed = false;
    let runError: string | undefined;

    try {
      await client.connect();

      const systemPrompt = await loadPrompt(ctx.task_type, ctx.task_id);
      const anthropic = new Anthropic();

      const messages: MessageParam[] = [
        {
          role: "user",
          content:
            "Please begin. Use run_tests to see what is currently failing, then read the relevant source files and fix the code.",
        },
      ];

      let iterations = 0;

      while (iterations < MAX_ITERATIONS) {
        ctx.metrics.incrementIterations();
        iterations++;

        const response = await anthropic.messages.create({
          model: MODEL,
          max_tokens: MAX_TOKENS,
          system: systemPrompt,
          tools: MCP_TOOL_DEFINITIONS,
          messages,
        });

        ctx.metrics.addTokens(
          response.usage.input_tokens,
          response.usage.output_tokens,
        );

        // Append assistant turn to conversation history
        messages.push({ role: "assistant", content: response.content });

        // If Claude made no tool calls, it's done
        if (response.stop_reason !== "tool_use") break;

        // Process every tool_use block in this response
        const toolUseBlocks = response.content.filter(
          (b): b is ToolUseBlock => b.type === "tool_use",
        );

        const toolResults = await Promise.all(
          toolUseBlocks.map(async (block) => {
            ctx.metrics.recordToolCall(block.name);
            const result = await dispatchTool(
              client,
              block.name,
              block.input as Record<string, unknown>,
            );
            // Attach the correct tool_use_id for this specific block
            return { ...result, tool_use_id: block.id };
          }),
        );

        messages.push({ role: "user", content: toolResults });
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
