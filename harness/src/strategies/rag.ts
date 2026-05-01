import { createLlmProvider } from "../llm/provider.js";
import { McpHarnessClient } from "../mcp/client.js";
import { buildRagIndex } from "../rag/indexer.js";
import { retrieveRelevantChunks } from "../rag/retriever.js";
import { loadPrompt } from "../runner/prompt_loader.js";
import type { ResultSchema } from "../runner/result_schema.js";
import type { Strategy, StrategyContext } from "./strategy.js";
import { extractPatch } from "./patch_extractor.js";

const MAX_TOKENS = 8096;
const TOP_K = 6;
const MAX_ITERATIONS = 3;

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

function extractFailureHighlights(testOutput: string): string[] {
  const lines = testOutput
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const highlights: string[] = [];
  for (const line of lines) {
    if (
      line.startsWith("E       ") ||
      line.startsWith("E   ") ||
      line.startsWith(">") ||
      line.includes("AssertionError") ||
      line.includes("FAILED ") ||
      line.includes("::")
    ) {
      highlights.push(line);
    }
  }

  return highlights.slice(0, 12);
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
  const failureHighlights = extractFailureHighlights(testOutput);
  let fixTarget: string;
  let groundingInstruction: string;

  if (ctx.task_type === "test_fix") {
    fixTarget =
      "Fix only the failing test file(s). Do not modify production source files.";
    groundingInstruction =
      "Treat the observed production behavior from the failing test output as ground truth. Use the retrieved context to identify the wrong assertion or expected value and correct only the test.";
  } else if (ctx.task_type === "feature") {
    fixTarget =
      "Fix only the production code. Do not modify test files.";
    groundingInstruction =
      "The failing tests define the expected feature behavior. Use the retrieved context to implement the missing logic with the smallest production-code patch that satisfies those tests.";
  } else {
    fixTarget =
      "Fix only the production code. Do not modify test files.";
    groundingInstruction =
      "The failing tests are the ground truth. The retrieved source code may already contain the injected bug, so do not copy its current behavior blindly. Infer the minimal correction from the test expectations and the surrounding implementation patterns.";
  }

  return [
    "Expected failing tests:",
    ...ctx.expected_failing_tests.map((testId) => `- ${testId}`),
    "",
    "Observed failure highlights:",
    ...(failureHighlights.length > 0 ? failureHighlights : ["(no condensed highlights extracted)"]),
    "",
    "Full task-specific test output:",
    "```",
    testOutput,
    "```",
    "",
    "Retrieved repository chunks relevant to this task:",
    "",
    retrievedContext,
    "",
    fixTarget,
    groundingInstruction,
    "Use the failing tests and assertion output as the primary truth for intended behavior.",
    "Treat the retrieved code as evidence that may already include the injected bug.",
    "Use only the retrieved context plus the failing test output to prepare the smallest correct patch.",
    "Please provide your fix as a unified diff patch wrapped in <patch>...</patch> tags.",
    "Output only the patch inside the tags and no extra explanation.",
  ].join("\n");
}

function countRetrievedChars(
  chunks: ReturnType<typeof retrieveRelevantChunks>,
): number {
  return chunks.reduce((sum, item) => sum + item.chunk.text.length, 0);
}

function countRetrievedLines(
  chunks: ReturnType<typeof retrieveRelevantChunks>,
): number {
  return chunks.reduce(
    (sum, item) => sum + (item.chunk.text.length === 0 ? 0 : item.chunk.text.split("\n").length),
    0,
  );
}

export class RagStrategy implements Strategy {
  async run(ctx: StrategyContext): Promise<ResultSchema> {
    const client = new McpHarnessClient();
    let testsPassed = false;
    let runError: string | undefined;

    try {
      await client.connect();

      const index = await buildRagIndex();
      const systemPrompt = await loadPrompt(ctx.task_type, ctx.task_id);
      const { provider, config: llmConfig } = createLlmProvider();

      let latestTests = await client.runTests(ctx.expected_failing_tests);
      testsPassed = latestTests.passed;
      ctx.metrics.setFinalTestsPassed(testsPassed);
      let patchGenerated = false;
      let patchApplied = false;
      const retrievedPaths = new Set<string>();
      let retrievedChunksCount = 0;
      let retrievedChars = 0;
      let retrievedLines = 0;

      for (let iteration = 0; iteration < MAX_ITERATIONS; iteration++) {
        if (testsPassed) {
          break;
        }

        const testOutput = [
          latestTests.stdout,
          latestTests.stderr,
        ]
          .filter(Boolean)
          .join("\n")
          .trim() || "(no output)";

        const retrievalQuery = buildRetrievalQuery(ctx, testOutput);
        const retrievedChunks = retrieveRelevantChunks(index, retrievalQuery, {
          topK: TOP_K,
        });
        retrievedChunksCount += retrievedChunks.length;
        retrievedChars += countRetrievedChars(retrievedChunks);
        retrievedLines += countRetrievedLines(retrievedChunks);
        for (const item of retrievedChunks) {
          retrievedPaths.add(item.chunk.path);
        }
        const retrievedContext = buildRetrievedContext(retrievedChunks);
        const userMessage = buildUserMessage(ctx, testOutput, retrievedContext);

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

        const patch = extractPatch(response.text, llmConfig.providerName, llmConfig.model);
        if (!patch) {
          break;
        }
        patchGenerated = true;

        const applied = await client.applyPatch(patch);
        if (applied.applied) {
          patchApplied = true;
        }
        latestTests = await client.runTests(ctx.expected_failing_tests);
        testsPassed = latestTests.passed;
        ctx.metrics.setFinalTestsPassed(testsPassed);
      }

      ctx.metrics.setPatchGenerated(patchGenerated);
      ctx.metrics.setPatchApplied(patchApplied);
      ctx.metrics.setRetrievalMetrics({
        retrieved_chunks_count: retrievedChunksCount,
        retrieved_files_count: retrievedPaths.size,
        retrieved_paths: [...retrievedPaths].sort(),
      });
      ctx.metrics.setContextMetrics({
        context_files_count: retrievedPaths.size,
        context_source_files_count: [...retrievedPaths].filter((path) => path.startsWith("pyservicelab/")).length,
        context_test_files_count: [...retrievedPaths].filter((path) => path.startsWith("tests/")).length,
        context_total_chars: retrievedChars,
        context_total_lines: retrievedLines,
      });

      const diff = await client.gitDiff();
      ctx.metrics.recordToolCall("run_tests");
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
