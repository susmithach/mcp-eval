import type { McpHarnessClient } from "../mcp/client.js";
import { createLlmProvider } from "../llm/provider.js";
import { McpHarnessClient as McpClient } from "../mcp/client.js";
import { loadPrompt } from "../runner/prompt_loader.js";
import type { ResultSchema } from "../runner/result_schema.js";
import type { Strategy, StrategyContext } from "./strategy.js";

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

// ---------------------------------------------------------------------------
// Patch extraction — tries <patch>...</patch> then ```diff fenced blocks
// ---------------------------------------------------------------------------

function extractPatch(text: string): string | null {
  const tagged = text.match(/<patch>([\s\S]*?)<\/patch>/);
  if (tagged) return tagged[1].trim();

  const fenced = text.match(/```(?:diff|patch)?\n([\s\S]*?)\n```/);
  if (fenced) return fenced[1].trim();

  return null;
}

// ---------------------------------------------------------------------------
// Strategy
// ---------------------------------------------------------------------------

export class PromptOnlyStrategy implements Strategy {
  async run(ctx: StrategyContext): Promise<ResultSchema> {
    const client = new McpClient();
    let testsPassed = false;
    let runError: string | undefined;

    try {
      await client.connect();

      // 1. Run tests to get current failing output (harness call, not counted)
      const initialTests = await client.runTests();

      // 2. Collect all Python source and test files for context
      const sourceFiles = new Map<string, string>();
      for (const root of ["pyservicelab", "tests"]) {
        const files = await collectPythonFiles(client, root);
        for (const [k, v] of files) sourceFiles.set(k, v);
      }

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
        "Here is the current test output:",
        "```",
        testOutput,
        "```",
        "",
        "Here are all the source files:",
        "",
        fileContext,
        "",
        "Please provide your fix as a unified diff patch wrapped in <patch>...</patch> tags.",
        "Output only the patch inside the tags — no explanation needed outside them.",
      ].join("\n");

      // 4. Single Claude API call — no tools
      const systemPrompt = await loadPrompt(ctx.task_type, ctx.task_id);
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

      // 5. Extract and apply the patch
      const patch = extractPatch(response.text);
      if (patch) {
        await client.applyPatch(patch);
        // Application errors are non-fatal — final tests determine success
      }

      // 6. Ground-truth success check
      const finalTests = await client.runTests();
      ctx.metrics.recordToolCall("run_tests");
      testsPassed = finalTests.passed;

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
