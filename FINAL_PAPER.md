# Evaluating Context Access Strategies for Repository-Level LLM Agents in Software Engineering Tasks

**Durga Susmitha Chakka** — Graduate Seminar, Department of Computer Science, Texas A&M University San Antonio — dchak01@jaguar.tamu.edu

**Shivani Sutrave** — Graduate Seminar, Department of Computer Science, Texas A&M University San Antonio — ssutr01@jaguar.tamu.edu

---

## Abstract

Large language models (LLMs) have shown strong potential in software engineering tasks such as bug repair, test-driven correction, and code generation. However, when these tasks are performed at the repository level, model performance does not depend only on the capability of the LLM itself, but also on how repository context is provided during reasoning and code modification. Static prompt injection, retrieval-augmented generation (RAG), and structured tool-based interaction represent three common approaches to this problem, but are rarely compared under the same experimental conditions.

This paper presents a controlled evaluation framework comparing these three context-access strategies in repository-level software engineering tasks. The study is conducted on a Python service repository with deterministic test-based validation and covers three task categories: controlled fault-injection repair, failing-test correction, and feature-driven implementation. Across all conditions, the same underlying model (Claude Sonnet 4.6), execution environment, and stopping criteria are maintained to isolate context-access strategy as the primary experimental variable. Each task-strategy combination is evaluated over three independent runs, yielding 81 total runs.

Results show that Prompt-Only achieves the highest pass rate (93%, 25/27), RAG achieves 89% (24/27) at 4× lower token cost, and MCP achieves 70% (19/27) with the highest operational overhead. The hypothesized token ordering (Prompt > RAG > MCP) was refuted: MCP consumed the most tokens on average due to agent loop overhead. The hypothesized reliability advantage for MCP was also refuted: MCP produced the most failures, including three commitment-paralysis failures and three provider-error failures from API exhaustion. These findings reveal that the value of dynamic context access is highly sensitive to codebase scale, and that agentic exploration overhead can outweigh its benefits when the full repository fits within a single prompt.

**Index Terms** — large language models, software engineering agents, retrieval-augmented generation, Model Context Protocol, repository-level code repair, tool-augmented LLMs, empirical evaluation

---

## I. Introduction

Over the past few years, large language models (LLMs) have shown significant progress in software engineering tasks such as code generation, debugging, and automated program repair. Systems based on models like Codex [1] demonstrated that LLMs can produce functional code solutions when the required context is clearly provided. However, most early evaluations were performed on isolated coding problems where the entire task context is available in a single prompt.

Real-world software development environments are considerably more complex. Modern codebases typically span multiple modules and contain hundreds or thousands of interconnected functions. When a bug occurs, developers must first identify which files are relevant before they can diagnose and repair the issue. This process of navigating repository structure and locating relevant context is an important part of software maintenance.

Several approaches have emerged for providing repository context to LLM-based coding agents. One common approach is prompt-based context injection, where selected source files are directly placed into the model prompt. Another approach is retrieval-augmented generation (RAG) [4], which retrieves relevant code fragments from a repository index before each generation step. More recently, tool-based interaction mechanisms have been proposed, where an agent can dynamically explore the repository using tools such as file readers, search utilities, or test execution commands. In this study, the tool-based condition is implemented using a Model Context Protocol (MCP) server that provides structured access to repository operations.

These approaches represent different ways of exposing repository context to language models. Each strategy provides distinct advantages and limitations in terms of context availability, efficiency, and system complexity. Understanding how these mechanisms influence agent behavior is therefore important for designing reliable LLM-based software engineering systems.

This paper presents a controlled experimental framework for studying repository-level LLM agents. Using a Python service repository with test-driven validation, we evaluate three context-access strategies across nine software engineering tasks covering bug repair, failing-test correction, and feature implementation. All experiments were completed and the results presented here reflect 81 independent runs with full metric collection.

**Contributions:**
1. A reproducible evaluation harness where every variable except context-access strategy is fixed across runs.
2. A controlled repository-level benchmark covering five fault-injection repair tasks, two feature implementation tasks, and two failing-test correction tasks across the same experimental framework.
3. A metric set that goes beyond pass rate to capture iteration cost, token usage, context precision, and behavioral failure modes.
4. Empirical verification of four pre-registered hypotheses and a characterization of the conditions under which each strategy succeeds or fails.
5. An analysis of the implementation challenges encountered for each strategy and the principled fixes required to achieve stable experimental results.

---

## II. Problem Statement

Despite rapid advances in LLM-based coding assistants, there is still limited controlled research on how different context-access mechanisms affect agent performance in real software repositories. Most existing work evaluates the model itself rather than the method used to provide repository context.

As a result, it remains unclear whether performance differences in repository-level software engineering tasks are caused primarily by the underlying language model, by the context-access strategy, or by the interaction between the two. This gap is especially important in multi-file repositories, where relevant information may be distributed across several modules and where incomplete or poorly structured context can lead to inefficient reasoning, invalid edits, or failed repairs.

This study addresses that problem by evaluating three context-access strategies — prompt-only context injection, retrieval-augmented generation, and structured tool-mediated interaction — under the same model configuration and controlled execution environment.

---

## III. Research Questions

We organize the study around four questions derived from gaps in the existing literature.

**RQ1 — Success Rate.** How do prompt-only, RAG, and MCP compare in terms of test-pass success rate across controlled software engineering tasks?

