# Design Decisions

PyServiceLab MCP Server — complete record of architectural and security decisions,
constraints, and implicit assumptions.

---

## 1. Transport

**Decision:** STDIO only (newline-delimited JSON, MCP SDK 1.27+).

- No HTTP server, no Express, no REST endpoints.
- One client per process — the server has no concept of sessions or connection
  multiplexing.
- Stdout is reserved exclusively for the MCP protocol. All diagnostics go to
  `logs/mcp.log`. Nothing is written to stderr except fatal startup errors.

---

## 2. Sandbox root

**Decision:** All file operations are restricted to `../target-repo` relative to
the server's working directory (i.e., `process.cwd()/../target-repo`).

- Overridable at startup via the `TARGET_REPO` environment variable.
  `TARGET_REPO` is resolved with `path.resolve()` so both absolute and relative
  values are accepted.
- The boundary is enforced by `resolveSafe()` in `file_utils.ts`:
  1. `path.resolve(base, userPath)` normalises the joined path (collapses `..`,
     symlink resolution is **not** performed — see limitations).
  2. `path.relative(normalBase, resolved)` computes the relative offset.
  3. If the relative path starts with `..` or is itself absolute, the request
     is rejected with an error — no partial access is granted.
- `.git/` **is accessible** — no special exclusion of `.git` was added. An
  agent can read `.git/` files such as `COMMIT_EDITMSG`, `config`, etc.

---

## 3. File size limits

**Decision:** 200 KB hard cap on all file reads.

- Applied in `read_file` before calling `fs.readFileSync`.
- Applied in `search_in_files` as a per-file skip threshold (files larger than
  200 KB are silently skipped, not errored).
- The limit is defined as the constant `MAX_FILE_SIZE = 200 * 1024` in
  `file_utils.ts` and re-declared locally in `search_in_files.ts` as
  `MAX_FILE_READ`.
- No limit is enforced on `apply_patch` input size — the patch string can be
  arbitrarily large (bounded only by the JSON message size, which is not
  capped by the server).

---

## 4. Path normalisation

**Decision:** Paths are normalised via `path.resolve()` before the sandbox check.

- `path.resolve()` collapses `.` and `..` segments and converts to an absolute
  path.
- Paths are **not** canonicalised via `fs.realpath()`, so symlinks inside the
  sandbox that point outside it are not detected.
- No URL-encoding or percent-decode step is applied — the assumption is that the
  MCP client passes literal filesystem path strings.

---

## 5. list_files — directory listing only (non-recursive)

**Decision:** `list_files` reads a single directory level only.

- `fs.readdirSync(resolved, { withFileTypes: true })` lists immediate children.
- Results are split into two sorted arrays: `files` and `directories`.
- Sorting is locale-sensitive (`Array.prototype.sort()` default), which is
  OS-dependent.
- Symlinks are classified by `entry.isFile()` / `entry.isDirectory()`, so
  symlinks to files appear in `files` and symlinks to directories appear in
  `directories`. Broken symlinks are omitted from both arrays.

---

## 6. search_in_files — plain-text substring search

**Decision:** Search uses `String.prototype.includes()` — literal substring,
case-sensitive, no regex.

- No user-supplied regex to prevent ReDoS.
- Files are read as UTF-8; files that throw on read (binary, permission denied,
  encoding errors) are silently skipped via the inner `try/catch`.
- Files over 200 KB are skipped before reading (size check via `stat`).
- Search is recursive via `walkFiles()`, which depth-first traverses all
  subdirectories. There is no depth limit.
- Match limit: 1–500, default 50. Controlled by Zod schema.
- `file` paths in results are **absolute** paths on the server filesystem, not
  paths relative to `target-repo`. This leaks the server's absolute path.
- Matching line content is trimmed (`String.prototype.trim()`), so leading/
  trailing whitespace is stripped in results.

---

## 7. run_tests — command whitelist

**Decision:** Only `pytest`, `python -m pytest`, and `python3 -m pytest`
invocations are allowed.

- Validated by splitting the command string on whitespace, checking the first
  token against `ALLOWED_BASES = { "pytest", "python", "python3" }`.
- For `python`/`python3`, the next two tokens must be exactly `-m` and `pytest`.
- Arguments beyond `-m pytest` are passed through to pytest unchanged — no
  further validation of pytest flags or paths. A caller can pass arbitrary
  pytest arguments including `--rootdir`, plugin flags, etc.
