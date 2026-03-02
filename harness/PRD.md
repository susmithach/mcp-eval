# Product Requirements Document (PRD)
## Component: Evaluation Harness
## Project: Evaluating Model Context Protocol (MCP) for Reliable Agentic AI

---

# 1. Purpose

The Evaluation Harness is responsible for:

- Running controlled experiments
- Resetting and mutating the target repository
- Executing agent strategies (prompt-only, MCP, RAG)
- Collecting structured metrics
- Persisting reproducible results

The harness MUST treat `server-mcp` as an external deterministic system.
The harness MUST NOT modify server-mcp logic.

---

# 2. Scope

The harness is responsible for:

- Experiment orchestration
- Strategy execution
- Metrics collection
- Result storage
- Deterministic experiment control

The harness is NOT responsible for:

- Implementing MCP tools
- Modifying target-repo source code directly
- Injecting randomness
- Network access

---

# 3. Directory Structure

The harness MUST follow this structure:

harness/
├── src/
│ ├── mcp/
│ │ └── client.ts
│ ├── runner/
│ │ ├── repo.ts
│ │ ├── metrics.ts
│ │ ├── result_schema.ts
│ │ └── run_task.ts
│ ├── strategies/
│ │ ├── prompt_only.ts
│ │ ├── mcp.ts
│ │ └── rag.ts
├── results/
├── prompts/
├── package.json
└── tsconfig.json



---

# 4. Core Responsibilities

## 4.1 Repository Control

File: `src/runner/repo.ts`

The harness MUST:

- Reset the repository before every run
- Apply exactly one task patch per run
- Use deterministic execution

Implementation requirements:

- Use `spawn`
- No shell execution
- Set `cwd` to `target-repo`
- Reject failures immediately

Commands:

- Reset:
  python ../target-repo/scripts/reset_repo.py

- Apply Task:
  python ../target-repo/scripts/apply_task.py <task_patch>

---

## 4.2 MCP Client Wrapper

File: `src/mcp/client.ts`

The harness MUST:

- Spawn `../server-mcp/build/index.js`
- Connect via `StdioClientTransport`
- Provide typed wrappers:
  - listFiles()
  - readFile()
  - searchInFiles()
  - runTests()
  - applyPatch()
  - gitDiff()

The client MUST:

- Track tool call counts
- Track runtime per call
- Remain deterministic
- Not modify tool contracts

---

## 4.3 Strategy Execution

File: `src/runner/run_task.ts`

Each run MUST:

1. Reset repository
2. Apply task patch
3. Execute strategy loop
4. Collect metrics
5. Save results JSON
6. Exit cleanly

---

# 5. Strategy Interface

Each strategy MUST implement:

TypeScript interface:

interface Strategy {
  run(taskId: string): Promise<ResultSchema>;
}

Strategies MUST:

- Not bypass repo reset
- Not bypass result schema
- Not introduce randomness
- Not modify server-mcp behavior

---

# 6. Result Schema

File: `src/runner/result_schema.ts`

Each run MUST produce a JSON object with this exact structure:


{
"task_id": "task_01",
"strategy": "mcp",
"run_id": 1,
"success": true,
"iterations": 4,
"runtime_ms": 8423,
"tool_calls_total": 17,
"tool_calls_by_name": {
"read_file": 6,
"search_in_files": 4,
"run_tests": 3
},
"tokens_in": 0,
"tokens_out": 0,
"final_diff": "string",
"error": null
}


All strategies MUST produce this identical schema.

---

# 7. Determinism Requirements

The harness MUST:

- Avoid randomness
- Avoid timestamps inside result fields
- Use sorted outputs
- Avoid OS-dependent logic
- Avoid hidden state
- Use fixed seeds if LLM is integrated

---

# 8. Experiment Protocol (Initial Phase)

Initial experiment configuration:

- 3 tasks
- 3 runs per task
- Compare:
  - Prompt-only
  - MCP

Metrics:

- Test success rate
- Iteration count
- Tool call count
- Runtime
- Token usage
- Diff size

---

# 9. Future Extensions

- RAG baseline
- Statistical analysis module
- Automated summary report
- Confidence interval computation