**RQ2 — Efficiency.** How do the three strategies differ in the cost of reaching a successful solution, measured through iteration count, runtime per task, and total token usage?

**RQ3 — Reliability.** Do structured tools (MCP) reduce unreliable agent behaviors such as invalid file references, failed patch applications, or edits to unrelated modules?

**RQ4 — Task Sensitivity.** Do different context-access strategies perform differently depending on task characteristics such as fault locality, cross-module dependencies, or feature implementation complexity?

---

## IV. Related Work

### A. LLMs for Code Generation and Bug Repair

The Codex paper [1] introduced pass@k as the standard way to measure whether a generated fix works. But the tasks in that evaluation were single functions with all needed context already provided. Nothing in the benchmark requires the model to figure out which part of a larger system is relevant. Our work uses the same pass@k metric but applies it to a setting where context navigation is the central challenge.

Tufano et al. [2] took a different angle, mining bug-fixing commits from open-source projects and training neural translation models to reproduce the fix. Their main contribution for our purposes is methodological: they showed that real test suites make reliable evaluation and that diffs are a natural output format for repair systems. We rely on both of these design choices in our setup.

Jiang et al. [3] introduced the idea of iterative self-repair, where the model sees the test output after each attempt and tries again. Fix rates went up, but something interesting also showed up in the failure cases: agents that did not have the right context kept making the same wrong edits in circles. That observation is part of why we track iteration count and repeated ineffective actions as first-class metrics.

### B. Retrieval-Augmented Generation for Code

Gao et al. [4] provide a broad survey of RAG and summarize the general retrieve-then-generate pattern used to improve grounding and reduce irrelevant context. That pattern maps naturally onto the code repair problem, where failing test output can be used to retrieve repository context before generation.

Zhang et al. [5] extend this idea to repository-level code tasks through iterative retrieval and generation. Their findings are directly relevant to our setting: retrieval quality depends strongly on chunking decisions, ranking quality, and whether the retrieved context actually covers the fault location. We therefore use a deterministic retrieval baseline so that the same query returns the same ranked chunks across runs. This keeps the comparison interpretable and reduces experimental variance from the retrieval layer.

### C. Tool-Augmented LLM Agents

Toolformer [6] demonstrated that language models can learn to call external APIs during generation, which helps reduce factual errors. Our approach differs in that tool interaction is handled through a separate MCP server that validates and executes tool requests. Despite this implementation difference, the core motivation is similar: grounding model outputs through interaction with external tools can reduce the hallucinations that often make LLM-generated code unreliable.

ReAct [8] is the closest architectural ancestor of our MCP agent loop. The idea of alternating between a reasoning step and a tool call, then feeding the tool's output back into the next reasoning step, is how Strategy C works. ReAct was evaluated on question-answering tasks, but the loop structure transfers directly to bug repair, where each `read_file` or `run_tests` call gives the agent new information to reason about.

Gorilla [7] is relevant for a specific reason. Patil et al. showed that when tool schemas are well-specified, models make substantially fewer malformed API calls. That finding is part of why we built the MCP server with strict schema validation — invalid calls show up in the logs as a concrete failure signal rather than silently producing garbage.

WebGPT [9] is less directly related but methodologically important. Nakano et al. argued that for tool-using agents, tracking the sequence of actions matters as much as the final answer. An agent that reaches the right answer through five unnecessary accesses is not the same as one that does it in two. We apply the same logic: it is not enough to know whether the bug was fixed; we want to know how many tool calls it took and whether any were wasteful.

### D. Evaluation Benchmarks

SWE-bench [10] is the benchmark our work is most directly in conversation with. It asks models to resolve actual GitHub issues evaluated against the repository's own test suite — the same test-driven setup we use. The difference is that SWE-bench uses real, heterogeneous repositories, which makes it hard to attribute performance differences to any single factor. We trade ecological validity for control: a synthetic repository with known faults lets us say something definitive about whether context-access strategy matters independently of codebase characteristics.

AgentBench [11] evaluated tool-using agents across a variety of tasks and emphasized that step count and error behavior are as informative as success rate. That shaped how we designed our metric collection. Knowing an agent succeeded but needed fifteen iterations and hallucinated three file paths along the way is useful information that a binary pass/fail score would hide.

To the best of our knowledge, previous work has not provided a controlled comparison in which prompt injection, RAG, and tool-mediated access are evaluated on the same repository-level tasks under a shared model and execution setting. That is the specific gap this study targets.

---

## V. Experimental Design

### A. Target Repository

We needed a codebase that was realistic enough to pose genuine context-navigation challenges but controlled enough that we could inject known faults and measure outcomes cleanly. We used a multi-module Python service application (`pyservicelab`) with approximately 1,200 lines of production source code across 12 source files, plus 500+ lines of test code. The repository has separate modules for authentication (`auth/`), core validation utilities (`core/`), database access (`db/`), domain models (`domain/`), and business logic services (`services/`). This structure is common in real backend services: a bug in one layer can only be diagnosed by reading across to another layer.

All pytest tests pass on the clean codebase, and the repository is Git-initialized. The Git setup matters specifically for Strategy C: the MCP server's `apply_patch` tool calls `git apply` internally, and `git_diff` gives the agent a view of what it has changed so far. The codebase occupies approximately 42,000 tokens when the complete production source is loaded into a single prompt — well within the context window of the evaluation model.

### B. Task Construction

We constructed nine tasks covering three categories. Table I provides the full task list.

**Table I: Experimental Tasks**

