# Limitations

Known weaknesses and edge cases in the MCP server that could affect
experimental validity, reproducibility, or security.

---

## 1. Nondeterministic file ordering in `list_files`

**Issue:** Results are sorted with `Array.prototype.sort()`, which uses the
locale-aware collation of the underlying JS engine. File ordering may differ
across OS, locale settings, or Node.js versions.

**Impact:** An agent that relies on a consistent file position (e.g., "the
third file in the list is always X") may behave differently across
environments. Logs cannot be compared across machines.

**Mitigation:** Sort is applied, so results are deterministic within the same
locale/runtime — not random. But locale-portability is not guaranteed.

---

## 2. Nondeterministic file traversal order in `search_in_files`

**Issue:** `walkFiles()` calls `fs.readdirSync()` on each directory. Directory
entry order is filesystem-dependent (ext4 returns entries in hash-table order,
not alphabetical). There is no sorting inside `walkFiles()`.

**Impact:** The order of matches returned for the same query will differ across
filesystems and after directory modifications. The limit cutoff (`break outer`)
will therefore produce different match sets depending on traversal order.

**Mitigation:** None currently. For strict reproducibility, callers should use
a high limit and sort/filter results themselves.

---

## 3. Symlink traversal is not sandboxed

**Issue:** `resolveSafe()` uses `path.resolve()`, which is purely lexical. It
does not call `fs.realpath()`. A symlink inside `target-repo` that points to a
path outside `target-repo` (e.g., `/etc/passwd`) will pass the sandbox check
and be accessible.

**Impact:** A malicious or misconfigured `target-repo` could expose arbitrary
host filesystem files.

**Mitigation:** The experimental setup controls `target-repo` contents, so
this is low-risk in practice. A production deployment should use
`fs.realpath()` (or equivalent) before the boundary check.

---

## 4. `.git/` directory is accessible

**Issue:** No exclusion of `.git/` from file operations. `list_files(".")`,
`read_file(".git/config")`, and `search_in_files` will all operate on `.git/`
contents.

**Impact:**
- `.git/config` may contain remote URLs, credentials (if stored insecurely),
  or author information that skews evaluation context.
- `search_in_files` will scan `.git/objects`, potentially matching binary pack
  files (skipped by size check) or loose object files.
- An agent aware of `.git/` might use commit history as an unfair information
  source during evaluation.

---

## 5. `search_in_files` returns absolute paths

**Issue:** The `file` field in each match is the absolute path on the server
host (e.g., `/home/monic/PyServiceLab/mcp-eval/target-repo/src/main.py`).

**Impact:**
- Leaks the server's filesystem layout to the client.
- Paths are not relative to `target-repo`, making them harder to use directly
  in follow-up tool calls (`read_file` expects relative paths).
- Inconsistency: `list_files` returns bare names; `search_in_files` returns
  absolute paths.

---

## 6. `run_tests` passes pytest arguments through unvalidated

**Issue:** After the whitelist check on the first token (`pytest`, `python`,
`python3`) and the `-m pytest` check, all remaining arguments are forwarded
to pytest without inspection.

**Impact:**
- `--rootdir=<path>` could redirect pytest's root outside `target-repo`.
- `-p no:cacheprovider` alters test discovery.
- Pytest plugins loaded via `-p` could execute arbitrary code.
- `--co` (collect-only) changes stdout content without running tests.
- The test runner path itself (`pytest tests/specific_file.py`) is
  unvalidated — no check that paths stay within `target-repo`.

**Mitigation:** `execFile` with `shell:false` prevents shell injection. The
risk is limited to the pytest process itself, which runs inside `target-repo`.

---

## 7. Test output instability

**Issue:** pytest output format varies by:
- pytest version
- installed plugins (e.g., `pytest-cov`, `pytest-xdist`)
- whether output is a TTY (ANSI colour codes may appear)
- verbose flags
- presence of `conftest.py` hooks that alter stdout
- timing information in output (e.g., `0.03s call`)

**Impact:** If evaluation compares raw stdout strings across runs or
environments, results may not match. Timing lines and ANSI codes make string
comparisons fragile.

---

## 8. `git diff` output is unstable across git versions

**Issue:** `git diff` output format includes:
- Index line SHA hashes (change with every commit).
- Hunk headers with surrounding context.
- Potentially CRLF/LF differences.
- Some git versions include `--stat`-like summaries with different formatting.

**Impact:** Exact string comparison of diffs across environments is unreliable.
Evaluations that match on diff content must handle this variability.

---

## 9. `apply_patch` temp-file name collision

**Issue:** Temp file name is `mcp_patch_${Date.now()}.patch`. Two concurrent
`apply_patch` calls within the same millisecond will attempt to write the same
file path, with the second write overwriting the first, and both `git apply`
invocations reading the same (second) patch content.

**Impact:** Rare in practice given typical request latency, but possible under
parallel load. Results in silent incorrect patch application without error.

---

## 10. Logging is synchronous and blocks the event loop

**Issue:** `writeLog()` calls `fs.appendFileSync()` — a synchronous operation
that blocks the Node.js event loop until the write completes.

**Impact:**
- Under load, log writes add measurable latency to every tool call.
- `ensureLogDir()` calls `fs.mkdirSync()` on every single write, not just on
  startup. This is an extra syscall per log entry.

---

## 11. `bytesReturned` in logs does not match wire bytes

**Issue:** `bytesReturned` is the `.length` of the JSON-stringified result
string inside the tool. In `index.ts`, the result is re-serialised with
`JSON.stringify(result, null, 2)` (pretty-printed). The logged size will be
smaller than the actual bytes sent on the wire.

**Impact:** Log-based size analysis will undercount actual message size.

---

## 12. `read_file` reads binary files as UTF-8

**Issue:** `fs.readFileSync(resolved, "utf8")` will throw (or return corrupted
content with replacement characters) on binary files.

**Impact:** Binary files (`.pyc`, images, compiled artifacts) cannot be read.
The error propagates as a tool error rather than a graceful "binary file"
message. `search_in_files` handles this more gracefully (inner try/catch
skips the file silently).

---

## 13. No patch size cap in `apply_patch`

**Issue:** The `patch` string passed to `apply_patch` has no size limit. An
arbitrarily large patch is written to disk and fed to `git apply`.

**Impact:**
- Very large patches could fill the temp directory or the target-repo working
  tree.
- `git apply` time is unbounded by data size; only by the 10-second timeout on
  the `git` subprocess, which may not be sufficient for very large patches.

---

## 14. No staged changes in `git_diff`

**Issue:** `git diff` (no flags) shows only unstaged working-tree changes.
Staged changes (`git add`-ed changes in the index) are invisible.

**Impact:** After `apply_patch` runs `git apply` (which modifies the working
tree but does not stage), `git diff` will show the patch. However, if an agent
uses `git add` via a test fixture or pytest plugin, those changes disappear
from `git_diff` output unexpectedly.

---

## 15. No concurrency control on `apply_patch` + `git_diff`

**Issue:** Multiple concurrent `apply_patch` or `git_diff` calls execute
independently. There is no locking around git operations.

**Impact:** Interleaved `apply_patch` and `git diff` calls may produce
inconsistent results — e.g., `git diff` may read a partial state while a patch
is being applied.

---

## 16. `getTargetRepo()` re-evaluates `process.env.TARGET_REPO` on every call

**Issue:** `getTargetRepo()` reads `process.env` on every tool invocation.

**Impact:** If `TARGET_REPO` is modified at runtime (e.g., by a test harness
that mutates `process.env`), the sandbox root can silently shift mid-session.
This is unlikely in production but is a hidden state risk in test environments.
