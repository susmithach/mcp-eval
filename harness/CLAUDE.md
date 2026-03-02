# CLAUDE.md
## Harness Component Rules

This file governs how Claude must operate within the harness directory.

---

# 1. Separation of Concerns

Claude MUST NOT:

- Modify server-mcp logic
- Modify target-repo logic
- Introduce HTTP servers
- Introduce network calls
- Introduce hidden state
- Introduce randomness

The harness is orchestration only.

---

# 2. Determinism Enforcement

Claude MUST:

- Sort outputs before storing
- Avoid Date.now() in results
- Avoid random seeds unless fixed
- Avoid OS-specific assumptions
- Avoid nondeterministic JSON key ordering

---

# 3. Strategy Discipline

Claude MUST:

- Keep strategies isolated
- Ensure all strategies produce identical result schema
- Not give MCP hidden advantages
- Not leak repository metadata

---

# 4. Metrics Integrity

Claude MUST:

- Track tool call counts
- Track iteration counts
- Track runtime per run
- Store structured JSON only
- Never mix logs with results

---

# 5. Repository Control Safety

Claude MUST:

- Use spawn (no shell)
- Enforce cwd to target-repo
- Fail fast on subprocess errors
- Reset repo before every run

---

# 6. MCP Client Usage

Claude MUST:

- Spawn server per run
- Close server after run
- Not reuse global state across runs
- Track tool usage per run

---

# 7. Experimental Integrity

Claude MUST:

- Ensure prompt-only baseline is fair
- Ensure MCP baseline uses only MCP tools
- Avoid modifying task patches
- Avoid contaminating runs

---

# 8. Code Quality

Claude MUST:

- Use strict TypeScript
- Use explicit types
- Avoid implicit any
- Avoid global variables
- Keep functions small and isolated