| Task | Category | Description | Target File |
|------|----------|-------------|-------------|
| task_01 | bug_fix | Token expiry check bypassed; expired tokens accepted | `auth/tokens.py` |
| task_02 | bug_fix | Project tag list returned in inverted order | `domain/project.py` |
| task_03 | bug_fix | Empty-name guard removed; empty strings accepted as valid | `core/validation.py` |
| task_04 | bug_fix | `AuditService.count()` hardcoded to return 0 | `services/audit_service.py` |
| task_05 | bug_fix | `UserRepo.email_exists()` hardcoded to return False | `db/user_repo.py` |
| task_06 | feature | `UserRepo.search_by_query()` stubbed to return empty list | `db/user_repo.py` |
| task_07 | feature | `AuditService.purge_old_entries()` stubbed to return 0 | `services/audit_service.py` |
| task_08 | test_fix | Wrong role value asserted in test (admin instead of member) | `tests/test_users.py` |
| task_09 | test_fix | Wrong count asserted in test (2 instead of 3) | `tests/test_users.py` |

Each task is introduced by applying a patch via `scripts/apply_task.py`. Bugs vary in type: hardcoded return values (task_04, task_05), removed validation guards (task_03), inverted logic (task_01, task_02), stubbed implementations (task_06, task_07), and wrong test assertions (task_08, task_09). The repository is restored to its clean state before each run using `scripts/reset_repo.py`, ensuring every strategy starts from the same baseline.

### C. Context-Access Strategies

**Strategy A — Prompt-Only.** All production Python source files are read at the start of each run and concatenated into a single prompt along with the failing test file and task description. The model produces a patch in one shot. This serves as the oracle baseline: the model has complete information with no retrieval step to go wrong.

**Strategy B — RAG.** At run initialization, a lexical index is built over all repository source files using 120-line chunks with 20-line overlap. Before each generation step, the failing test names and file contents are used to construct a retrieval query. The top-8 chunks are selected using BM25 TF-IDF scoring with two key enhancements: (1) IDF weighting that gives rare, code-specific tokens (function names, class names, exception types) higher weight than common tokens (`return`, `if`, `def`); and (2) a 2× source-file priority boost for `bug_fix` and `feature` tasks, which ensures that production source files rank above test files that share the same domain vocabulary. A `maxChunksPerFile=2` cap prevents large files from flooding all top-K slots. The model receives up to 3 refinement rounds if the first patch fails.

**Strategy C — MCP.** The agent interacts with the repository through a structured tool interface rather than receiving pre-loaded context. A TypeScript MCP server runs as a subprocess and exposes six tools: `list_files`, `read_file`, `search_in_files`, `run_tests`, `apply_patch`, and `git_diff`. The agent decides which files to read, which searches to run, and when to apply patches. The agent loop runs for up to 30 iterations. Three behavioral mechanisms govern the loop: (1) early exit when `run_tests` returns `passed=true` for the expected failing tests; (2) a structured context summarization that compresses evicted conversation history into a memo (files read, searches run, patch outcomes, test results) instead of silently dropping it; and (3) a staleness nudge that fires after 3 consecutive iterations in which no new file was read and no new search was executed, signaling that the agent is cycling without progress.

### D. Implementation Challenges and Fixes

During development, several implementation issues were identified and corrected before running the final baseline. These are documented here as they reflect real engineering challenges in building reliable evaluation harnesses.

**RAG retrieval failures:** Initial retrieval missed `core/validation.py` for task_03 (transitive call chain — callers had higher lexical overlap with the query than the target utility) and retrieved only test files for task_06 (the stub removed the domain-specific tokens that would have identified the file). These were resolved by introducing IDF weighting and the source-file priority boost. An initial per-file deduplication of top-1 per file caused a regression on task_07 (the second chunk of `audit_service.py`, containing the stubbed method body, was dropped); this was corrected by changing to `maxChunksPerFile=2`.

**MCP agent loop defects:** Five loop-level issues were identified: (1) no early exit when tests pass mid-loop, causing the model to undo a correct fix (task_03 was fixed at iteration 10 then broken by iteration 30); (2) silent context eviction causing re-read loops (the model re-read the same 14–17 files when prior results were trimmed without summarization); (3) no exploratory nudge mechanism for any task type; (4) an output token budget (8,096) smaller than the maximum tool result size (12,000 chars), causing path hallucinations under compression; and (5) a failure classification bug that reported `patch_apply_failure` when the patch had in fact landed on disk. Additionally, `apply_patch` and `run_tests` in the same response turn were dispatched concurrently via `Promise.all`, creating a race condition where tests could complete before the file write finished. All six issues were fixed before the final baseline run.

**Metric integrity:** The failure category inference was rewritten to use `patchGenerated` (whether the model ever called `apply_patch`) and `finalDiff` (what `git diff` reports after the loop) as authoritative signals, rather than the `patchApplied` bookkeeping flag which could be stale.

### E. Evaluation Protocol

Each task-strategy combination is run 3 independent times (81 total runs). The same model (Claude Sonnet 4.6), temperature, and system prompt are used across all strategies. The iteration cap is 30 for MCP and 3 refinement rounds for RAG. A run is scored as a pass if and only if the expected failing tests pass in the final ground-truth `pytest` invocation after the agent's last action — independent of what the agent claims.

### F. Controlled Variables

Across all runs: same LLM at the same temperature; same iteration limit and stopping conditions; Python 3.12 execution environment; no external network access during runs; identical task patches applied through the same script; Git reset between every run.

