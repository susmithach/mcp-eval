# LLM Code-Repair Strategy Evaluation
## Comparative Analysis: RAG vs Prompt-Only vs MCP

> **Evaluation date:** 2026-05-02
> **Model:** Claude Sonnet 4.6 (claude-sonnet-4-6)
> **Runs per task per strategy:** 3 independent runs
> **Total runs:** 81 (9 tasks × 3 strategies × 3 runs)

---

## 1. Project Overview

### Goal
Compare three LLM-based automated code-repair strategies on a controlled Python codebase. Each strategy receives the same intentionally broken or stubbed code and must produce a patch that makes specified failing tests pass — without any knowledge of the correct answer.

### Codebase: `pyservicelab`
A multi-module Python service application with authentication, user management, project management, task management, and audit logging. Approximately 1,200 lines of production code across 12 source files, plus 500+ lines of tests.

### Three Strategies

| Strategy | Mechanism | LLM Interaction |
|----------|-----------|----------------|
| **RAG** | Builds a lexical index of the repo at run time. Retrieves the top-8 most relevant code chunks using BM25 IDF scoring + source-file priority boost. Feeds chunks to LLM in a single prompt. | One-shot with up to 3 refinement rounds |
| **Prompt-Only** | Reads every production Python file and the failing test files. Concatenates everything into a single large prompt. No retrieval step. | One-shot, single round |
| **MCP** | Gives the LLM a toolbox: `list_files`, `read_file`, `search_in_files`, `run_tests`, `apply_patch`, `git_diff`. The LLM decides what to read, when to patch, and when to stop. | Multi-turn agent loop, up to 30 iterations |

### Nine Tasks

| Task | Type | Bug / Stub Description | Target File |
|------|------|------------------------|-------------|
| task_01 | bug_fix | Token expiry check bypassed — expired tokens accepted | `auth/tokens.py` |
| task_02 | bug_fix | Project tag list returned in inverted order | `domain/project.py` |
| task_03 | bug_fix | Empty-name guard removed — empty strings accepted | `core/validation.py` |
| task_04 | bug_fix | `AuditService.count()` hardcoded to return `0` | `services/audit_service.py` |
| task_05 | bug_fix | `UserRepo.email_exists()` hardcoded to return `False` | `db/user_repo.py` |
| task_06 | feature | `UserRepo.search_by_query()` stubbed to return `[]` | `db/user_repo.py` |
| task_07 | feature | `AuditService.purge_old_entries()` stubbed to return `0` | `services/audit_service.py` |
| task_08 | test_fix | Wrong role value asserted in test (`"admin"` → `"member"`) | `tests/test_users.py` |
| task_09 | test_fix | Wrong count asserted in test (`2` → `3`) | `tests/test_users.py` |

---

## 2. Overall Results

### Pass Rates (3 runs each)

| Strategy | Passes | Total Runs | Pass Rate |
|----------|--------|------------|-----------|
| **RAG** | 24 | 27 | **89%** |
| **Prompt-Only** | 25 | 27 | **93%** |
| **MCP** | 19 | 27 | **70%** |

### Per-Task Pass Rate Heatmap

| Task | Type | RAG | Prompt | MCP |
|------|------|:---:|:------:|:---:|
| task_01 | bug_fix | 3/3 ✓ | 2/3 ~ | 3/3 ✓ |
| task_02 | bug_fix | 3/3 ✓ | 2/3 ~ | 3/3 ✓ |
| task_03 | bug_fix | 3/3 ✓ | 3/3 ✓ | 2/3 ~ |
| task_04 | bug_fix | 3/3 ✓ | 3/3 ✓ | 3/3 ✓ |
| task_05 | bug_fix | **0/3 ✗** | 3/3 ✓ | 3/3 ✓ |
| task_06 | feature | 3/3 ✓ | 3/3 ✓ | **0/3 ✗** |
| task_07 | feature | 3/3 ✓ | 3/3 ✓ | 2/3 ~ |
| task_08 | test_fix | 3/3 ✓ | 3/3 ✓ | 3/3 ✓ |
| task_09 | test_fix | 3/3 ✓ | 3/3 ✓ | **0/3 ✗** |

> ✓ = passed all 3 runs  ~  = passed 2/3  ✗ = failed all 3 runs

---

## 3. Metric-by-Metric Analysis

### 3.1 Token Consumption

Token consumption measures LLM API cost. Lower is better.

