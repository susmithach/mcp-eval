# RAG Strategy — Architecture and Execution Flow

## Overview

The RAG (Retrieval-Augmented Generation) strategy uses a pre-built index of the repository to retrieve the most relevant code chunks for a given task, then passes those chunks as static context to the LLM for patch generation. Unlike MCP, the model does not explore the repository interactively — it receives retrieved context and must produce a fix in a single LLM call per iteration. The strategy runs for up to 3 iterations, re-querying and re-retrieving on each retry.

---

## 1. Component Architecture

```
harness/
├── src/
│   ├── strategies/
│   │   └── rag.ts             # Main strategy: index, retrieve, generate, apply
│   ├── rag/
│   │   ├── indexer.ts         # Walk repo, chunk files, compute IDF
│   │   ├── chunker.ts         # Split files into overlapping line windows
│   │   ├── retriever.ts       # BM25-style scoring with path boost
│   │   └── rag.ts             # Query builder, retrieval orchestration
│   └── runner/
│       ├── run_task.ts        # Repo reset, task injection, strategy dispatch
│       ├── prompt_loader.ts   # Load system prompt by task type
│       ├── patch_extractor.ts # Extract <patch>...</patch> from LLM response
│       └── metrics.ts         # MetricsTracker: accumulate and finalize results
target-repo/
└── pyservicelab/              # The Python codebase under test
    └── tests/
```

---

## 2. Pre-Run Setup

Before the RAG strategy is called, the harness performs the same two operations as other strategies:

### 2.1 Repository Reset

```
git -C target-repo checkout -- .
git -C target-repo clean -fd
```

Every run starts from a clean repository state.

### 2.2 Task Injection

The task's `.patch` file is applied to introduce the bug or stub:

```
git -C target-repo apply patches/{task_id}.patch
```

---

## 3. Index Building

At the start of each run, the RAG strategy builds a fresh index from the current state of the repository. This happens before any LLM call.

### 3.1 File Walk (`indexer.ts`)

The indexer walks two directories:
- `target-repo/pyservicelab/` — production source files
- `target-repo/tests/` — test files

Only `.py` files are included. Binary files, `__pycache__`, and `.pyc` files are skipped.

### 3.2 Chunking (`chunker.ts`)

Each file is split into overlapping line windows:

```
Chunk size:   120 lines
Overlap:      20 lines
Chunk ID:     {path}:{startLine}-{endLine}
```

A 300-line file produces chunks at lines 0–119, 100–219, 200–299. The 20-line overlap ensures that code spanning a chunk boundary appears in at least one chunk in full context.

Empty chunks (files shorter than one chunk) are included as a single chunk. Completely empty files are filtered out.

### 3.3 IDF Computation (`indexer.ts`)

After all chunks are built, the indexer computes Inverse Document Frequency (IDF) for every token across the entire corpus:

```
IDF(token) = log((N + 1) / (df(token) + 1))
```

Where:
- `N` = total number of chunks
- `df(token)` = number of chunks containing this token

Common tokens like `self`, `return`, `def` appear in almost every chunk and get low IDF scores. Rare tokens like a specific function name or variable get high IDF scores, making them more discriminative for retrieval.

The IDF table is computed once and reused for all retrieval calls within the same run.

---

## 4. Query Building

For each retrieval call, the strategy builds a text query from task metadata and test failure output.

### 4.1 Test Identifier Extraction

Test node IDs like `tests/test_user.py::TestUserService::test_search_by_username` are decomposed:

```
"test_search_by_username" → ["search", "by", "username", "search_by_username"]
```

This captures both the compound identifier and its constituent words, improving retrieval when individual words appear in source files but the full snake_case name does not.

### 4.2 Failure Highlights

The strategy runs the target tests first to capture the current failure output. From the raw stdout/stderr, it extracts the most informative lines:

- Lines starting with `E ` (pytest error lines)
- Lines starting with `>` (code being executed at failure)
- Lines containing `AssertionError`, `FAILED`, or `Error:`

These lines are condensed (max 10 lines, truncated at 200 chars each) into a short failure highlight block.

### 4.3 Full Query

```
{task_type} {test_id_1} {test_id_2} ... {extracted_words} {failure_highlights}
```

Example for a bug fix task:
```
bug_fix test_search_by_username search by username AssertionError: 0 != 3
```

---

## 5. Retrieval Scoring (`retriever.ts`)

### 5.1 Tokenization

Both the query and each chunk are tokenized using the same rule:

```
Extract tokens matching: [a-zA-Z0-9_]+
Filter: length >= 2 characters
Remove stop words: ["self", "return", "def", "class", "import", "from", "if",
                    "else", "for", "in", "not", "and", "or", "true", "false",
                    "none", "is", "as", "with", "pass", "raise", "try", "except"]
```

### 5.2 BM25-Style Scoring

Each chunk receives a raw score from three components:

**Coverage Score** — which query tokens appear in the chunk:
```
coverageScore = Σ IDF(t) for t in (queryTokens ∩ chunkTokens)
              / Σ IDF(t) for t in queryTokens
```
Range: 0–1. A chunk that contains all high-IDF query tokens scores close to 1.

**Density Score** — how concentrated the matches are:
```
densityScore = Σ IDF(t) for t in (queryTokens ∩ chunkTokens)
             / chunkTokens.length
```
Short chunks with dense matches score higher than long chunks with scattered matches.

**Path Boost** — does the file path itself contain query tokens:
```
pathBoost = Σ IDF(t) for t in (queryTokens ∩ pathTokens)
           / Σ IDF(t) for t in queryTokens
```
This rewards chunks from files whose name matches the query (e.g., a chunk from `user_service.py` scores higher for a query about `search_by_username`).

**Raw Score:**
```
rawScore = coverageScore + densityScore + pathBoost
```

### 5.3 Source File Boost

For `bug_fix` and `feature` tasks, production source files (`pyservicelab/`) are boosted:
```
if chunk.path.startsWith("pyservicelab/"):
  rawScore *= 2.0
```

For `test_fix` tasks, this boost is **not applied** (boost factor = 1.0), because the target of the fix is the test file itself.

### 5.4 Top-K Selection with File Deduplication

The top chunks by score are selected, subject to a per-file cap:
```
maxChunksPerFile = 2
Top-K = 8 chunks total
```

This prevents overlapping 120-line windows from the same file filling all 8 slots. A file contributes at most 2 chunks; remaining slots go to other files.

---

## 6. Strategy Execution Flow

### 6.1 Constants

```typescript
MAX_ITERATIONS = 3
MAX_TOKENS = 16_384
```

### 6.2 Iteration Loop

Each iteration:

1. **Run Tests** — Run the target tests to get current failure output.
   ```typescript
   const testResult = await runPytest(ctx.expected_failing_tests);
   ```

2. **Build Query** — Combine task metadata, test identifiers, and failure highlights into a retrieval query.

3. **Retrieve Chunks** — Score all chunks in the index using BM25 and return the top 8, with at most 2 per file.

4. **Build User Message** — Assemble the prompt:

   ```
   Expected failing tests:
   - tests/test_user.py::TestUserService::test_search_by_username
   
   Observed failure highlights:
   E  AssertionError: 0 != 3
   
   Full task-specific test output:
   {full pytest stdout/stderr}
   
   Retrieved repository chunks relevant to this task:
   === pyservicelab/services/user_service.py:45-164 | score=2.14 ===
   {chunk text}
   
   === tests/test_user.py:1-120 | score=0.87 ===
   {chunk text}
   
   Fix only the production code. Do not modify any test files.
   
   Please provide your fix as a unified diff patch wrapped in <patch>...</patch> tags.
   ```

   The fix target instruction varies by task type:
   - `bug_fix`/`feature` → "Fix only the production code. Do not modify any test files."
   - `test_fix` → "Fix only the test file. Do not modify any production source files."

5. **LLM Call** — A single `createTextResponse()` call with the system prompt and user message:
   ```typescript
   provider.createTextResponse({
     systemPrompt,
     userMessage,
     maxTokens: MAX_TOKENS
   })
   ```
   Token usage is recorded.

6. **Extract Patch** — `extractPatch()` looks for:
   - `<patch>...</patch>` tags (primary format)
   - Markdown code fences: `` ```diff `` or `` ```patch `` (fallback)
   - Returns `null` if neither is found.

7. **Apply Patch** — If a patch was found, it is applied via `git apply`:
   ```
   git -C target-repo apply --whitespace=fix
   ```
   If application fails (e.g., hunk mismatch), the failure is recorded and the iteration continues.

8. **Test Verification** — Run the target tests again. If they pass, exit the loop.

9. **Next Iteration** — If tests still fail and iterations remain, go back to step 1 with fresh retrieval using the updated test output.

### 6.3 Ground-Truth Verification

After the loop, the final test state is used as the authoritative success signal:

```typescript
testsPassed = lastTestResult.passed;
ctx.metrics.setFinalTestsPassed(testsPassed);
```

---

## 7. System Prompts