---

## VI. Evaluation Metrics

We collect metrics in four areas.

### A. Effectiveness

Pass rate per task per strategy across 3 runs, and pass@k (probability that at least one of k attempts succeeds), following the protocol from Chen et al. [1]. Pass@k captures the probability that at least one of k attempts succeeds, which is meaningful when model variance is high.

### B. Efficiency

Number of repair iterations before success or cap; wall-clock runtime per task; total token usage broken down into input and output. These three together give a picture of operating cost.

### C. Reliability

Rather than tracking generic hallucination, we track failure categories that have direct operational meaning: `no_patch` (model never attempted to modify any file), `patch_apply_failure` (model generated a patch that the version control system rejected), `wrong_logic` (patch applied but tests still fail), `environment_error` (infrastructure failure before LLM call), and `provider_error` (API rate limit or credit exhaustion during the run).

### D. Strategy-Specific Signals

For RAG: context precision, defined as `min(1.0, files_changed / files_accessed)`, measuring how targeted the retrieval was relative to the actual edit.

For MCP: iteration count, tool calls per run, and proportion of runs reaching the 30-iteration ceiling.

For Prompt-Only: total tokens consumed relative to context window capacity, as context saturation is the primary failure mode at scale.

---

## VII. System Architecture

The evaluation framework consists of four layers: the LLM agent, the experiment harness, the three strategy implementations, and the target repository.

```
LLM Agent
    │
Experiment Harness (Reset · Route · Collect Metrics · Persist JSON)
    │
    ├── Strategy A: Prompt-Only  ──►  Static Snapshot  ──►  One-shot patch
    ├── Strategy B: RAG          ──►  BM25 Index + Top-K  ──►  Iterative patch
    └── Strategy C: MCP          ──►  MCP Server (STDIO)  ──►  Agent loop patch
    │
Target Repository (pyservicelab + pytest)
```

**Experiment Harness.** Before each run, the harness resets the repository via Git, applies the task fault patch, and routes execution to the selected strategy module. It enforces the iteration cap, detects the stopping condition when all expected tests pass, and writes a structured JSON result file containing all collected metrics. The same harness code runs for all three strategies, making timing and logging identical across conditions.

**Strategy Implementations.** Strategy A assembles all production Python source files and the failing test file into a single prompt. Strategy B queries the in-memory BM25 index and injects the top-8 chunks. Strategy C spawns the MCP server subprocess, connects the agent to it, and manages the tool-call loop including context summarization, staleness detection, and early exit.

**MCP Server.** The server runs as a TypeScript subprocess over STDIO and enforces: a `READ_FILE_CHAR_LIMIT` of 8,000 characters per file read (to prevent any single read from consuming the full output budget); schema validation on every tool call; and sequential execution ordering when `apply_patch` and `run_tests` appear in the same response turn (to prevent the test read from racing the file write).

---

## VIII. Results

### A. RQ1 — Success Rate

Table II shows pass rates across all 81 runs.

**Table II: Pass Rate by Task and Strategy (3 runs each)**

| Task | Type | RAG | Prompt-Only | MCP |
|------|------|:---:|:-----------:|:---:|
| task_01 | bug_fix | 3/3 | 2/3 | 3/3 |
| task_02 | bug_fix | 3/3 | 2/3 | 3/3 |
| task_03 | bug_fix | 3/3 | 3/3 | 2/3 |
| task_04 | bug_fix | 3/3 | 3/3 | 3/3 |
| task_05 | bug_fix | **0/3** | 3/3 | 3/3 |
| task_06 | feature | 3/3 | 3/3 | **0/3** |
| task_07 | feature | 3/3 | 3/3 | 2/3 |
| task_08 | test_fix | 3/3 | 3/3 | 3/3 |
| task_09 | test_fix | 3/3 | 3/3 | **0/3** |
| **Total** | | **24/27 (89%)** | **25/27 (93%)** | **19/27 (70%)** |

Prompt-Only achieves the highest aggregate pass rate (93%), followed by RAG (89%), then MCP (70%). Across task types: all three strategies achieve high pass rates on `bug_fix` tasks (RAG: 14/15, Prompt: 14/15, MCP: 14/15), but diverge on `feature` and `test_fix` tasks. RAG passes all feature and test_fix tasks. Prompt-Only passes all feature tasks. MCP fails all three runs of both task_06 (feature synthesis) and task_09 (test_fix), representing 0% reliability on two of the nine tasks.

The tasks on which all three strategies pass consistently (task_01, task_02, task_04, task_08) correspond to bugs with direct tracebacks that name the target file — the simplest context-navigation scenario. The tasks that differentiate strategies correspond to either semantic reasoning gaps (task_05: requires inferring correct return semantics), feature synthesis (task_06, task_07: requires generating new SQL code), or assertion literal correction requiring commitment (task_09).

Pass@3 values — the probability that at least one of three runs succeeds — are shown in Table III.

**Table III: Pass@3 by Strategy**

| Strategy | Tasks with Pass@3 = 1.0 | Tasks with Pass@3 < 1.0 | Overall Pass@3 |
|----------|------------------------|------------------------|----------------|
| RAG | 8/9 | task_05 (0.0) | 0.89 |
| Prompt-Only | 7/9 | task_01 (0.67), task_02 (0.67) | 0.93 |
| MCP | 6/9 | task_06 (0.0), task_07 (0.67), task_09 (0.0) | 0.78 |

### B. RQ2 — Efficiency