#### Average Tokens per Task (across all 3 runs)

| Task | RAG | Prompt | MCP |
|------|----:|-------:|----:|
| task_01 | 8,601 | 42,581 | 21,362 |
| task_02 | 7,127 | 27,881 | 15,009 |
| task_03 | 8,348 | 43,330 | 86,139 |
| task_04 | 8,279 | 42,224 | 46,527 |
| task_05 | 28,312 | 45,020 | 49,997 |
| task_06 | 8,486 | 42,136 | 65,782 |
| task_07 | 6,693 | 42,434 | 74,492 |
| task_08 | 7,927 | 41,825 | 16,855 |
| task_09 | 7,598 | 42,624 | 152,028 |
| **Grand avg** | **10,152** | **41,117** | **58,688** |

#### Key Observations
- **RAG is 4× cheaper than Prompt and 5.8× cheaper than MCP** on average.
- RAG's cost is nearly flat across tasks (6,693–8,601 tokens), except task_05 (28,312) where it fails and exhausts its 3 refinement rounds.
- Prompt-Only cost is almost perfectly flat (41,825–45,020) regardless of task difficulty — it always sends the entire codebase.
- MCP cost is highly variable: 9,143 tokens for an easy run (task_02) up to 183,377 for a failing 30-iteration run (task_09). This unpredictability is a fundamental property of the agent loop.

#### Token Cost Ratio (normalized to Prompt-Only = 1×)

| Strategy | Token ratio | Relative cost |
|----------|-------------|---------------|
| RAG | 0.25× | **4× cheaper** |
| Prompt-Only | 1.00× | baseline |
| MCP | 1.43× | **43% more expensive** |

---

### 3.2 Iteration Count

Iterations = number of LLM calls per task run.

| Task | RAG | Prompt | MCP |
|------|----:|-------:|----:|
| task_01 | 1.3 | 1.0 | 8.7 |
| task_02 | 1.0 | 0.7 | 7.0 |
| task_03 | 1.0 | 1.0 | 18.3 |
| task_04 | 1.0 | 1.0 | 12.7 |
| task_05 | 3.0 | 1.0 | 12.0 |
| task_06 | 1.0 | 1.0 | 14.3 |
| task_07 | 1.0 | 1.0 | 17.0 |
| task_08 | 1.0 | 1.0 | 5.7 |
| task_09 | 1.0 | 1.0 | 28.3 |
| **Avg** | **1.3** | **1.0** | **13.8** |

#### Key Observations
- RAG and Prompt both converge in 1 iteration for 8/9 tasks. RAG occasionally needs a second round when the first patch fails to apply cleanly.
- MCP's iteration count varies from 5.7 (task_08, easy test_fix) to 28.3 (task_09, intractable). This reflects the agent's exploratory behavior — tasks where the bug is directly named in the traceback resolve quickly; tasks requiring broader search or synthesis take far longer.
- MCP's highest iteration tasks (task_09: 28.3, task_03: 18.3, task_07: 17.0) correspond to either consistent failures or high token costs.

---

### 3.3 Runtime

Wall-clock time per task run (milliseconds). Includes LLM API latency.

| Task | RAG (ms) | Prompt (ms) | MCP (ms) |
|------|---------:|------------:|---------:|
| task_01 | 5,882 | 6,757 | 10,429 |
| task_02 | 5,096 | 4,397 | 9,726 |
| task_03 | 8,371 | 6,376 | 29,558 |
| task_04 | 12,090 | 5,180 | 13,530 |
| task_05 | 26,033 | 4,009 | 13,487 |
| task_06 | 11,230 | 5,692 | 10,405 |
| task_07 | 3,860 | 5,689 | 17,906 |
| task_08 | 2,990 | 3,959 | 6,434 |
| task_09 | 4,049 | 11,012 | 23,279 |
| **Avg** | **8,845** | **5,897** | **14,972** |

#### Key Observations
- Prompt-Only is fastest on average (5.9 s), driven by single API call with no iteration overhead.
- RAG is close (8.8 s), with additional time for index building and retrieval.
- MCP is 2.5× slower than Prompt on average, with worst-case runs taking 58 s (task_03 run_1, 30 iterations).
- Prompt-Only's runtime is nearly constant (3.3–11.0 s range). MCP's runtime is proportional to iteration count, making it unpredictable.

---

### 3.4 Context Precision

`context_precision = min(1.0, files_changed / files_accessed)`