- Executed via `execFile` (no shell), so shell metacharacters in arguments
  are safe.
- Timeout: 60 seconds.
- stdout/stderr buffer: 2 MB (`maxBuffer`). Output exceeding this causes the
  process to be killed and an error returned.
- `exit_code` for timed-out processes uses `error.code` from the `execFile`
  callback, which is `null` (not a number) for timeout — falls back to `1`.
- Raw stdout and stderr are returned unparsed. No test-result parsing is done.

---

## 8. apply_patch — git apply via temp file

**Decision:** Patch content is written to a temp file in `os.tmpdir()`, then
`git apply <tempfile>` is run.

- Temp file name: `mcp_patch_${Date.now()}.patch` — millisecond timestamp.
  A collision is possible if two patches are applied in the same millisecond.
- `git apply` is run with a 10-second timeout.
- Temp file is cleaned up in `finally` (best-effort; silently ignored if
  deletion fails).
- No size cap on the patch string.
- No validation of patch content beyond checking it is a non-empty string.
  Invalid diffs are rejected by `git apply` with an error message.
- `git apply` operates on the working tree only (`--index` is not passed), so
  patches are applied as unstaged changes.

---

## 9. git_diff — unstaged changes only

**Decision:** `git diff` with no arguments returns only unstaged working-tree
changes.

- Staged changes (in the index) are **not** included. To see staged changes
  `git diff --cached` would be needed.
- No flags like `--stat` or `--name-only` are passed; output is the full patch
  format.
- 10-second timeout.
- Output size is bounded by `maxBuffer` (2 MB).

---

## 10. Error handling strategy

**Decision:** Errors never crash the server process.

- Tool functions catch all errors, log them, and re-throw.
- `index.ts` catches at the dispatch level:
  - `McpError` is re-thrown as-is (carries an explicit JSON-RPC error code).
  - `ZodError` is converted to `ErrorCode.InvalidParams`.
  - All other errors are converted to `ErrorCode.InternalError`.
- The MCP SDK handles serialising these errors into JSON-RPC error responses.
- `main()` has a top-level `.catch()` that writes to stderr and calls
  `process.exit(1)` only for fatal startup failures (e.g., transport bind
  failure).
- `writeLog()` wraps its `fs.appendFileSync` in a `try/catch` so a log write
  failure never propagates to the caller.

---

## 11. Logging

**Decision:** Structured JSON log entries, one per line, appended to
`logs/mcp.log`.

- Log directory is created on every write via `fs.mkdirSync(LOG_DIR,
  { recursive: true })`. This is an `O(1)` syscall if the directory already
  exists but is called on every single log write.
- Arguments are truncated to 200 characters before logging (to prevent large
  patch content from bloating the log).
- For `apply_patch`, the log entry records `patchSizeBytes` instead of the
  patch content, to avoid enormous log entries.
- `bytesReturned` counts the length of the JSON-stringified result string, not
  the actual bytes sent on the wire (which may differ due to serialisation
  overhead in `index.ts`).
- Logging is synchronous (`appendFileSync`), which blocks the event loop.

---

## 12. No caching, no rate limiting, no concurrency control

**Decision:** The server is stateless per-call. No caching layer. No in-flight
request tracking.

- Concurrent tool calls (if the MCP client sends multiple requests in flight)
  will execute concurrently without ordering guarantees.
- No rate limiting.
- No request IDs are tracked at the tool level (only at the SDK protocol level).

---

## 13. Validation library

**Decision:** Zod for all input validation.

- Each tool defines its own Zod schema (`ListFilesSchema`, `ReadFileSchema`,
  etc.).
- `rawArgs: unknown` is the type received by every tool function — validation
  is the first operation.
- `additionalProperties: false` is set in the JSON schema in `index.ts` (for
  the MCP tool description), but Zod schemas do not use `.strict()` by default
  — except `GitDiffSchema` which does use `.strict()`.

---

## 14. Environment variable exposure

**Decision:** Only `TARGET_REPO` is read from the environment. No other
environment variables are read or returned.

- The `TARGET_REPO` value affects the sandbox root and is therefore a trusted
  configuration input, not user-controlled.

---

## 15. No network access

**Decision:** No outbound or inbound network connections are made.

- No `fetch`, `http`, `https`, `net`, or `dgram` usage.
- `execFile` spawns child processes without `shell:true`, so shell-based
  network commands via pytest arguments remain possible if pytest plugins
  allow it.