**Token Consumption.** Table IV shows average token usage per task across 3 runs.

**Table IV: Average Token Consumption per Task (tokens)**

| Task | RAG | Prompt-Only | MCP |
|------|----:|------------:|----:|
| task_01 | 8,601 | 42,581 | 21,362 |
| task_02 | 7,127 | 27,881 | 15,009 |
| task_03 | 8,348 | 43,330 | 86,139 |
| task_04 | 8,279 | 42,224 | 46,527 |
| task_05 | 28,312 | 45,020 | 49,997 |
| task_06 | 8,486 | 42,136 | 65,782 |
| task_07 | 6,693 | 42,434 | 74,492 |
| task_08 | 7,927 | 41,825 | 16,855 |
| task_09 | 7,598 | 42,624 | 152,028 |
| **Average** | **10,152** | **41,117** | **58,688** |

RAG consumes an average of 10,152 tokens per task — 4.1× fewer than Prompt-Only (41,117) and 5.8× fewer than MCP (58,688). RAG token cost is nearly flat across tasks (6,693–8,601 tokens on passing tasks), with the only outlier being task_05 (28,312) where all three refinement rounds are exhausted before success. Prompt-Only cost is almost perfectly constant (41,794–45,051 tokens) regardless of task difficulty, reflecting the fixed cost of loading the entire codebase. MCP cost is highly variable: 9,143 tokens for a successful 5-iteration run (task_02, run_3) up to 183,377 tokens for a failing 30-iteration run (task_09, run_1). This unpredictability is a fundamental consequence of the agent loop structure.

**Iteration Count.** Table V shows average iterations per task.

**Table V: Average Iterations per Task**

| Task | RAG | Prompt-Only | MCP |
|------|----:|------------:|----:|
| task_01 | 1.3 | 1.0 | 8.7 |
| task_02 | 1.0 | 0.7 | 7.0 |
| task_03 | 1.0 | 1.0 | 18.3 |
| task_04 | 1.0 | 1.0 | 12.7 |
| task_05 | 3.0 | 1.0 | 12.0 |
| task_06 | 1.0 | 1.0 | 14.3 |
| task_07 | 1.0 | 1.0 | 17.0 |
| task_08 | 1.0 | 1.0 | 5.7 |
| task_09 | 1.0 | 1.0 | 28.3 |
| **Average** | **1.3** | **1.0** | **13.8** |

RAG and Prompt-Only both converge in 1 iteration for 8 of 9 tasks. MCP's iteration count ranges from 5.7 (task_08, a direct assertion fix) to 28.3 (task_09, a commitment-paralysis failure). The highest-iteration MCP tasks correspond either to consistent failures (task_09: 28.3, task_06: 14.3) or to high-variance multi-patch behavior (task_03: 18.3, task_07: 17.0).

**Runtime.** Table VI shows average wall-clock runtime per task.

**Table VI: Average Runtime per Task (milliseconds)**

| Task | RAG | Prompt-Only | MCP |
|------|----:|------------:|----:|
| task_01 | 5,882 | 6,757 | 10,429 |
| task_02 | 5,096 | 4,397 | 9,726 |
| task_03 | 8,371 | 6,376 | 29,558 |
| task_04 | 12,090 | 5,180 | 13,530 |
| task_05 | 26,033 | 4,009 | 13,487 |
| task_06 | 11,230 | 5,692 | 10,405 |
| task_07 | 3,860 | 5,689 | 17,906 |
| task_08 | 2,990 | 3,959 | 6,434 |
| task_09 | 4,049 | 11,012 | 23,279 |
| **Average** | **8,845** | **5,897** | **14,972** |

Prompt-Only is fastest on average (5.9 s), driven by a single API call per task. RAG is close (8.8 s). MCP is 2.5× slower than Prompt-Only on average, with worst-case runs reaching 58 s (task_03, run_1: 30 iterations). Prompt-Only runtime is nearly constant (3.3–11.0 s range); MCP runtime is proportional to iteration count and therefore unpredictable.

**Efficiency Summary.** Table VII summarizes relative efficiency.

**Table VII: Efficiency Summary (normalized to Prompt-Only)**

| Metric | RAG | Prompt-Only | MCP |
|--------|:---:|:-----------:|:---:|
| Pass rate | 89% | **93%** | **70%** |
| Token ratio vs Prompt | **0.25×** | 1.0× | 1.43× |
| Iteration ratio vs Prompt | 1.3× | **1.0×** | 13.8× |
| Runtime ratio vs Prompt | 1.5× | **1.0×** | 2.5× |

### C. RQ3 — Reliability

**Failure Category Distribution.** Table VIII shows all failures by category.

**Table VIII: Failure Count by Category**

| Category | Meaning | RAG | Prompt-Only | MCP |
|----------|---------|:---:|:-----------:|:---:|
| `wrong_logic` | Patch applied, tests still fail | 3 | 1 | 2 |
| `no_patch` | Model never attempted `apply_patch` | 0 | 0 | 3 |
| `environment_error` | Infrastructure failure before LLM call | 0 | 1 | 0 |
| `provider_error` | API rate limit / credit exhaustion | 0 | 0 | 3 |
| **Total** | | **3** | **2** | **8** |

