import { McpHarnessClient } from "../mcp/client.js";
import { createLlmProvider } from "../llm/provider.js";
import type { LlmConversationMessage } from "../llm/types.js";
import { loadPrompt } from "../runner/prompt_loader.js";
import type { ResultSchema } from "../runner/result_schema.js";
import type { Strategy, StrategyContext } from "./strategy.js";
import { MCP_TOOL_DEFINITIONS, dispatchTool, normalizeToolName } from "./mcp_tools.js";

// Fix #4: was 8096 — raised to match RAG/Prompt so the model has enough room
// to reason about a file it just read AND format a complete patch in one turn.
const MAX_TOKENS = 16384;
const MAX_ITERATIONS = 30;
// Fix #2: window is kept small; summarizeAndTrim replaces evicted content with
// a structured memo so the model never loses track of what it already did.
const MAX_HISTORY_MESSAGES = 12;

// ---------------------------------------------------------------------------
// Fix #2 — Context summarization
// When messages exceed MAX_HISTORY_MESSAGES, extract key facts from the evicted
// turns and inject them as a compact memo rather than silently dropping them.
// This prevents the re-read loop where the model keeps re-fetching files whose
// results were trimmed away.
// ---------------------------------------------------------------------------

function extractFirstError(stdout: string): string {
  for (const line of stdout.split("\n")) {
    const t = line.trim();
    if (t.startsWith("E ") || t.includes("AssertionError") || t.includes("FAILED")) {
      return t.slice(0, 140);
    }
  }
  return stdout.slice(0, 140);
}

function buildContextSummary(evicted: LlmConversationMessage[]): string {
  const testsRun: string[] = [];
  const filesRead: string[] = [];
  const searchesRun: string[] = [];
  const patchResults: string[] = [];

  // Map tool-call id → name and input so we can label each result.
  const toolCallNames = new Map<string, string>();
  const toolCallInputs = new Map<string, Record<string, unknown>>();
  for (const msg of evicted) {
    if (msg.kind === "assistant") {
      for (const tc of msg.toolCalls) {
        toolCallNames.set(tc.id, tc.name);
        toolCallInputs.set(tc.id, tc.input);
      }
    }
  }

  for (const msg of evicted) {
    if (msg.kind !== "tool_results") continue;
    for (const result of msg.results) {
      const name = toolCallNames.get(result.toolCallId) ?? "";
      const input = toolCallInputs.get(result.toolCallId) ?? {};
      try {
        const parsed = JSON.parse(result.content) as Record<string, unknown>;
        if (name === "run_tests") {
          const passed = parsed["passed"] === true;
          const snippet = passed
            ? "PASSED"
            : `FAILED — ${extractFirstError(String(parsed["stdout"] ?? ""))}`;
          testsRun.push(snippet);
        } else if (name === "read_file") {
          const path = input["path"] as string | undefined;
          if (path) filesRead.push(path);
        } else if (name === "search_in_files") {
          const query = input["query"] as string | undefined;
          if (query) searchesRun.push(`"${query}"`);
        } else if (name === "apply_patch") {
          const applied = parsed["applied"] === true;
          const err = parsed["error"]
            ? ` (${String(parsed["error"]).slice(0, 80)})`
            : "";
          patchResults.push(applied ? "succeeded" : `failed${err}`);
        }
      } catch {
        // unparseable tool result — skip
      }
    }
  }

  if (!testsRun.length && !filesRead.length && !searchesRun.length && !patchResults.length) {
    return "";
  }

  const lines = [
    "[Summary of earlier iterations — use this to avoid repeating work]",
  ];
  if (testsRun.length) lines.push(`Test runs: ${testsRun.join("; ")}`);
  if (filesRead.length) lines.push(`Files read: ${[...new Set(filesRead)].join(", ")}`);
  if (searchesRun.length) lines.push(`Searches: ${searchesRun.join(", ")}`);
  if (patchResults.length) lines.push(`Patch attempts: ${patchResults.join("; ")}`);
  return lines.join("\n");
}

function summarizeAndTrim(
  messages: LlmConversationMessage[],
): LlmConversationMessage[] {
  if (messages.length <= MAX_HISTORY_MESSAGES) return messages;

  const [firstMessage, ...rest] = messages;
  // Reserve one slot for the summary memo; keep the rest as recent history.
  const keepCount = MAX_HISTORY_MESSAGES - 2;
  const evicted = rest.slice(0, rest.length - keepCount);
  let tail = rest.slice(-keepCount);

  // Drop leading tool_results at the trim boundary — they reference tool calls
  // from an evicted assistant turn and would cause API errors.
  while (tail.length > 0 && tail[0].kind === "tool_results") {
    tail = tail.slice(1);
  }

  const summary = buildContextSummary(evicted);
  const result: LlmConversationMessage[] = [firstMessage];
  if (summary) {
    result.push({ role: "user", kind: "text", text: summary });
  }
  result.push(...tail);
  return result;
}

// ---------------------------------------------------------------------------
// Run instruction builder
// ---------------------------------------------------------------------------

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

  const editTarget = "production code";

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