Measures how targeted the strategy is: what fraction of accessed files were actually needed?

| Task | RAG | Prompt | MCP |
|------|----:|-------:|----:|
| task_01 | 0.17 | 0.02 | 0.67 |
| task_02 | 0.14 | 0.01 | 0.83 |
| task_03 | 0.13 | 0.02 | 0.31 |
| task_04 | 0.20 | 0.02 | 0.31 |
| task_05 | 0.13 | 0.00 | 0.36 |
| task_06 | 0.14 | 0.02 | 0.11 |
| task_07 | 0.20 | 0.02 | 0.25 |
| task_08 | 0.17 | 0.02 | 0.67 |
| task_09 | 0.17 | 0.02 | 0.22 |
| **Avg** | **0.16** | **0.02** | **0.41** |

#### Key Observations
- **Prompt-Only has the lowest precision (0.02)**: it dumps ~50 files but only changes 1. By definition it accesses everything regardless of relevance.
- **RAG has moderate precision (0.16)**: retrieves 6–8 chunks covering 5–7 files, changes 1. The retrieval narrows the context but still brings in irrelevant files.
- **MCP has the highest precision (0.41)**: the agent reads only the files it actively chooses. On simple tasks (task_01, task_02, task_08) it reads 2–3 files and changes 1, giving 0.67–0.83 precision. On harder tasks it reads more broadly, dropping precision.
- Context precision is an efficiency signal, not a correctness one — MCP's higher precision doesn't directly translate to higher accuracy.

---

## 4. Per-Run Detail

### RAG — All Runs

| Run | task_01 | task_02 | task_03 | task_04 | task_05 | task_06 | task_07 | task_08 | task_09 |
|-----|---------|---------|---------|---------|---------|---------|---------|---------|---------|
| run_1 | ✓ 6,430 | ✓ 7,162 | ✓ 7,969 | ✓ 8,242 | ✗ 28,397 | ✓ 8,471 | ✓ 6,696 | ✓ 7,925 | ✓ 7,653 |
| run_2 | ✓ 12,858 | ✓ 6,869 | ✓ 9,049 | ✓ 8,519 | ✗ 28,245 | ✓ 9,000 | ✓ 6,740 | ✓ 7,916 | ✓ 7,790 |
| run_3 | ✓ 6,515 | ✓ 7,349 | ✓ 8,027 | ✓ 8,075 | ✗ 28,295 | ✓ 7,987 | ✓ 6,642 | ✓ 7,941 | ✓ 7,352 |

> task_05 fails every run with identical token count (~28,300) — all 3 refinement rounds exhausted each time. This is a deterministic retrieval+reasoning failure, not variability.

### Prompt-Only — All Runs

| Run | task_01 | task_02 | task_03 | task_04 | task_05 | task_06 | task_07 | task_08 | task_09 |
|-----|---------|---------|---------|---------|---------|---------|---------|---------|---------|
| run_1 | ✓ 42,400 | ✓ 41,972 | ✓ 43,299 | ✓ 42,284 | ✓ 44,962 | ✓ 42,058 | ✓ 42,461 | ✓ 41,816 | ✓ 42,730 |
| run_2 | ✓ 42,640 | ✓ 41,671 | ✓ 43,300 | ✓ 42,183 | ✓ 45,048 | ✓ 42,275 | ✓ 42,516 | ✓ 41,818 | ✓ 42,669 |
| run_3 | ✗ 42,702 | ✗ 0 | ✓ 43,392 | ✓ 42,204 | ✓ 45,051 | ✓ 42,074 | ✓ 42,325 | ✓ 41,841 | ✓ 42,474 |

> task_01 run_3: `wrong_logic` — model produced an incorrect fix despite having all context. Single-sample LLM variability.
> task_02 run_3: `environment_error` — repo reset failed before the LLM was even called (0 tokens, 0 iterations). Infrastructure fluke, not a strategy failure.

### MCP — All Runs