MCP produced 8 failures across 27 runs, compared to 3 for RAG and 2 for Prompt-Only. MCP's dominant failure modes are `no_patch` (3 occurrences — 1 on task_06 run_1, 2 on task_09 runs_1 and_3) and `provider_error` (3 occurrences — 2 on task_06, 1 on task_09). The `provider_error` failures represent a qualitatively distinct failure mode not present in the other strategies: long-running agent loops accumulate enough tokens (100,000–183,000 per run) that the API returns rate-limit or credit-exhaustion errors mid-run. These are operational failures caused by the agent loop's token accumulation.

**Context Precision.** Table IX shows average context precision per task, defined as `min(1.0, files_changed / files_accessed)`.

**Table IX: Average Context Precision**

| Task | RAG | Prompt-Only | MCP |
|------|----:|------------:|----:|
| task_01 | 0.17 | 0.02 | 0.67 |
| task_02 | 0.14 | 0.01 | 0.83 |
| task_03 | 0.13 | 0.02 | 0.31 |
| task_04 | 0.20 | 0.02 | 0.31 |
| task_05 | 0.13 | 0.00 | 0.36 |
| task_06 | 0.14 | 0.02 | 0.11 |
| task_07 | 0.20 | 0.02 | 0.25 |
| task_08 | 0.17 | 0.02 | 0.67 |
| task_09 | 0.17 | 0.02 | 0.22 |
| **Average** | **0.16** | **0.02** | **0.41** |

MCP achieves the highest context precision (0.41): on easy tasks it reads 2–3 files and changes 1, yielding 0.67–0.83. On harder tasks it reads more broadly, dropping to 0.11–0.36. Prompt-Only has the lowest precision (0.02): it always loads all ~50 files but changes only 1. RAG falls in between (0.16). Notably, MCP's higher precision does not translate to higher accuracy — it accesses only what it needs, but the exploration process itself is less reliable than static injection.

**Per-Run Reproducibility.** A key reliability finding is that single-run estimates of pass rate are unreliable. The Prompt-Only strategy shows 67% pass rate for task_01 and task_02 across 3 runs, despite appearing to pass in prior single-run tests. MCP shows 67% pass rate for task_03 and task_07, with the failing run consuming 4–5× the tokens of the passing runs. RAG shows perfectly consistent token consumption across 3 runs on all passing tasks (variance < 5%), while MCP shows up to 7× variance within the same task.

### D. RQ4 — Task Sensitivity

**By task type.** Table X summarizes pass rates by task category.

**Table X: Pass Rate by Task Category**

| Category | Tasks | RAG | Prompt-Only | MCP |
|----------|-------|:---:|:-----------:|:---:|
| bug_fix | 5 | 14/15 (93%) | 14/15 (93%) | 14/15 (93%) |
| feature | 2 | 6/6 (100%) | 6/6 (100%) | 2/6 (33%) |
| test_fix | 2 | 6/6 (100%) | 6/6 (100%) | 3/6 (50%) |

All three strategies perform identically on bug_fix tasks (93%). The divergence is entirely in feature and test_fix categories. RAG and Prompt-Only both achieve 100% on these task types; MCP achieves only 33% on feature tasks and 50% on test_fix tasks.

**Feature tasks (task_06, task_07).** Feature tasks require generating new code from scratch. For task_06, the model must write a SQL `SELECT` query with `LIKE`, `LOWER()`, and `ORDER BY` clauses. RAG and Prompt-Only succeed because they see the full codebase including similar query patterns in other files — the model can infer the pattern from context. MCP fails task_06 consistently: the agent reads similar files but cannot commit to writing the new SQL code, spending all 30 iterations gathering more context without acting. Task_07 passes 2/3 in MCP but produces one 30-iteration failure (145,734 tokens) due to iterative over-patching.

**Test-fix tasks (task_08, task_09).** Task_08 requires changing a role string in a test assertion — a direct, single-literal fix. All strategies pass this consistently. Task_09 requires changing a count assertion from 2 to 3. The answer is directly visible in the test failure message. RAG and Prompt-Only both succeed every time. MCP fails every time: the agent reads the test file, then reads production code to verify the correct count, then reads more code, and never commits to changing the literal. This is commitment paralysis: the agent has the answer but cannot act without additional verification that never arrives.

**Fault locality.** Tasks where the bug is directly named in the traceback (task_01, task_02, task_08) resolve quickly across all strategies. Tasks where the bug is in a utility called transitively by the failing test (task_03: `validate_non_empty` called by services) or where the stub removed identifying tokens (task_05, task_06) create difficulties specifically for strategies that rely on lexical matching. RAG overcame this for task_03 and task_06 through the source-file boost, but still fails task_05 where no lexical signal points to the correct semantic fix.

### E. Hypothesis Verification

**H1 — Simple faults will not differentiate the strategies.** *Partially confirmed.* The four tasks on which all three strategies achieve 3/3 pass rates (task_01, task_02, task_04, task_08) are indeed the most direct: the bug is visible in the traceback and the target file is lexically obvious. However, task_03 differentiates strategies at the run level even though it is a single-function fix — MCP's 30-iteration failure run on task_03 demonstrates that even simple faults can cause catastrophic cost under certain agentic behaviors.

**H2 — MCP will produce fewer bad patches.** *Refuted.* MCP produced the most failures (8 vs. 3 for RAG and 2 for Prompt). The structured tool interface does prevent malformed file references (the server rejects invalid paths immediately), but this advantage is outweighed by the agent's tendency toward commitment paralysis and the operational cost of long-running loops. The dominant failure modes are `no_patch` (agent never tried) and `provider_error` (API exhaustion), neither of which is addressed by schema validation.

