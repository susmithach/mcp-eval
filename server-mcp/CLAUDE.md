# Claude Development Rules – MCP Server

This file defines strict implementation constraints for the PyServiceLab MCP server.

Claude must follow these rules without deviation.

---

## 1. Architecture Rules

- Use official MCP SDK
- Use STDIO transport only
- DO NOT implement HTTP server
- DO NOT use Express
- DO NOT use Fastify
- DO NOT use HTTP or HTTPD
- No REST endpoints

---

## 2. Security Constraints

- Prevent path traversal
- Restrict file access to ../target-repo
- Reject "../" path attempts
- Enforce file size limits
- Do NOT allow arbitrary shell commands
- run_tests must not execute arbitrary input
- No network requests
- No environment variable exposure

---

## 3. Logging Requirements

- Log every tool invocation
- Log execution duration
- Log truncated arguments only
- Log to logs/mcp.log
- Logging must not block execution

---

## 4. Implementation Constraints

- Use Zod for validation
- No global mutable state
- No caching (minimal server only)
- No rate limiting
- No telemetry
- No analytics

---

## 5. Common Mistakes to Avoid

- Do NOT build HTTP server
- Do NOT allow arbitrary shell commands
- Do NOT allow arbitrary file access
- Do NOT expose filesystem root
- Do NOT allow unbounded patch size
- Do NOT forget timeout for test execution
- Do NOT crash on malformed input

---

## 6. Completion Checklist

Before stopping, Claude must:

1. Ensure all tools compile
2. Ensure build folder exists
3. Ensure logs directory exists
4. Ensure package.json scripts exist:
   - build
   - start
5. Ensure server starts without runtime errors


### Smoke Test Enforcement

Claude must ensure:

- A smoke client exists under scripts/
- It programmatically spawns the server
- It verifies:
  - Tool registration
  - Safe file listing
  - File read within limit
  - Search returns deterministic order
  - run_tests executes successfully
- The smoke test exits cleanly and terminates the server process
- No manual testing steps are allowed