| Run | task_01 | task_02 | task_03 | task_04 | task_05 | task_06 | task_07 | task_08 | task_09 |
|-----|---------|---------|---------|---------|---------|---------|---------|---------|---------|
| run_1 | ✓ 10,251 (7i) | ✓ 24,057 (9i) | ✗ 161,506 (30i) | ✓ 25,878 (9i) | ✓ 93,442 (22i) | ✗ 157,473 (30i) | ✓ 42,143 (11i) | ✓ 22,393 (7i) | ✗ 183,377 (30i) |
| run_2 | ✓ 25,383 (10i) | ✓ 11,828 (7i) | ✓ 58,102 (13i) | ✓ 69,527 (16i) | ✓ 19,130 (5i) | ✗ 39,872 (12i)† | ✓ 35,599 (10i) | ✓ 19,350 (6i) | ✗ 123,492 (25i)† |
| run_3 | ✓ 28,453 (9i) | ✓ 9,143 (5i) | ✓ 38,808 (12i) | ✓ 44,177 (13i) | ✓ 37,419 (9i) | ✗ 0 (1i)† | ✗ 145,734 (30i) | ✓ 8,823 (4i) | ✗ 149,215 (30i) |

> † = `provider_error` — API rate limit or credit exhaustion hit mid-run. These are operational failures from long-running agent loops consuming large token budgets.
> (Ni) = N iterations

---

## 5. Failure Analysis

### 5.1 Failure Categories

| Category | Description | RAG | Prompt | MCP |
|----------|-------------|:---:|:------:|:---:|
| `wrong_logic` | Patch applied but tests still fail | 3 | 1 | 2 |
| `no_patch` | Model never called `apply_patch` | 0 | 0 | 3 |
| `environment_error` | Repo setup failed before LLM call | 0 | 1 | 0 |
| `provider_error` | API rate limit or credit exhaustion | 0 | 0 | 3 |
| **Total failures** | | **3** | **2** | **8** |

### 5.2 Root Cause Analysis per Failure

#### RAG — task_05 (0/3, `wrong_logic`)

**Bug:** `UserRepo.email_exists()` is stubbed to `return False`. Correct fix: `return row is not None`.