// ---------------------------------------------------------------------------
// Strategy
// ---------------------------------------------------------------------------

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
      let applyPatchAttempts = 0;
      let appliedPatchSucceeded = false;

      // Staleness-based nudge: fires when the model has spent N consecutive
      // iterations revisiting the same files and searches without applying any
      // change. This is a behavioral signal — not a fixed iteration count or
      // task-type gate — so it applies equally to all task types and would
      // also catch over-exploration on tasks that would otherwise pass.
      const STALE_THRESHOLD = 3;
      const filesSeenSet = new Set<string>();
      const searchesSeen = new Set<string>();
      let staleIterations = 0;
      let sentNudge = false;

      while (iterations < MAX_ITERATIONS) {
        ctx.metrics.incrementIterations();
        iterations++;

        const response = await provider.createToolResponse({
          systemPrompt,
          messages: summarizeAndTrim(messages), // Fix #2: was trimConversation
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

        const dispatchOne = async (toolCall: (typeof response.toolCalls)[number]) => {
          const toolInput =
            normalizeToolName(toolCall.name, toolCall.input) === "run_tests" &&
            (!Array.isArray(toolCall.input["tests"]) ||
              toolCall.input["tests"].length === 0)
              ? { ...toolCall.input, tests: ctx.expected_failing_tests }
              : toolCall.input;
          const result = await dispatchTool(client, toolCall.name, toolInput);
          if (result.name) {
            ctx.metrics.recordToolCall(result.name);
            if (result.name === "apply_patch") {
              applyPatchAttempts++;
              if (result.patchApplied) appliedPatchSucceeded = true;
            }
          }
          return { toolCallId: toolCall.id, content: result.content };
        };

        // If apply_patch is in this batch, run all calls sequentially so the
        // file write completes before any subsequent run_tests reads the disk.
        const batchHasPatch = response.toolCalls.some(
          (tc) => normalizeToolName(tc.name, tc.input) === "apply_patch",
        );
        const toolResults: { toolCallId: string; content: string }[] = [];
        if (batchHasPatch) {
          for (const tc of response.toolCalls) toolResults.push(await dispatchOne(tc));
        } else {
          toolResults.push(...(await Promise.all(response.toolCalls.map(dispatchOne))));
        }

        messages.push({
          role: "user",
          kind: "tool_results",
          results: toolResults,
        });

        // Fix #1: exit as soon as a run_tests result shows the target tests
        // passing. Without this, the model keeps going after a successful fix
        // and can undo it (as happened in task_03: fixed at iter ~10, then
        // spent 20 more iterations breaking its own correct patch).
        const targetTestsPassed = response.toolCalls.some((tc, i) => {
          if (normalizeToolName(tc.name, tc.input) !== "run_tests") return false;
          try {
            const parsed = JSON.parse(toolResults[i].content) as Record<string, unknown>;
            return parsed["passed"] === true;
          } catch {
            return false;
          }
        });
        if (targetTestsPassed) {
          testsPassed = true;
          messages.push({
            role: "user",
            kind: "text",
            text: "All target tests are now passing. Task complete — stop here.",
          });
          break;
        }

        // Staleness nudge: if the model has spent STALE_THRESHOLD consecutive
        // iterations reading the same files and running the same searches with
        // no patch attempt, it is cycling. Fire once to break the loop.
        // This is behavior-driven, not task-type or iteration-count gated.
        {
          let gainedNewInfo = false;
          let patchThisIteration = false;
          for (const tc of response.toolCalls) {
            const name = normalizeToolName(tc.name, tc.input);
            if (name === "read_file") {
              const path = tc.input["path"] as string | undefined;
              if (path && !filesSeenSet.has(path)) {
                filesSeenSet.add(path);
                gainedNewInfo = true;
              }
            } else if (name === "search_in_files") {
              const query = tc.input["query"] as string | undefined;
              if (query && !searchesSeen.has(query)) {
                searchesSeen.add(query);
                gainedNewInfo = true;
              }
            } else if (name === "apply_patch") {
              patchThisIteration = true;
            }
          }
          if (patchThisIteration) {
            staleIterations = 0;
          } else if (gainedNewInfo) {
            staleIterations = 0;
          } else {
            staleIterations++;
          }
          if (!sentNudge && staleIterations >= STALE_THRESHOLD) {
            messages.push({
              role: "user",
              kind: "text",
              text:
                "You have been revisiting the same files and searches for several " +
                "iterations without making a change. Stop exploring and apply a patch " +
                "now based on what you have already found.",
            });
            sentNudge = true;
          }
        }
      }

      // Ground-truth success check — independent of what the model claims.
      const finalTests = await client.runTests(ctx.expected_failing_tests);
      ctx.metrics.recordToolCall("run_tests");
      testsPassed = finalTests.passed;
      ctx.metrics.setFinalTestsPassed(testsPassed);
      ctx.metrics.setPatchGenerated(applyPatchAttempts > 0);
      ctx.metrics.setPatchApplied(appliedPatchSucceeded);
      const accessStats = client.getAccessStats();
      ctx.metrics.setAccessMetrics({
        files_read_count: accessStats.filesReadCount,
        files_read_paths: accessStats.filesReadPaths,
        search_queries_count: accessStats.searchQueriesCount,
      });

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
