# MCP Strategy — Architecture and Execution Flow

## Overview

The MCP (Model Context Protocol) strategy is an interactive, agentic approach where an LLM explores a software repository using structured tools rather than receiving static context upfront. The model drives its own information gathering — deciding which files to read, what to search for, and when to apply a fix — through a multi-turn conversation loop running for up to 30 iterations.

---

## 1. Component Architecture

```
harness/
├── src/
│   ├── strategies/
│   │   ├── mcp.ts           # Main strategy: run loop, staleness, trim, early exit
│   │   └── mcp_tools.ts     # Tool schemas, dispatch, name normalization
│   ├── mcp/
│   │   └── client.ts        # McpHarnessClient: spawns server, routes tool calls
│   └── runner/
│       ├── run_task.ts      # Repo reset, task injection, strategy dispatch
│       ├── prompt_loader.ts # Load system prompt by task type
│       └── metrics.ts       # MetricsTracker: accumulate and finalize results
server-mcp/
└── src/
    └── index.ts             # MCP server: exposes 6 tools over STDIO
target-repo/
└── pyservicelab/            # The Python codebase under test
    └── tests/
```

---

## 2. Pre-Run Setup

Before the MCP strategy is called, the harness does two mandatory operations:

### 2.1 Repository Reset

```
git -C target-repo checkout -- .
git -C target-repo clean -fd
```

Every run starts from a clean repository state. This prevents leftover patches from previous runs contaminating the next.

### 2.2 Task Injection

Each task ships a `.patch` file that deliberately introduces a bug (or stub) into the repository. The harness applies it:

```
git -C target-repo apply patches/{task_id}.patch
```

After injection, the expected failing tests are confirmed to be failing. The strategy's job is to repair them.

---

## 3. MCP Server

The MCP server (`server-mcp/src/index.ts`) is a separate Node.js process that wraps file system and test operations over the target repository. It communicates with the harness client over STDIO using the MCP protocol.

### 3.1 Server Startup

The client spawns the server as a child process at the start of every strategy run:

```typescript
new StdioClientTransport({
  command: "node",
  args: ["../server-mcp/build/index.js"],
  env: { ...safeEnv, PYTHON_BIN: resolvePythonBin() }
})
```

A new server process is started per run and closed after the run completes. No state is shared across runs.

### 3.2 Tools Exposed

The server exposes exactly six tools:

| Tool | Description | Safety Constraints |
|------|-------------|-------------------|
| `list_files(path)` | List files and directories under a path | Path traversal (`../`) rejected |
| `read_file(path)` | Read file content | Max 200 KB per file; path validated |
| `search_in_files(query, path?)` | Text search across files | Results sorted alphabetically |
| `run_tests(tests?)` | Run pytest with optional test node IDs | Only `python -m pytest` allowed; no shell |
| `apply_patch(patch)` | Apply a unified diff via `git apply` | Applied within target-repo cwd |
| `git_diff()` | Show current git working tree diff | Read-only; no flags allowed |

All subprocess calls use `spawn()` without a shell. The working directory is always locked to `target-repo`. All invocations are logged to `logs/mcp.log`.

---

## 4. Strategy Execution Flow

### 4.1 Initialization

```typescript
const client = new McpHarnessClient();
await client.connect();  // spawns the MCP server subprocess

const systemPrompt = await loadPrompt(ctx.task_type, ctx.task_id);
// Loads from: prompts/bug_fix.txt, feature.txt, or test_fix.txt

const { provider } = createLlmProvider();
// Reads LLM_PROVIDER env var (default: "anthropic")
// Model: claude-sonnet-4-6
```

The conversation history is initialized with a single user message:

```
"Please begin. Focus on these expected failing tests first: {test_ids}.
 Use run_tests to run the task's expected failing tests first, then inspect 
 only the needed files and fix the production code..."
```

For `test_fix` tasks, the instruction differs: the model is told to fix only the test file and not modify production code.

### 4.2 Main Loop

```
MAX_ITERATIONS = 30
MAX_TOKENS = 16,384
```

Each iteration:

1. **Context Trim** — If conversation history exceeds 12 messages, `summarizeAndTrim()` compresses old turns into a structured memo (see §4.5).