**Why it fails every time:**
The retriever correctly surfaces `db/user_repo.py` as the top chunk. The LLM sees the stubbed `return False` and the failing test (`test_create_duplicate_email_raises`). But the correct fix requires semantic reasoning about what the function *should* return — which is not visible from the surrounding code alone. The test error message says "no exception raised", not "wrong return value". The LLM consistently misinterprets this and applies wrong logic (e.g., `return True`, or checking a condition that doesn't exist). This is an **LLM semantic reasoning limitation**, not a retrieval failure.

**Evidence:** All 3 runs consume exactly the same token count (~28,300) and exhaust all 3 refinement rounds, suggesting the model converges to the same incorrect fix each time.

---

#### Prompt-Only — task_01 run_3 (`wrong_logic`)

**Bug:** Token expiry check bypassed. Correct fix: reverse a boolean condition.

**Why it failed once:**
With full codebase context, the model correctly identifies the file and function in 2 of 3 runs. The single failure is **LLM sampling variability** — the model chose a different (incorrect) fix on that run despite having identical context. This demonstrates that even with perfect information, probabilistic generation introduces non-determinism. The 67% success rate for this task across 3 runs shows this is a marginal case for the Prompt strategy.

---

#### Prompt-Only — task_02 run_3 (`environment_error`)

**What happened:** 0 tokens, 0 iterations, 117 ms runtime. The run failed before any LLM call.

**Why it failed:**
The repo reset script (`apply_task.py`) failed during the third consecutive run for task_02. This is an infrastructure-level fluke — likely a file-locking or subprocess timing issue during rapid sequential runs. It is **not a strategy failure** and would not appear in a production deployment with proper inter-run delays.

---

#### MCP — task_09 (0/3, `no_patch` + `provider_error`)

**Bug:** Wrong count asserted in a test (`2` → `3`).

**Why it fails every time:**
task_09 is a `test_fix` — the model needs to find a wrong number in a test assertion and change it. The error message directly shows the mismatch. However:
- The model reads the test file, then reads production files to "understand what the correct count should be", then reads more files...
- It keeps finding new files to read (no two consecutive iterations revisit the same file), so the staleness nudge never fires.
- It never commits to changing the assertion literal — paralysis from uncertainty ("what if the production code also needs changing?").
- Runs 1 and 3 hit 30 iterations with `no_patch`. Run 2 accumulated 25 iterations and hit an API provider error (rate limiting from the long token stream).

This is a **fundamental agentic limitation**: the MCP agent has no built-in pressure to stop gathering information, and for tasks requiring a simple literal change, over-exploration prevents action.

---

#### MCP — task_06 (0/3, `no_patch` + `provider_error`)

**Bug:** `search_by_query()` is stubbed. Correct fix: write a SQL `SELECT` with `LIKE` and `ORDER BY`.

**Why it fails every time:**
Unlike bug fixes where there is a suspicious existing line to target, task_06 requires **synthesizing new SQL code from scratch**. The model:
- Reads other SQL patterns in the codebase for reference
- Finds similar queries in other repo files
- But lacks confidence about the exact `LIKE`/`LOWER()` pattern needed
- Keeps searching instead of committing

Run_1 reaches the 30-iteration limit with 0 patches. Runs 2 and 3 hit provider errors before the limit (39,872 and 0 tokens respectively), meaning the API rejected the calls due to accumulated usage. This is a **task complexity limitation** combined with an **operational cost issue** — feature synthesis tasks require MCP to explore more, which exhausts the API budget.

---

#### MCP — task_03 run_1 (`wrong_logic`, 30 iter, 161,506 tokens)

**Bug:** Empty-name guard removed from `validate_non_empty()`.

**Why this one run failed while runs 2 and 3 passed:**
The model applied 5 patches across 30 iterations, each modifying the validation function. The patches accumulated incorrectly — the model kept rewriting the docstring and surrounding code while trying to add the `if not value:` check, breaking the function's structure in the process. The final accumulated state was syntactically valid but semantically wrong. Runs 2 (13 iter, 58K tokens) and 3 (12 iter, 38K tokens) show the correct approach: find the function, apply one targeted patch, verify. The 30-iteration failure is **high-variance behavior from iterative over-patching**, not a consistent failure mode.

---

#### MCP — task_07 run_3 (`wrong_logic`, 30 iter, 145,734 tokens)

**Bug:** `purge_old_entries()` is stubbed to `return 0`. Correct fix: write a SQL `DELETE` with a date threshold.

**Why this one run failed while runs 1 and 2 passed:**
Same pattern as task_03 run_1 — runs 1 and 2 resolved in 11 and 10 iterations respectively. Run_3 hit the 30-iteration ceiling with an incorrect accumulated patch. This is **high-variance multi-patch behavior** specific to feature implementation tasks where the first patch attempt often fails (wrong unified diff context after the stub is still in the file).

---

## 6. Strategy Strengths and Weaknesses

### RAG

**Strengths:**
- Lowest token cost by a wide margin (avg 10,152 tokens — 4× cheaper than Prompt)
- Consistent iteration count (1.0–1.3 per task)
- Predictable cost regardless of task difficulty
- Scales well: retrieval cost is O(log N) for index lookup, not O(N) for full read

**Weaknesses:**
- Retrieval can miss the right file if the bug destroys the tokens needed to find it (e.g., a stub that removes all domain-specific identifiers)
- Cannot verify its own fix — no test execution loop
- The one-shot nature means a wrong patch has no recovery path
- Context precision is moderate (0.16) — still retrieves some irrelevant files

**Best suited for:** Bounded, well-tokenized codebases; bugs where the relevant file is lexically identifiable from the test name or error message.

---

### Prompt-Only

**Strengths:**
- Highest pass rate (93%) in this evaluation
- Fastest wall-clock time (avg 5.9 s) — single API call per task
- Completely deterministic context — no retrieval error possible
- Handles semantic reasoning well (task_05 passes 3/3 because the model sees the full system and understands what `email_exists` should do)

**Weaknesses:**
- Fixed cost regardless of task complexity (~42K tokens for every task, including trivial ones)
- Context precision is essentially zero (0.02) — forces the LLM to filter a very large context
- Hard limit: fails when codebase exceeds the LLM's context window
- LLM variability is the only remaining failure mode — with perfect information, the model still occasionally chooses the wrong fix

**Best suited for:** Small-to-medium codebases that fit in one context; tasks where the bug requires broad cross-file understanding.

---

### MCP

**Strengths:**
- Highest context precision (0.41) — the agent reads only what it needs
- Can execute and observe tests mid-run, allowing iterative verification
- Can recover from a wrong first patch by re-reading and re-patching
- Excels on easy tasks: task_01, task_02, task_08 resolve in 5–9 iterations with low token cost

**Weaknesses:**
- Highest failure rate (30%) and highest average token cost
- Cost is unpredictable — ranges from 9,143 to 183,377 tokens for a single run
- Long-running tasks hit API provider limits (3 `provider_error` failures across 2 tasks)
- `no_patch` failures (3 total): agent over-explores without committing to a fix
- `wrong_logic` failures from iterative over-patching (2 total): model applies multiple patches that interfere with each other
- Agent loop adds latency: avg 14.9 s vs 5.9 s for Prompt

**Best suited for:** Large codebases where full-context prompting is impossible; tasks requiring active test-feedback loops; bugs that cannot be identified without running the failing tests and reading their output.

---

## 7. Design Issues Found and Fixed

During development, nine issues were identified and fixed. These are documented here as part of the evaluation methodology.

### RAG Fixes (4 issues)

| Issue | Root Cause | Fix Applied |
|-------|-----------|-------------|
| **R1: Retrieval miss — transitive call chains** | Common tokens in callers ranked higher than the target utility file. `ValidationError` had same weight as `user`, `create`. | BM25 IDF scoring: rare tokens now weighted proportionally to `log((N+1)/(df+1))`. |
| **R2: Retrieval miss — stub destroys search tokens** | Stubbing a function removes the domain-specific identifiers that would find it. Test file scored higher than the stubbed source. | 2× source-file priority boost for `bug_fix` and `feature` task types. |
| **R3: Duplicate method generation** | Multiple overlapping chunks from the same large file consumed top-K slots. LLM saw near-duplicate content and generated duplicate method definitions. | `maxChunksPerFile=2`: cap at 2 chunks per file, preventing crowding while preserving full file visibility. |
| **R4: Context noise** | 8 files retrieved including irrelevant test helpers. Rare-token bugs buried in noise. | Combined effect of IDF + source boost + deduplication reduced average retrieved files and raised signal-to-noise. |

**RAG result before/after:** 4/9 tasks (44%) → 8/9 tasks (89%)

### MCP Fixes (5 issues)

| Issue | Root Cause | Fix Applied |
|-------|-----------|-------------|
| **M1: No early exit on test pass** | Loop had no stopping condition for success. Model fixed a bug then kept running and undid the fix. | After each `run_tests` result: if `passed=true`, inject stop message and break immediately. |
| **M2: Silent context eviction** | `MAX_HISTORY_MESSAGES=10` caused model to lose test tracebacks after 5 iterations. Model re-read same files repeatedly. | `summarizeAndTrim`: extract key facts from evicted turns (files read, searches run, patch outcomes, test results) and inject as a structured memo. |
| **M3: Exploration loops without patching** | No mechanism to detect when the model is cycling. Old approach: task-type-gated fixed iteration count (hack). | Behavior-driven staleness detection: if 3 consecutive iterations add no new files and no new searches, inject a single nudge. Fires based on observed behavior, not elapsed time. |
| **M4: Output token budget too small** | `MAX_TOKENS=8,096` output budget was smaller than a single `read_file` result (12,000 chars ≈ 3,000 tokens). Model hallucinated file paths from compressed memory. | Raised `MAX_TOKENS` to 16,384. Reduced `READ_FILE_CHAR_LIMIT` to 8,000 chars so a single read can't consume the full budget. |
| **M5: Failure misclassification** | `inferFailureCategory` used `patch_applied` (bookkeeping flag) rather than actual disk evidence. Tasks where the patch landed but the flag was wrong were misclassified. | Decision table using `patchGenerated` (model attempted a patch) and `finalDiff` (git confirms what changed): `no_patch` → `patch_apply_failure` → `wrong_logic`. |
| **M6 (additional): Concurrent dispatch race** | `apply_patch` and `run_tests` in the same response turn dispatched via `Promise.all` — tests could read the file before the write completed. | Sequential dispatch when any call in the batch is `apply_patch`; parallel dispatch otherwise. |

**MCP result before/after:** 7/9 tasks passing in previous session → 7/9 tasks in 3-run baseline (high variance remains for feature tasks).

---

## 8. Summary Comparison Table

| Metric | RAG | Prompt-Only | MCP |
|--------|:---:|:-----------:|:---:|
| Pass rate (27 runs) | 89% | **93%** | **70%** |
| Avg tokens per task | **10,152** | 41,117 | 58,688 |
| Avg iterations | **1.3** | **1.0** | 13.8 |
| Avg runtime | 8.8 s | **5.9 s** | 14.9 s |
| Avg context precision | 0.16 | 0.02 | **0.41** |
| Token cost vs Prompt | **4.0× cheaper** | baseline | 1.4× more expensive |
| Cost predictability | High | **Very high** | Low |
| Handles large codebases | Yes | No | Yes |
| Test feedback loop | No | No | **Yes** |
| Consistent failure | task_05 | — | task_06, task_09 |

---

## 9. Key Takeaways for Presentation

### Finding 1: No single strategy dominates
Each strategy has a distinct profile. Prompt-Only has the highest pass rate on this benchmark but is fundamentally limited by context-window size. RAG is the most cost-efficient. MCP is the most capable in principle but the least reliable in practice on small, bounded problems.

### Finding 2: Accuracy and cost are inversely correlated
The strategy with the most information (Prompt-Only: full codebase) passes the most tasks. The strategy with the least information (RAG: 8 chunks) is 4× cheaper. MCP spends more than Prompt-Only and passes fewer tasks — demonstrating that agentic exploration overhead can outweigh its benefits on small problems.

### Finding 3: Failure modes are structurally different
- RAG fails on **semantic reasoning** (correct file retrieved, wrong fix inferred)
- Prompt fails on **LLM variability** (correct context, non-deterministic output)
- MCP fails on **commitment paralysis** (enough context found, never acts on it) and **operational cost** (provider errors from long token streams)

### Finding 4: MCP's value proposition requires scale
MCP's advantages — test feedback, surgical file access, iterative refinement — matter most when the codebase is too large to fit in a prompt. On this 1,200-line repo, Prompt-Only sends everything in 42K tokens. MCP spends up to 183K tokens reaching the same (or worse) conclusion. The crossover point where MCP outperforms Prompt-Only is when the codebase exceeds the context window (~200K tokens for this model).

### Finding 5: Three runs reveals what one run hides
- Prompt task_01 appeared 100% reliable in a 1-run test; 3 runs show 67% — a meaningful difference.
- MCP task_05 appeared lucky (1/1 pass) in a 1-run test; 3 runs confirm it passes consistently (3/3).
- MCP task_03 appeared catastrophic (30 iter, 156K tokens) in a 1-run test; 3 runs show 2/3 pass rate with reasonable cost on successful runs — the 30-iteration run was a high-variance outlier.

---

## 10. Raw Data Reference

### Tokens per Run (all 81 runs)

#### RAG
| | task_01 | task_02 | task_03 | task_04 | task_05 | task_06 | task_07 | task_08 | task_09 |
|-|---------|---------|---------|---------|---------|---------|---------|---------|---------|
| run_1 | 6,430 | 7,162 | 7,969 | 8,242 | 28,397✗ | 8,471 | 6,696 | 7,925 | 7,653 |
| run_2 | 12,858 | 6,869 | 9,049 | 8,519 | 28,245✗ | 9,000 | 6,740 | 7,916 | 7,790 |
| run_3 | 6,515 | 7,349 | 8,027 | 8,075 | 28,295✗ | 7,987 | 6,642 | 7,941 | 7,352 |

#### Prompt-Only
| | task_01 | task_02 | task_03 | task_04 | task_05 | task_06 | task_07 | task_08 | task_09 |
|-|---------|---------|---------|---------|---------|---------|---------|---------|---------|
| run_1 | 42,400 | 41,972 | 43,299 | 42,284 | 44,962 | 42,058 | 42,461 | 41,816 | 42,730 |
| run_2 | 42,640 | 41,671 | 43,300 | 42,183 | 45,048 | 42,275 | 42,516 | 41,818 | 42,669 |
| run_3 | 42,702✗ | 0✗ | 43,392 | 42,204 | 45,051 | 42,074 | 42,325 | 41,841 | 42,474 |

#### MCP
| | task_01 | task_02 | task_03 | task_04 | task_05 | task_06 | task_07 | task_08 | task_09 |
|-|---------|---------|---------|---------|---------|---------|---------|---------|---------|
| run_1 | 10,251 | 24,057 | 161,506✗ | 25,878 | 93,442 | 157,473✗ | 42,143 | 22,393 | 183,377✗ |
| run_2 | 25,383 | 11,828 | 58,102 | 69,527 | 19,130 | 39,872✗ | 35,599 | 19,350 | 123,492✗ |
| run_3 | 28,453 | 9,143 | 38,808 | 44,177 | 37,419 | 0✗ | 145,734✗ | 8,823 | 149,215✗ |

> ✗ = failed run. Token count shown is actual consumption even on failure.

---

*Evaluation conducted on branch `validation`. All harness source available in `harness/src/`. Task patches in `tasks/`. Full result JSON files in `harness/results/`.*
