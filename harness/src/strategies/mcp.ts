import { McpHarnessClient } from "../mcp/client.js";
import { createLlmProvider } from "../llm/provider.js";
import type { LlmConversationMessage } from "../llm/types.js";
import { loadPrompt } from "../runner/prompt_loader.js";
import type { ResultSchema } from "../runner/result_schema.js";
import type { Strategy, StrategyContext } from "./strategy.js";
import { MCP_TOOL_DEFINITIONS, dispatchTool } from "./mcp_tools.js";

const MAX_TOKENS = 8096;
const MAX_ITERATIONS = 20;
const MAX_HISTORY_MESSAGES = 10;

function trimConversation(
  messages: LlmConversationMessage[],
): LlmConversationMessage[] {
  if (messages.length <= MAX_HISTORY_MESSAGES) return messages;
  const [firstMessage, ...rest] = messages;
  return [firstMessage, ...rest.slice(-(MAX_HISTORY_MESSAGES - 1))];
}

function buildRunInstruction(ctx: StrategyContext): string {
  const tests = ctx.expected_failing_tests.join(", ");

  if (ctx.task_type === "test_fix") {
    return (
      "Please begin. Focus on these expected failing tests first: " +
      `${tests}. ` +
      "Use run_tests on those task tests first, then inspect the failing test file and the minimal related production code needed to understand the correct behavior. " +
      "Fix only the test file. Do not modify production source files for this task type. " +
      "When the traceback already shows a wrong expected literal or assertion target in the test, prefer correcting that test expectation directly before doing broader exploration. " +
      "If a test creates N explicit objects in setup and then asserts a count, treat that setup count as the strongest clue for the correct expected value unless nearby production code clearly adds more. " +
      "If a run_tests call omits tests, it will still run the task's expected failing tests, so stay scoped to them. " +
      "Once you identify the incorrect assertion or expected value, stop exploring and apply the smallest test-only patch that makes those task tests pass. " +
      "Use only these exact tool names: list_files, read_file, search_in_files, run_tests, apply_patch, git_diff. " +
      "After each patch, rerun run_tests on the same task tests. Stop once those tests pass."
    );
  }

  const editTarget =
    ctx.task_type === "feature" ? "production code" : "production code";

  return (
    "Please begin. Focus on these expected failing tests first: " +
    `${tests}. ` +
    "Use run_tests to run the task's expected failing tests first, then inspect only the needed files and fix the " +
    `${editTarget}. ` +
    "Prioritize the source file named in the failing traceback before exploring elsewhere. " +
    "If a run_tests call omits tests, it will still run the task's expected failing tests, so stay scoped to them. " +
    "Once you identify a likely root cause, stop exploring and apply the smallest production-code patch that makes the task tests pass. " +
    "Use only these exact tool names: list_files, read_file, search_in_files, run_tests, apply_patch, git_diff. " +
    "After each patch, rerun run_tests on the same task tests. Stop once those tests pass."
  );
}

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
          text: buildRunInstruction(ctx),
        },
      ];

      let iterations = 0;

      while (iterations < MAX_ITERATIONS) {
        ctx.metrics.incrementIterations();
        iterations++;

        const response = await provider.createToolResponse({
          systemPrompt,
          messages: trimConversation(messages),
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
            const toolInput =
              toolCall.name === "run_tests" &&
              (!Array.isArray(toolCall.input["tests"]) ||
                toolCall.input["tests"].length === 0)
                ? { ...toolCall.input, tests: ctx.expected_failing_tests }
                : toolCall.input;
            const result = await dispatchTool(
              client,
              toolCall.name,
              toolInput,
            );
            if (result.name) {
              ctx.metrics.recordToolCall(result.name);
            }
            return {
              toolCallId: toolCall.id,
              content: result.content,
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
      const finalTests = await client.runTests(ctx.expected_failing_tests);
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