**H3 — Prompt-Only will cost the most tokens.** *Refuted.* The actual token ordering is MCP > Prompt-Only > RAG. MCP consumed an average of 58,688 tokens per task, 43% more than Prompt-Only's 41,117. The agent loop's iterative LLM calls accumulate tokens at a rate proportional to iteration count, and on hard tasks (task_09: 152,028 average; task_03: 86,139 average) this far exceeds the fixed cost of loading the full codebase once. The hypothesis assumed MCP would terminate quickly on each task; instead, hard tasks push the agent to the 30-iteration ceiling.

**H4 — RAG will be sensitive to retrieval quality.** *Confirmed.* RAG's single consistent failure (task_05, 0/3) is a retrieval quality failure of a specific kind: the correct file (`db/user_repo.py`) is retrieved, but the retrieved chunk shows only the stubbed `return False` with no semantic signal about what the return value should be. The model cannot infer `return row is not None` from the stub and the test error message alone. This confirms that retrieval coverage (the right file was present) is a necessary but not sufficient condition for RAG success — the content of retrieved chunks must provide enough semantic context for the generation step.

---

## IX. Discussion

### A. Why MCP Underperforms on a Small Repository

MCP's value proposition is grounded in scenarios where the model cannot know what it needs without exploring first. In a large codebase spanning hundreds of files and thousands of functions, dynamic tool use allows the agent to navigate to relevant code without loading everything. In our setting, the full repository fits in a 42,000-token prompt — well within this model's context window. This means that Prompt-Only can provide complete information at lower cost than MCP's exploration loop provides partial information.

The agent loop's cost grows proportionally with difficulty: easy tasks (task_01, task_08) resolve in 4–9 iterations at 8,000–22,000 tokens, which is comparable to Prompt-Only. Hard tasks (task_03, task_07, task_09) push toward 30 iterations and 80,000–183,000 tokens, far exceeding Prompt-Only's fixed ~42,000 tokens. This asymmetry means MCP is simultaneously less reliable and more expensive than Prompt-Only on this benchmark — a result that would reverse as codebase size grows beyond the context window.

### B. Commitment Paralysis as a Failure Mode

Three `no_patch` failures (task_09 runs 1 and 3, and task_06 run 1) represent a failure mode with no analog in RAG or Prompt-Only: the model has gathered enough context to fix the bug but cannot commit to acting. This appears in two flavors:

*Verification-seeking paralysis* (task_09): the fix is a single literal change visible in the test failure message, but the agent reads production code to "verify" the correct count before changing the test. It keeps finding more files to read, never reaching certainty, and exhausts the iteration budget without acting.

*Synthesis paralysis* (task_06): the fix requires writing new SQL code. The agent reads similar query patterns in other files but cannot commit to writing the new function, preferring to gather more context over acting on incomplete confidence.

Both forms of paralysis reflect a fundamental property of agentic loops with no economic pressure: each additional tool call feels like progress. Unlike a human developer who pays a cognitive cost for searching, the agent faces no cost for "one more read." The staleness nudge partially addresses this but cannot fully override the agent's preference for information over action.

### C. RAG's Retrieval-Reasoning Boundary

RAG demonstrates that selective context access can achieve near-Prompt-level accuracy (89% vs. 93%) at a fraction of the cost (4× cheaper). The implementation improvements — IDF weighting, source-file priority boost, and per-file deduplication — were necessary to achieve this result; the baseline retrieval (equal-weight BM25 without source boost) failed on four of nine tasks.

The one consistent failure (task_05) identifies a boundary: retrieval can surface the right file, but if the content of the retrieved chunk does not contain enough semantic signal for the generation step, the model fails. The stub in task_05 (`return False`) is syntactically valid and provides no contextual hint about the correct replacement. This is a retrieval-coverage problem (the file was retrieved) combined with a content-sufficiency problem (the chunk content is not enough). No retrieval improvement can solve this without providing the model semantic knowledge about what `email_exists` should semantically return.

### D. Prompt-Only's Ceiling

Prompt-Only achieves the highest pass rate on this benchmark, but this result has a clear boundary condition: the codebase must fit in the model's context window. At 42,000 tokens for this repository, the approach works. For a production codebase of 500,000+ tokens, it would fail before any LLM call is made.

The two Prompt-Only failures also highlight a different ceiling: even with perfect information, probabilistic sampling introduces non-determinism. task_01 passed in 2 of 3 runs with identical context — the single failure was not a knowledge problem but a sampling one. Pass@3 captures this correctly (task_01 pass@3 = 0.67), whereas a single-run evaluation would have shown either 100% or 0% with equal probability.

### E. The Value of Multiple Runs

A single run per strategy per task would have produced materially different conclusions. In our data, several tasks that appeared to pass 100% in prior single-run tests showed degraded pass rates at 3 runs: Prompt-Only task_01 and task_02 show 67% pass rate with LLM variability failures. MCP task_05 appeared to fail in prior testing but shows 3/3 success in the baseline (the prior failure was a different run configuration). MCP task_03, which appeared catastrophically expensive in a single run (156,450 tokens), shows that 2/3 runs complete in 38,000–58,000 tokens; the 30-iteration run was a high-variance outlier.

These observations validate the use of pass@k as an evaluation metric rather than binary pass/fail from single-run testing.

---

## X. Conclusion

This paper presented a controlled comparison of three context-access strategies — Prompt-Only, RAG, and MCP — for repository-level LLM software engineering tasks. Using nine tasks across three categories and three independent runs per combination (81 total runs), we find that:

