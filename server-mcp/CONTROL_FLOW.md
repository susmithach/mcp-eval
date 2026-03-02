# Control Flow

Step-by-step walkthrough of the MCP server from process start to tool response.

---

## 1. Process startup (`src/index.ts → main()`)

```
node build/index.js
```

1. Node.js loads `build/index.js` (ESM module).
2. Top-level module evaluation runs in order:
   a. SDK imports resolved (`McpServer`, `StdioServerTransport`, schemas, etc.).
   b. Tool function imports resolved (each tool module is evaluated; each calls
      `createLogger(toolName)` at module scope, capturing the tool name in a
      closure — no I/O at this point).
   c. `new McpServer(...)` constructs the server instance with capabilities
      `{ tools: {} }`.
   d. Two `setRequestHandler()` calls register handlers for
      `ListToolsRequestSchema` and `CallToolRequestSchema` on the server.
3. `main()` is called (async).
4. `new StdioServerTransport()` is constructed — no I/O yet, just wires up
   references to `process.stdin` and `process.stdout`.
5. `await server.connect(transport)` is called:
   a. SDK calls `transport.start()`, which registers `process.stdin` data and
      error listeners.
   b. The server is now listening. `process.stdin` is in flowing mode.
6. `main()` returns. The Node.js event loop keeps the process alive because
   `process.stdin` has active listeners.

---

## 2. MCP initialization handshake (client-initiated)

The client sends:
```
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}\n
```

Flow inside the SDK:

1. `process.stdin` emits a `data` event with the raw chunk.
2. `StdioServerTransport._ondata(chunk)` appends the chunk to `ReadBuffer`.
3. `ReadBuffer.readMessage()` scans for `\n`, extracts the line, JSON-parses
   it, validates against `JSONRPCMessageSchema`.
4. `transport.onmessage(message)` is called — this is the SDK's internal
   Protocol handler.
5. The SDK matches the method `"initialize"` against its registered handler
   (registered automatically by `McpServer` constructor via
   `setRequestHandler(InitializeRequestSchema, ...)`).
6. The SDK's `_oninitialize` handler validates the protocol version, builds the
   server capabilities response.
7. The response is serialised via `serializeMessage()` → `JSON.stringify(msg) + "\n"`.
8. `transport.send(response)` calls `process.stdout.write(json)`.
9. The client receives the `initialize` result.
10. Client sends `{"method":"notifications/initialized"}` (a notification, no
    `id`). The SDK handles this internally; the `oninitialized` callback fires.

---

## 3. Tool listing (`tools/list` request)

Client sends:
```
{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n
```

1. Same stdin → ReadBuffer → transport.onmessage path as above.
2. SDK matches `"tools/list"` against the handler registered for
   `ListToolsRequestSchema`.
3. The handler (in `index.ts`) returns the hardcoded array of 6 tool
   definitions with their JSON schemas.
4. SDK serialises and sends the response.

---

## 4. Tool invocation (`tools/call` request)

Client sends (example):
```
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"read_file","arguments":{"path":"src/main.py"}}}\n
```

### 4a. Protocol layer (SDK)

1. ReadBuffer extracts the message.
2. SDK matches `"tools/call"` against the `CallToolRequestSchema` handler.
3. The async handler in `index.ts` is awaited.

### 4b. Dispatch (`index.ts` handler)

1. `request.params.name` and `request.params.arguments` are destructured.
2. A `switch` on `name` routes to the appropriate tool function.
3. The tool function is `await`-ed.

### 4c. Tool execution (example: `read_file`)

1. `ReadFileSchema.parse(rawArgs)` — Zod validates that `args` is
   `{ path: string (min 1) }`. Throws `ZodError` on failure (caught at 4d).
2. `getTargetRepo()` — reads `TARGET_REPO` env var or defaults to
   `path.resolve(process.cwd(), "../target-repo")`. Returns an absolute path.
3. `resolveSafe(base, args.path)` — joins and normalises the path, checks the
   sandbox boundary. Throws `Error` on traversal (caught at 4d).
4. `start = Date.now()` — begin timing.
5. `assertExists(resolved)` — `fs.existsSync()` check. Throws on missing.
6. `assertIsFile(resolved)` — `fs.statSync()` check. Throws if not a file.
7. `getFileSize(resolved)` — `fs.statSync().size`.
8. Size check against `MAX_FILE_SIZE` (200 KB). Throws if over limit.
9. `fs.readFileSync(resolved, "utf8")` — synchronous file read.
10. `logger.log(args, durationMs, JSON.stringify(result), true)` — writes
    a JSON entry to `logs/mcp.log` via `fs.appendFileSync`. Blocks event loop
    briefly.
11. Returns `{ content, size }`.

### 4d. Error handling in dispatch

If the tool throws:
- `McpError` → re-thrown immediately.
- `ZodError` → wrapped in `McpError(ErrorCode.InvalidParams, ...)`.
- Any other `Error` → wrapped in `McpError(ErrorCode.InternalError, ...)`.

The tool's own catch block also calls `logger.log(..., false, errorMessage)`
before re-throwing, so errors are always logged.

### 4e. Response serialisation

On success:
```ts
return {
  content: [{ type: "text", text: JSON.stringify(result, null, 2) }]
}
```
The result object is JSON-stringified twice: once inside the tool's logger
call (`JSON.stringify(result)`) and once here with pretty-printing (`null, 2`).

The SDK wraps this in a JSON-RPC result envelope and sends it via
`transport.send()` → `process.stdout.write()`.

---

## 5. Process of `run_tests` (subprocess path)

This tool has an additional async subprocess step:

1. Zod parse → `RunTestsSchema`.
2. `parseCommand(args.command)` — whitelist check and split.
3. `getTargetRepo()` → `cwd`.
4. `runProcess(cmd, cmdArgs, cwd, 60_000)` — calls `execFile`:
   - No shell. The executable must be on `PATH`.
   - `cwd` is set to `target-repo`.
   - Timeout 60 s. `maxBuffer` 2 MB.
   - Runs asynchronously; the current Node.js event loop is free to process
     other requests while waiting.
5. `execFile` callback fires when the process exits or times out.
6. `runProcess` always resolves (never rejects). On timeout/error, `exitCode`
   defaults to `error.code ?? 1`.
7. Result `{ exit_code, stdout, stderr }` is returned and logged.

---

## 6. Process of `apply_patch` (temp-file path)

1. Zod parse.
2. `applyGitPatch(repoPath, patchContent)`:
   a. `path.join(os.tmpdir(), "mcp_patch_<timestamp>.patch")`.
   b. `fs.writeFileSync(tmpFile, patchContent, "utf8")` — synchronous.
   c. `runProcess("git", ["apply", tmpFile], repoPath, 10_000)` — async.
   d. On exit: check `exitCode === 0`; build result.
   e. `finally`: `fs.unlinkSync(tmpFile)` — synchronous cleanup.
3. Result `{ applied, error }` is returned.

---

## 7. Concurrency model

- The Node.js event loop is single-threaded.
- The MCP SDK processes incoming messages sequentially as they arrive.
- However, `async` tool handlers yield the event loop during I/O (subprocess
  execution, etc.), so a second incoming request can begin processing while
  the first is waiting on a subprocess.
- There is no request queue or mutex; tool calls can interleave.

---

## 8. Shutdown

There is no explicit shutdown handler. The process exits when:

- `process.stdin` closes (client disconnects) — the event loop drains and Node
  exits naturally.
- A fatal error reaches `main().catch()` → `process.exit(1)`.
- The parent process sends SIGTERM/SIGKILL.
