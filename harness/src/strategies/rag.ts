import { createLlmProvider } from "../llm/provider.js";
import { McpHarnessClient } from "../mcp/client.js";
import { buildRagIndex } from "../rag/indexer.js";
import { retrieveRelevantChunks } from "../rag/retriever.js";
import { loadPrompt } from "../runner/prompt_loader.js";
import type { ResultSchema } from "../runner/result_schema.js";
import type { Strategy, StrategyContext } from "./strategy.js";

const MAX_TOKENS = 8096;
const TOP_K = 6;

function extractPatch(text: string): string | null {
  const tagged = text.match(/<patch>([\s\S]*?)<\/patch>/);
  if (tagged) return tagged[1].trim();

  const fenced = text.match(/```(?:diff|patch)?\n([\s\S]*?)\n```/);
  if (fenced) return fenced[1].trim();

  return null;
}

function buildRetrievalQuery(ctx: StrategyContext, testOutput: string): string {
  return [
    `Task ID: ${ctx.task_id}`,
    `Task type: ${ctx.task_type}`,
    "Expected failing tests:",
    ...ctx.expected_failing_tests,
    "",
    "Observed test output:",
    testOutput,
  ].join("\n");
}

function buildRetrievedContext(
  chunks: ReturnType<typeof retrieveRelevantChunks>,
): string {
  return chunks
    .map(
      ({ chunk, score }) =>
        `=== ${chunk.path}:${chunk.startLine}-${chunk.endLine} | score=${score.toFixed(4)} ===\n${chunk.text}`,
    )
    .join("\n\n");
}

function buildUserMessage(
  ctx: StrategyContext,
  testOutput: string,
  retrievedContext: string,
): string {
  const fixTarget =
    ctx.task_type === "test_fix"
      ? "Fix only the failing test file(s). Do not modify production source files."
      : "Fix only the production code. Do not modify test files.";

  return [
    "Here is the current task-specific test output:",
    "```",
    testOutput,
    "```",
    "",
    "Here are the retrieved repository chunks relevant to this task:",
    "",
    retrievedContext,
    "",
    fixTarget,
    "Use only the retrieved context plus the failing test output to prepare the smallest correct patch.",
    "Please provide your fix as a unified diff patch wrapped in <patch>...</patch> tags.",
    "Output only the patch inside the tags and no extra explanation.",
  ].join("\n");
}

export class RagStrategy implements Strategy {
  async run(ctx: StrategyContext): Promise<ResultSchema> {
    const client = new McpHarnessClient();
    let testsPassed = false;
    let runError: string | undefined;

    try {
      await client.connect();

      const initialTests = await client.runTests(ctx.expected_failing_tests);
      const testOutput = [
        initialTests.stdout,
        initialTests.stderr,
      ]
        .filter(Boolean)
        .join("\n")
        .trim() || "(no output)";

      const index = await buildRagIndex();
      const retrievalQuery = buildRetrievalQuery(ctx, testOutput);
      const retrievedChunks = retrieveRelevantChunks(index, retrievalQuery, {
        topK: TOP_K,
      });
      const retrievedContext = buildRetrievedContext(retrievedChunks);

      const systemPrompt = await loadPrompt(ctx.task_type, ctx.task_id);
      const userMessage = buildUserMessage(ctx, testOutput, retrievedContext);
      const { provider } = createLlmProvider();

      ctx.metrics.incrementIterations();

      const response = await provider.createText({
        systemPrompt,
        userMessage,
        maxTokens: MAX_TOKENS,
      });

      ctx.metrics.addTokens(
        response.usage.inputTokens,
        response.usage.outputTokens,
      );

      const patch = extractPatch(response.text);
      if (patch) {
        await client.applyPatch(patch);
      }

      const finalTests = await client.runTests(ctx.expected_failing_tests);
      ctx.metrics.recordToolCall("run_tests");
      testsPassed = finalTests.passed;

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