2. **LLM Call** — The provider sends the current conversation with all tool definitions:
   ```
   provider.createToolResponse({
     systemPrompt,
     messages: summarizeAndTrim(messages),
     tools: MCP_TOOL_DEFINITIONS,
     maxTokens: 16_384
   })
   ```
   Token usage (`inputTokens`, `outputTokens`) is recorded for every call.

3. **Append Assistant Message** — The model's response (text + tool calls) is pushed onto the conversation history.

4. **No Tool Calls → Break** — If the model returns no tool calls, the loop ends (it has decided it is done).

5. **Dispatch Tool Calls** — For each tool call in the response:
   - `normalizeToolName()` maps model aliases to canonical names (e.g., `read` → `read_file`, `grep` → `search_in_files`).
   - If `run_tests` is called without explicit test IDs, the task's expected failing tests are automatically injected.
   - `dispatchTool(client, name, input)` routes to the correct MCP client method.
   - Results are returned as JSON strings.

6. **Sequential vs Parallel Dispatch** — If `apply_patch` appears in the current batch, all tools in that batch are dispatched sequentially. This prevents a race condition where `run_tests` reads the file before `apply_patch` finishes writing it. Batches without `apply_patch` are dispatched with `Promise.all`.

7. **Append Tool Results** — Results are pushed as a `tool_results` message in the conversation.

8. **Early Exit Check** — After each `run_tests` call, the harness parses the result. If `passed === true`, the loop exits immediately with `testsPassed = true`. A final confirmation message is added: `"All target tests are now passing. Task complete — stop here."` This prevents the model from continuing to iterate after a correct fix and accidentally undoing it.

9. **Staleness Detection** — Tracks which files have been read (`filesSeenSet`) and which search queries have been run (`searchesSeen`). If 3 consecutive iterations pass with no new file, no new search query, and no `apply_patch` call, the model is considered to be cycling. A one-time nudge is sent: `"You have been revisiting the same files and searches for several iterations without making a change. Stop exploring and apply a patch now based on what you have already found."` The nudge fires at most once per run.

### 4.3 Ground-Truth Verification

After the loop exits (whether by early exit, max iterations, or no tool calls), the harness independently runs the target tests:

```typescript
const finalTests = await client.runTests(ctx.expected_failing_tests);
testsPassed = finalTests.passed;
```

This is the authoritative success signal — independent of what the model claimed or what was observed mid-loop.

### 4.4 Metrics Collection

After the loop:

```typescript
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
ctx.metrics.setFinalDiff(diff.diff);
```

The `client.getAccessStats()` returns unique files read and unique search queries tracked across the entire run.

### 4.5 Context Summarization (Fix #2)

When `messages.length > 12`, old turns are evicted and replaced with a structured memo:

```
[Summary of earlier iterations — use this to avoid repeating work]
Test runs: FAILED — AssertionError: ...; PASSED
Files read: pyservicelab/db/user_repo.py, pyservicelab/services/user_service.py
Searches: "get_user_by_id", "email"
Patch attempts: failed (patch does not apply), succeeded
```

The memo is injected as a user message after the first (system setup) message. This prevents the model from re-reading files it already saw in evicted turns, which was the primary cause of infinite re-read loops before this fix.

Leading `tool_results` messages at the trim boundary are also dropped — they reference tool call IDs from evicted assistant turns and would cause API errors.

---

## 5. Tool Name Normalization

The `normalizeToolName()` function handles cases where the model uses informal or aliased names for tools:

| Model alias | Canonical name |
|-------------|----------------|
| `read` | `read_file` |
| `open` | `read_file` |
| `grep` | `search_in_files` |
| `search` | `search_in_files` |
| `test` | `run_tests` |
| `patch` | `apply_patch` |
| `diff` | `git_diff` |

This normalization is applied before dispatch and also in all staleness/early-exit checks to ensure consistent behavior regardless of how the model names a tool.

---

## 6. System Prompts

Prompts are loaded from `harness/prompts/` based on task type. The `{{task_id}}` placeholder is substituted per run.