1. **No single strategy dominates.** Prompt-Only achieves the highest pass rate (93%) but is bounded by context-window capacity. RAG achieves 89% at 4× lower token cost. MCP achieves 70% with the highest operational overhead and the most failures.

2. **Token cost ordering is the inverse of the hypothesis.** MCP consumes more tokens per task than Prompt-Only (58,688 vs. 41,117) because agent loop overhead on hard tasks outpaces the cost savings from selective access. The assumed ordering (Prompt > RAG > MCP) holds only when MCP tasks resolve quickly; on hard tasks it reverses.

3. **MCP's reliability advantage does not materialize at this scale.** The structured tool interface prevents malformed file path references, but the dominant MCP failure modes — commitment paralysis (`no_patch`) and API exhaustion (`provider_error`) — are not addressed by schema validation. MCP produced 8 failures compared to 3 for RAG and 2 for Prompt-Only.

4. **Task type is a stronger predictor of strategy performance than task difficulty.** All three strategies achieve 93% on bug_fix tasks. The differentiation occurs on feature and test_fix tasks, where MCP achieves only 33–50% while RAG and Prompt-Only both achieve 100%.

5. **MCP's advantages become relevant at codebase scale.** On a repository that fits in a single prompt, static context injection outperforms dynamic exploration. The crossover point where MCP's surgical access would outperform Prompt-Only's full-codebase injection occurs when the codebase exceeds the model's context window — a threshold not reached in this benchmark but routinely exceeded in production systems.

**Limitations.** The benchmark uses a synthetic repository with injected faults, which enables experimental control but limits ecological validity. All tasks involve single-file edits; multi-file repairs may favor MCP differently. Results use a single model (Claude Sonnet 4.6) and may not generalize to models with different tool-use proficiency. Three runs per condition provides pass@3 but is insufficient for fine-grained statistical analysis.

**Future Work.** The most direct extension is to evaluate these strategies on codebases that exceed the Prompt-Only context limit, which is where MCP's value proposition is strongest. A second extension is to combine strategies: RAG for context selection paired with an MCP test-execution loop would provide the cost efficiency of retrieval with the verification advantage of tool use. A third direction is studying commitment paralysis more formally — characterizing when and why agents fail to act on sufficient context has implications beyond code repair.

---

## References

[1] M. Chen, J. Tworek, H. Jun, Q. Yuan, H. P. de Oliveira Pinto, J. Kaplan, H. Edwards, Y. Burda, N. Joseph, G. Brockman, A. Ray, R. Puri, G. Krueger, M. Petrov, H. Khlaaf, G. Sastry, P. Mishkin, B. Chan, S. Gray, and W. Zaremba, "Evaluating Large Language Models Trained on Code," 2021. Available: https://arxiv.org/abs/2107.03374

[2] M. Tufano, C. Watson, G. Bavota, D. Poshyvanyk, M. Di Penta, and R. Oliveto, "An Empirical Study on Learning Bug-Fixing Patches in the Wild via Neural Machine Translation," in *Proc. 34th IEEE/ACM Int. Conf. Automated Software Engineering (ASE 2019)*, pp. 832–843, 2019.

[3] Z. Jiang et al., "Impact of Code Language Models on Automated Program Repair," 2023. Available: https://ieeexplore.ieee.org/document/10172517

[4] Y. Gao, Y. Xiong, X. Gao, K. Jia, J. Pan, Y. Bi, Y. Dai, J. Sun, and H. Wang, "Retrieval-Augmented Generation for Large Language Models: A Survey," 2023. DOI: https://doi.org/10.48550/arXiv.2312.10997

[5] X. Zhang et al., "RepoCoder: Repository-Level Code Completion Through Iterative Retrieval and Generation," 2023. Available: https://openreview.net/forum?id=oXl4q5RRmF

[6] T. Schick, J. Dwivedi-Yu, R. Dessì, R. Raileanu, M. Lomeli, E. Hambro, L. Zettlemoyer, N. Cancedda, and T. Scialom, "Toolformer: Language Models Can Teach Themselves to Use Tools," in *Int. Conf. Learning Representations (ICLR 2023)*, 2023.

[7] S. G. Patil, T. Zhang, X. Wang, and J. E. Gonzalez, "Gorilla: Large Language Model Connected with Massive APIs," 2023. DOI: https://doi.org/10.48550/arXiv.2305.15334

[8] S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan, and Y. Cao, "ReAct: Synergizing Reasoning and Acting in Language Models," in *Int. Conf. Learning Representations (ICLR 2023)*, 2023.

[9] R. Nakano, J. Hilton, S. Balaji, J. Wu, L. Ouyang, C. Kim, C. Hesse, A. Jain, V. Kosaraju, W. Saunders, X. Jiang, K. Cobbe, T. Eloundou, G. Krueger, K. Button, and J. Schulman, "WebGPT: Browser-Assisted Question-Answering with Human Feedback," in *Advances in Neural Information Processing Systems (NeurIPS 2021)*, 2021.

[10] C. E. Jimenez, J. Yang, A. Wettig, S. Yao, K. Pei, O. Press, and K. Narasimhan, "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?" in *Advances in Neural Information Processing Systems (NeurIPS 2023)*, 2023.

[11] Z. Liu et al., "AgentBench: Evaluating LLMs as Agents," 2024. DOI: https://doi.org/10.48550/arXiv.2308.03688
