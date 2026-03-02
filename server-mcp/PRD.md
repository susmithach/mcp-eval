# Product Requirements Document (PRD)
## Project: PyServiceLab MCP Server

---

## 1. Objective

Build a minimal, secure, deterministic Model Context Protocol (MCP) server that provides structured access to the PyServiceLab dataset repository.

This server will be used to evaluate MCP-based context access against prompt-only and RAG-based approaches.

---

## 2. Technical Requirements

- Language: TypeScript
- Runtime: Node.js 20+
- Transport: STDIO only
- No HTTP server
- No web framework
- Use official MCP SDK
- Strict argument validation (Zod)
- Deterministic behavior
- No hidden state

---

## 3. Directory Structure

server-mcp/
  src/
    index.ts
    tools/
      list_files.ts
      read_file.ts
      search_in_files.ts
      run_tests.ts
      apply_patch.ts
      git_diff.ts
    utils/
      file_utils.ts
      process_utils.ts
      git_utils.ts
      logger.ts
  logs/
  package.json
  tsconfig.json
  README.md
  CLAUDE.md
  PRD.md

---

## 4. Target Repository Access

The MCP server must operate only on:

../target-repo

This path must be resolved safely and must not allow traversal outside that directory.

---

## 5. Tool Specifications

### 5.1 list_files

Input:
{
  "path": "string"
}

Output:
{
  "files": ["string"],
  "directories": ["string"]
}

Constraints:
- Must stay inside target-repo
- Must prevent path traversal

---

### 5.2 read_file

Input:
{
  "path": "string"
}

Output:
{
  "content": "string",
  "size": number
}

Constraints:
- File size limit: 200 KB
- No traversal
- Must not crash on binary files

---

### 5.3 search_in_files

Input:
{
  "query": "string",
  "path": "string",
  "limit": number
}

Output:
{
  "matches": [
    {
      "file": "string",
      "line": number,
      "content": "string"
    }
  ]
}

Constraints:
- Limit matches
- Text search only
- No regex execution from user input

---

### 5.4 run_tests

Input:
{
  "command": "string"
}

Output:
{
  "exit_code": number,
  "stdout": "string",
  "stderr": "string"
}

Constraints:
- Must execute only inside target-repo
- Enforce timeout
- No arbitrary shell execution

---

### 5.5 apply_patch

Input:
{
  "patch": "string"
}

Output:
{
  "applied": boolean,
  "error": "string | null"
}

Constraints:
- Accept unified diff format only
- Reject large patches
- Fail safely

---

### 5.6 git_diff

Input:
{}

Output:
{
  "diff": "string"
}

---

## 6. Logging Requirements

All tool calls must log:

- timestamp
- tool name
- execution time
- truncated arguments
- success/failure

Logs must be written to:

server-mcp/logs/mcp.log

---

## 7. Security Rules

- No HTTP server
- No HTTPD
- No Express
- No arbitrary shell execution
- No execution outside target-repo
- No environment variable leakage
- No external network access

---

## 8. Acceptance Criteria

1. `npm install` works
2. `npm run build` compiles TypeScript
3. `node build/index.js` starts server
4. All tools respond correctly
5. Invalid paths are rejected
6. No crashes on malformed input