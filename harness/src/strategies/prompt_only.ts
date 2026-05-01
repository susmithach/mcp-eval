import { createLlmProvider } from "../llm/provider.js";
import { McpHarnessClient } from "../mcp/client.js";
import { loadPrompt } from "../runner/prompt_loader.js";
import type { ResultSchema } from "../runner/result_schema.js";
import type { Strategy, StrategyContext } from "./strategy.js";
import { extractPatch } from "./patch_extractor.js";

const MAX_TOKENS = 8096;

// ---------------------------------------------------------------------------
// Recursive source file collector
// Not counted as LLM tool calls — this is harness-side context building.
// ---------------------------------------------------------------------------

async function collectPythonFiles(
  client: McpHarnessClient,
  dir: string,
  depth = 0,
  maxDepth = 3,
): Promise<Map<string, string>> {
  const result = new Map<string, string>();
  if (depth > maxDepth) return result;

  let listing: { files: string[]; directories: string[] };
  try {
    listing = await client.listFiles(dir);
  } catch {
    return result;
  }

  for (const file of listing.files.filter((f) => f.endsWith(".py"))) {
    const filePath = `${dir}/${file}`;
    try {
      const { content } = await client.readFile(filePath);
      result.set(filePath, content);
    } catch {
      // skip unreadable files
    }
  }

  for (const subdir of listing.directories.filter((d) => d !== "__pycache__")) {
    const subdirPath = `${dir}/${subdir}`;
    const sub = await collectPythonFiles(client, subdirPath, depth + 1, maxDepth);
    for (const [k, v] of sub) result.set(k, v);
  }

  return result;
}

async function readKnownFiles(
  client: McpHarnessClient,
  paths: string[],
): Promise<Map<string, string>> {
  const result = new Map<string, string>();
  for (const path of paths) {
    try {
      const { content } = await client.readFile(path);
      result.set(path, content);
    } catch {
      // skip unreadable files
    }
  }
  return result;
}

function testNodeIdToPath(testNodeId: string): string {
  const [path] = testNodeId.split("::");
  return path ?? testNodeId;
}

function countTotalChars(files: Map<string, string>): number {
  return [...files.values()].reduce((sum, content) => sum + content.length, 0);
}

function countTotalLines(files: Map<string, string>): number {
  return [...files.values()].reduce(
    (sum, content) => sum + (content.length === 0 ? 0 : content.split("\n").length),
    0,
  );
}

// ---------------------------------------------------------------------------
// Strategy
// ---------------------------------------------------------------------------

export class PromptOnlyStrategy implements Strategy {
  async run(ctx: StrategyContext): Promise<ResultSchema> {
    const client = new McpHarnessClient();
    let testsPassed = false;
    let runError: string | undefined;

    try {
      await client.connect();

      // 1. Run tests to get current failing output (harness call, not counted)
      const initialTests = await client.runTests(ctx.expected_failing_tests);

      // 2. Collect fixed static context:
      //    - all production Python files
      //    - only the expected failing test files
      const sourceFiles = new Map<string, string>();
      const productionFiles = await collectPythonFiles(client, "pyservicelab");
      for (const [k, v] of productionFiles) sourceFiles.set(k, v);

      const failingTestPaths = [...new Set(ctx.expected_failing_tests.map(testNodeIdToPath))];
      const failingTestFiles = await readKnownFiles(client, failingTestPaths);
      for (const [k, v] of failingTestFiles) sourceFiles.set(k, v);
      ctx.metrics.setContextMetrics({
        context_files_count: sourceFiles.size,
        context_source_files_count: productionFiles.size,
        context_test_files_count: failingTestFiles.size,
        context_total_chars: countTotalChars(sourceFiles),
        context_total_lines: countTotalLines(sourceFiles),
      });

      // 3. Build user message
      const testOutput = [
        initialTests.stdout,
        initialTests.stderr,
      ]
        .filter(Boolean)
        .join("\n")
        .trim() || "(no output)";

      const fileContext = [...sourceFiles.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([path, content]) => `=== ${path} ===\n${content}`)
        .join("\n\n");

      const userMessage = [
        "Expected failing tests:",
        ...ctx.expected_failing_tests.map((testId) => `- ${testId}`),
        "",
        "Here is the current task-specific test output:",
        "```",
        testOutput,
        "```",
        "",
        "Here is the fixed static repository context for this task:",
        "",
        fileContext,
        "",
        "Please provide your fix as a unified diff patch wrapped in <patch>...</patch> tags.",
        "Output only the patch inside the tags — no explanation needed outside them.",
      ].join("\n");

      // 4. Single Claude API call — no tools
      const systemPrompt = await loadPrompt(ctx.task_type, ctx.task_id);
      const { provider, config: llmConfig } = createLlmProvider();

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

      // 5. Extract and apply the patch
      const patch = extractPatch(response.text, llmConfig.providerName, llmConfig.model);
      ctx.metrics.setPatchGenerated(patch !== null);
      if (patch) {
        const applied = await client.applyPatch(patch);
        ctx.metrics.setPatchApplied(applied.applied);
        // Application errors are non-fatal — final tests determine success
      }

      // 6. Ground-truth success check
      const finalTests = await client.runTests(ctx.expected_failing_tests);
      ctx.metrics.recordToolCall("run_tests");
      testsPassed = finalTests.passed;
      ctx.metrics.setFinalTestsPassed(testsPassed);

      // 7. Capture final diff
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