Same prompts as MCP, loaded from `harness/prompts/` by task type.

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
Implement the feature in the production code so all tests pass.
Follow existing patterns: type hints, docstrings, self._repo for DB access.
```

**Test Fix (`test_fix.txt`)**
```
The production source code is correct. A bug has been introduced into a test file.
Fix only the test file so the assertion reflects correct expected behavior.
Do not modify any production source files.
```

---

## 8. Metrics and Result Schema

Every run produces a JSON result file at `results/{task_id}/rag/run_{n}.json`.

**Key fields tracked:**

| Field | Description |
|-------|-------------|
| `success` | Whether the target tests passed after the run |
| `iterations` | Number of LLM calls attempted (max 3) |
| `tokens_in / tokens_out` | LLM token usage across all iterations |
| `retrieved_chunks_count` | Total chunks retrieved across all iterations |
| `retrieved_files_count` | Unique files those chunks came from |
| `retrieved_paths` | Sorted list of those file paths |
| `retrieved_chars` | Total characters across all retrieved chunks |
| `retrieved_lines` | Total lines across all retrieved chunks |
| `context_files_count` | Total files in context (source + test) |
| `context_source_files_count` | Source files specifically |
| `context_test_files_count` | Test files specifically |
| `patch_generated` | Whether the model returned a patch |
| `patch_applied` | Whether `git apply` succeeded |
| `final_tests_passed` | Ground-truth test result |
| `final_diff` | Full git diff at end of run |
| `files_changed_count` | Files modified in final diff |
| `lines_added / lines_deleted` | Size of final change |
| `context_precision` | `files_changed / files_retrieved` — ratio of useful to total retrieval |
| `failure_category` | Categorical failure reason (see below) |

**Failure category inference:**

```
If error message contains "429" or "rate limit"  → provider_error
If error message contains "git apply"            → patch_apply_failure
If no error but !patchGenerated                  → no_patch
If patchGenerated but finalDiff is empty         → patch_apply_failure
If patchGenerated and finalDiff non-empty        → wrong_logic
```

---

## 9. Design Decisions and Tradeoffs

| Decision | Rationale |
|----------|-----------|
| Max 3 iterations | RAG is a retrieval + generation pipeline, not exploration; 3 gives one retry without the overhead of a full agent loop |
| Chunk size 120 lines, overlap 20 | Large enough to include a full function with context; overlap prevents missing code at boundaries |
| BM25 IDF weighting | Rare, distinctive tokens (function names, domain terms) dominate scoring over common Python keywords |
| Source boost = 2.0 for bug_fix/feature | Production files are the target; test files are needed for context but should not crowd out the source |
| Source boost = 1.0 for test_fix | The test file IS the target; no boost needed for source files |
| maxChunksPerFile = 2 | Prevents overlapping windows from the same large file consuming all top-K slots |
| Top-K = 8 chunks | Empirically balances retrieval coverage against prompt length; more chunks increase tokens without proportional benefit |
| Failure highlights extracted | Condensed error lines focus retrieval and generation on the specific failure rather than the full, noisy pytest output |
| Single LLM call per iteration | Keeps per-iteration cost low; the retrieved context is the only tool available — no interactive exploration |
| Patch in `<patch>` tags | Structured output format; easier to extract reliably than parsing arbitrary code blocks |

---

## 10. End-to-End Example (Bug Fix Task)

**Task:** `task_05` — `email_exists` always returns false

```
Iteration 1:

  Query built: "bug_fix test_email_exists email exists False AssertionError"
  
  Retrieved chunks:
    pyservicelab/services/user_service.py:0-119   | score=2.31
    tests/test_user.py:0-119                      | score=1.14
    pyservicelab/db/user_repo.py:0-119            | score=0.89
    ...
  
  LLM receives: system prompt + test output + 8 chunks
  LLM returns: <patch>
    --- a/pyservicelab/services/user_service.py
    +++ b/pyservicelab/services/user_service.py
    @@ -55,7 +55,7 @@
    -    return False
    +    return self._repo.email_exists(email)
    </patch>
  
  git apply: success
  run_tests: FAILED (patch applied wrong method)
  
Iteration 2:

  Query rebuilt with updated failure output
  Retrieved chunks: same top files (retrieval is deterministic for same query)
  
  LLM receives: updated test output + same chunks
  LLM returns: revised patch targeting correct method
  
  git apply: success
  run_tests: PASSED → exit loop

Ground-truth verification: PASSED
```

Output metrics:
- `iterations: 2`
- `tokens_total: ~14,000`
- `retrieved_chunks_count: 16` (8 per iteration)
- `retrieved_files_count: 5`
- `context_precision: 0.20` (1 file changed / 5 files retrieved)
- `success: true`

---

## 11. Key Differences from MCP and Prompt-Only

| Property | Prompt-Only | RAG | MCP |
|----------|-------------|-----|-----|
| Context source | All files (static) | Top-K chunks (retrieved) | Model chooses (dynamic) |
| Iterations | 1 | Up to 3 | Up to 30 |
| Token cost | High (all files) | Low (targeted) | Highest (exploration overhead) |
| Context precision | Low (reads everything) | Medium (retrieves relevant) | Highest (reads only needed files) |
| Failure modes | Wrong fix on one shot | Wrong retrieval → wrong fix | Commitment paralysis, provider errors |
| Repository knowledge | Complete upfront | Pre-indexed at run start | Built up turn by turn |
| Patch format | `<patch>` tags | `<patch>` tags | Unified diff via `apply_patch` tool |