**Bug Fix (`bug_fix.txt`)**
```
You are a software engineer working on the PyServiceLab Python codebase.
A bug has been introduced into the production source code. One or more tests are failing.

Goal:
1. Run the test suite to identify failing tests.
2. Read the relevant source files to locate the bug.
3. Fix only the production code so all tests pass.
4. Do not modify any test files.
```

**Feature (`feature.txt`)**
```
A feature has been stubbed out. One or more tests are failing because the
feature returns a placeholder value instead of real results.
Implement the feature in production code. Follow existing patterns: type hints,
docstrings, self._repo for DB access, self.db.fetchall / fetchone for SQL queries.
```

**Test Fix (`test_fix.txt`)**
```
The production source code is correct. A bug has been introduced into a test file.
Fix only the test file so the assertion reflects correct expected behavior.
Do not modify any production source files.
```

---

## 7. Metrics and Result Schema

Every run produces a JSON result file at `results/{task_id}/mcp/run_{n}.json`.

**Key fields tracked:**

| Field | Description |
|-------|-------------|
| `success` | Whether the target tests passed after the run |
| `iterations` | Number of LLM round-trips |
| `tokens_in / tokens_out` | LLM token usage |
| `tool_calls_by_name` | Count of each tool called (e.g., `{ run_tests: 4, read_file: 6 }`) |
| `files_read_count` | Unique files the model accessed via `read_file` |
| `files_read_paths` | Sorted list of those paths |
| `search_queries_count` | Number of distinct search queries issued |
| `patch_generated` | Whether the model ever called `apply_patch` |
| `patch_applied` | Whether any patch succeeded |
| `final_tests_passed` | Ground-truth test result |
| `final_diff` | Full git diff at end of run |
| `files_changed_count` | Files modified in final diff |
| `lines_added / lines_deleted` | Size of final change |
| `context_precision` | `files_changed / files_accessed` — ratio of useful to total access |
| `failure_category` | Categorical failure reason (see below) |

**Failure category inference:**

```
If error message contains "429" or "rate limit"  → provider_error
If error message contains "git apply"            → patch_apply_failure
If error message contains "working tree"         → environment_error
If no error but !patchGenerated                  → no_patch
If patchGenerated but finalDiff is empty         → patch_apply_failure
If patchGenerated and finalDiff non-empty        → wrong_logic
```

---

## 8. Design Decisions and Tradeoffs

| Decision | Rationale |
|----------|-----------|
| Max 30 iterations | Enough for multi-step exploration; beyond this, provider cost and context explosion outweigh benefit |
| Max 12 history messages | Keeps each LLM call to a manageable prompt size; older turns are summarized, not dropped |
| Max 16,384 output tokens | Enough for the model to reason about a file it just read AND format a complete unified diff in one response |
| Staleness threshold = 3 | Fires early enough to interrupt a stuck loop without being too aggressive; behavior-driven (not iteration-count-gated) |
| Sequential dispatch on apply_patch | Eliminates the race condition where run_tests could read the file before apply_patch finished writing |
| Ground-truth final test run | Model's own assessment of success is unreliable; harness always re-runs tests independently |
| One nudge maximum | Sending the nudge repeatedly would distract the model; one well-timed nudge is sufficient |

---

## 9. End-to-End Example (Bug Fix Task)

```
Iteration 1:
  Model calls: run_tests(["tests/test_auth.py::test_token_expiry"])
  Result: FAILED — AssertionError: Expected 401, got 200

Iteration 2:
  Model calls: read_file("pyservicelab/services/auth_service.py")
  Result: [file content]

Iteration 3:
  Model calls: search_in_files("token_expiry")
  Result: auth_service.py:45: if expiry > 0:  ← wrong direction

Iteration 4:
  Model calls: apply_patch("--- a/pyservicelab/services/auth_service.py\n+++ ...")
  Result: { applied: true }
  Model calls: run_tests(["tests/test_auth.py::test_token_expiry"])
  Result: { passed: true }
  → EARLY EXIT: testsPassed = true

Ground-truth verification: PASSED
```

Output metrics:
- `iterations: 4`
- `tokens_total: ~18,000`
- `files_read_count: 1`
- `context_precision: 1.0` (1 file changed / 1 file accessed)
- `success: true`
