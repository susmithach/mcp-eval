# PyServiceLab MCP Server

A minimal TypeScript MCP server that provides structured, sandboxed access to the PyServiceLab `target-repo` via stdio transport.

---

## Prerequisites

- Node.js 22+ (install via [nvm](https://github.com/nvm-sh/nvm) — see below)
- npm 10+
- Git (required by `apply_patch` and `git_diff` tools)
- Python 3 + pytest (required by `run_tests` tool)

### Install Node.js via nvm (WSL / Linux)

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.bashrc
nvm install 22
nvm use 22
node --version   # v22.x.x
```

---

## Setup

```bash
# From the server-mcp/ directory:
npm install
npm run build
```

The compiled output is written to `build/`.

---

## Target repository

All tools operate on `../target-repo` (relative to `server-mcp/`).
Place the repository you want to evaluate at that path before starting the server.

```
mcp-eval/
├── server-mcp/      ← this server
└── target-repo/     ← repository exposed to the MCP client
```

---

## Start

```bash
node build/index.js
```

The server reads JSON-RPC messages from **stdin** and writes responses to **stdout** (newline-delimited JSON, MCP SDK 1.27+). Do not write to stdout from any application code — it is reserved for the MCP protocol.

---

## Logs

Every tool invocation is appended to `logs/mcp.log` (auto-created on first call):

```json
{"timestamp":"2026-01-01T00:00:00.000Z","tool":"read_file","args":"{\"path\":\"src/main.py\"}","durationMs":3,"success":true,"bytesReturned":1024}
```

---

## Tools

| Tool | Description |
|------|-------------|
| `list_files` | List files and directories at a path inside `target-repo` |
| `read_file` | Read a file (max 200 KB) |
| `search_in_files` | Text search across files (max 500 matches) |
| `run_tests` | Run `pytest` or `python -m pytest` inside `target-repo` |
| `apply_patch` | Apply a unified diff via `git apply` |
| `git_diff` | Return current unstaged diff of `target-repo` |

All file paths are validated against `../target-repo` — path traversal is rejected.

---

## Manual test

Send a newline-terminated JSON-RPC message directly to stdin:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}' | node build/index.js
```

Expected response (one JSON line on stdout):
```json
{"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"server-mcp","version":"1.0.0"}},"jsonrpc":"2.0","id":1}
```

Or use the Python test helper:

```bash
python3 tests/manual_test.py
```

---

## package.json scripts

| Script | Command |
|--------|---------|
| `npm run build` | Compile TypeScript → `build/` |
| `npm start` | Start the compiled server |
| `npm run dev` | Watch mode (recompile on save) |
