/**
 * Integration tests for the PyServiceLab MCP server.
 *
 * A real server process is spawned for each describe suite via
 * StdioClientTransport with TARGET_REPO pointing at a temporary fixture
 * directory.  No mocking — every assertion exercises the full stack.
 *
 * Run from server-mcp/:
 *   node --test build/test/integration.test.js
 */

import { after, before, describe, test } from "node:test";
import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import * as url from "node:url";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { ErrorCode, McpError } from "@modelcontextprotocol/sdk/types.js";

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const __filename = url.fileURLToPath(import.meta.url);
// Compiled layout:  build/test/integration.test.js
//                   build/index.js
const SERVER_ENTRY = path.resolve(path.dirname(__filename), "..", "index.js");

// MAX_FILE_SIZE mirrors src/utils/file_utils.ts
const MAX_FILE_SIZE = 200 * 1024; // 200 KB

// ---------------------------------------------------------------------------
// Fixture helpers
// ---------------------------------------------------------------------------

/**
 * Creates a minimal fixture repository.
 * Files are written in *reverse* alphabetical order on purpose, so that any
 * missing sort() in the tool implementation is caught immediately.
 */
function createFixtureRepo(): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "mcp-intg-"));

  // Root-level text files — created intentionally out of alphabetical order.
  fs.writeFileSync(
    path.join(root, "gamma.txt"),
    "line one\npyservicelab gamma\nline three\n",
  );
  fs.writeFileSync(path.join(root, "beta.txt"), "line one\npyservicelab beta\n");
  fs.writeFileSync(path.join(root, "alpha.txt"), "pyservicelab alpha\nline two\n");

  // Subdirectory (also created after the files to stress directory ordering).
  const subdir = path.join(root, "subdir");
  fs.mkdirSync(subdir);
  fs.writeFileSync(path.join(subdir, "delta.txt"), "pyservicelab delta\n");

  // Oversized file: MAX_FILE_SIZE + 1 400 bytes — must be rejected by read_file.
  fs.writeFileSync(
    path.join(root, "bigfile.bin"),
    Buffer.alloc(MAX_FILE_SIZE + 1_400, 0x41), // 'A' × (200 KB + 1 400)
  );

  return root;
}

// ---------------------------------------------------------------------------
// Client factory
// ---------------------------------------------------------------------------

async function spawnClient(fixtureRepo: string): Promise<Client> {
  // Build an environment that inherits the current process env (so node is on
  // PATH) and overrides TARGET_REPO so the server uses our fixture directory.
  const env: Record<string, string> = {};
  for (const [k, v] of Object.entries(process.env)) {
    if (v !== undefined) env[k] = v;
  }
  env["TARGET_REPO"] = fixtureRepo;

  const transport = new StdioClientTransport({
    command: "node",
    args: [SERVER_ENTRY],
    env,
    stderr: "pipe",
  });

  const client = new Client(
    { name: "integration-test-client", version: "1.0.0" },
    { capabilities: {} },
  );
  await client.connect(transport);
  return client;
}

// ---------------------------------------------------------------------------
// Tool call helper — parses the first text-content item back to a value.
// ---------------------------------------------------------------------------

interface TextContentItem {
  type: "text";
  text: string;
}

async function callTool(
  client: Client,
  name: string,
  args: Record<string, unknown>,
): Promise<unknown> {
  const response = await client.callTool({ name, arguments: args });
  const items = response.content as unknown[];
  if (items.length === 0) throw new Error(`Empty content from tool "${name}"`);
  const first = items[0];
  if (
    typeof first === "object" &&
    first !== null &&
    "type" in first &&
    (first as TextContentItem).type === "text"
  ) {
    return JSON.parse((first as TextContentItem).text) as unknown;
  }
  throw new Error(`Unexpected content shape from tool "${name}"`);
}

// ---------------------------------------------------------------------------
// Assertion helper for MCP errors
// ---------------------------------------------------------------------------

function assertMcpError(err: unknown, code: ErrorCode, pattern?: RegExp): void {
  assert.ok(
    err instanceof McpError,
    `expected McpError, got ${err instanceof Error ? err.constructor.name : typeof err}: ${String(err)}`,
  );
  assert.equal(err.code, code, `expected error code ${code}, got ${err.code}`);
  if (pattern !== undefined) {
    assert.match(
      err.message,
      pattern,
      `error message "${err.message}" did not match ${String(pattern)}`,
    );
  }
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

describe("MCP server integration", () => {
  let client: Client;
  let fixtureRepo: string;

  before(async () => {
    fixtureRepo = createFixtureRepo();
    client = await spawnClient(fixtureRepo);
  });

  after(async () => {
    await client.close();
    fs.rmSync(fixtureRepo, { recursive: true, force: true });
  });

  // ── list_files: ordering ──────────────────────────────────────────────────

  test("list_files returns files in strict alphabetical order", async () => {
    const result = (await callTool(client, "list_files", { path: "." })) as {
      files: string[];
      directories: string[];
    };

    // Both arrays must equal their own sorted copies.
    const sortedFiles = [...result.files].sort((a, b) => a.localeCompare(b));
    assert.deepEqual(
      result.files,
      sortedFiles,
      "files array is not alphabetically sorted",
    );

    const sortedDirs = [...result.directories].sort((a, b) =>
      a.localeCompare(b),
    );
    assert.deepEqual(
      result.directories,
      sortedDirs,
      "directories array is not alphabetically sorted",
    );

    // Fixture members must all be present.
    assert.ok(result.files.includes("alpha.txt"));
    assert.ok(result.files.includes("beta.txt"));
    assert.ok(result.files.includes("gamma.txt"));
    assert.ok(result.files.includes("bigfile.bin"));
    assert.ok(result.directories.includes("subdir"));
  });

  test("list_files ordering is identical across repeated calls", async () => {
    const r1 = await callTool(client, "list_files", { path: "." });
    const r2 = await callTool(client, "list_files", { path: "." });
    assert.deepEqual(r1, r2, "list_files produced different results on second call");
  });

  test("list_files subdirectory is also alphabetically sorted", async () => {
    // Subdir contains only delta.txt — create a second file to have a
    // two-element array to sort-check.
    const subdir = path.join(fixtureRepo, "subdir");
    fs.writeFileSync(path.join(subdir, "aardvark.txt"), "first\n");

    const result = (await callTool(client, "list_files", {
      path: "subdir",
    })) as { files: string[]; directories: string[] };

    const sorted = [...result.files].sort((a, b) => a.localeCompare(b));
    assert.deepEqual(result.files, sorted);
    assert.ok(result.files.includes("aardvark.txt"));
    assert.ok(result.files.includes("delta.txt"));
    // aardvark must come before delta alphabetically.
    assert.ok(
      result.files.indexOf("aardvark.txt") < result.files.indexOf("delta.txt"),
    );

    fs.rmSync(path.join(subdir, "aardvark.txt"));
  });

  // ── search_in_files: ordering ─────────────────────────────────────────────

  test("search_in_files ordering is identical across repeated calls", async () => {
    const args = { query: "pyservicelab", path: ".", limit: 20 } as const;
    const r1 = (await callTool(client, "search_in_files", args)) as {
      matches: unknown[];
    };
    const r2 = (await callTool(client, "search_in_files", args)) as {
      matches: unknown[];
    };
    assert.ok(r1.matches.length > 0, "expected at least one search match");
    assert.deepEqual(
      r1,
      r2,
      "search_in_files produced different order on second call",
    );
  });

  test("search_in_files limit is strictly enforced", async () => {
    const result = (await callTool(client, "search_in_files", {
      query: "pyservicelab",
      path: ".",
      limit: 2,
    })) as { matches: unknown[] };

    assert.ok(
      result.matches.length <= 2,
      `limit=2 violated: got ${result.matches.length} matches`,
    );
  });

  test("search_in_files returns expected number of fixture matches", async () => {
    // Fixture has exactly 4 lines containing "pyservicelab":
    //   alpha.txt:1, beta.txt:2, gamma.txt:2, subdir/delta.txt:1
    const result = (await callTool(client, "search_in_files", {
      query: "pyservicelab",
      path: ".",
      limit: 100,
    })) as { matches: { file: string; line: number; content: string }[] };

    assert.equal(
      result.matches.length,
      4,
      `expected 4 fixture matches, got ${result.matches.length}`,
    );
  });

  // ── path traversal rejection ──────────────────────────────────────────────

  test("list_files rejects path traversal", async () => {
    await assert.rejects(
      async () => {
        await client.callTool({ name: "list_files", arguments: { path: "../" } });
      },
      (err: unknown) => {
        assertMcpError(err, ErrorCode.InternalError, /traversal|escape|sandbox/i);
        return true;
      },
    );
  });

  test("read_file rejects path traversal", async () => {
    await assert.rejects(
      async () => {
        await client.callTool({
          name: "read_file",
          arguments: { path: "../../etc/passwd" },
        });
      },
      (err: unknown) => {
        assertMcpError(err, ErrorCode.InternalError, /traversal|escape|sandbox/i);
        return true;
      },
    );
  });

  test("search_in_files rejects path traversal", async () => {
    await assert.rejects(
      async () => {
        await client.callTool({
          name: "search_in_files",
          arguments: { query: "x", path: "../" },
        });
      },
      (err: unknown) => {
        assertMcpError(err, ErrorCode.InternalError, /traversal|escape|sandbox/i);
        return true;
      },
    );
  });

  // ── file size limit ───────────────────────────────────────────────────────

  test(`read_file rejects files larger than ${MAX_FILE_SIZE} bytes`, async () => {
    await assert.rejects(
      async () => {
        await client.callTool({
          name: "read_file",
          arguments: { path: "bigfile.bin" },
        });
      },
      (err: unknown) => {
        assertMcpError(err, ErrorCode.InternalError, /too large|limit|size/i);
        return true;
      },
    );
  });

  // ── run_tests command validation ──────────────────────────────────────────

  test("run_tests rejects an arbitrary shell command", async () => {
    await assert.rejects(
      async () => {
        await client.callTool({
          name: "run_tests",
          arguments: { command: "ls -la" },
        });
      },
      (err: unknown) => {
        // parseCommand throws Error("Command not allowed: ...") →
        // server wraps as McpError(InternalError, ...)
        assertMcpError(err, ErrorCode.InternalError, /not allowed/i);
        return true;
      },
    );
  });

  test("run_tests rejects python without -m pytest suffix", async () => {
    await assert.rejects(
      async () => {
        await client.callTool({
          name: "run_tests",
          arguments: { command: "python -c 'import os; print(os.getcwd())'" },
        });
      },
      (err: unknown) => {
        assertMcpError(err, ErrorCode.InternalError, /python -m pytest|allowed/i);
        return true;
      },
    );
  });

  test("run_tests rejects commands using cat", async () => {
    await assert.rejects(
      async () => {
        await client.callTool({
          name: "run_tests",
          arguments: { command: "cat /etc/passwd" },
        });
      },
      (err: unknown) => {
        assertMcpError(err, ErrorCode.InternalError, /not allowed/i);
        return true;
      },
    );
  });

  test("run_tests rejects shell injection attempts", async () => {
    await assert.rejects(
      async () => {
        await client.callTool({
          name: "run_tests",
          arguments: { command: "pytest; rm -rf /" },
        });
      },
      (err: unknown) => {
        // "pytest;" is parsed as cmd="pytest;" which is not in ALLOWED_BASES.
        assertMcpError(err, ErrorCode.InternalError);
        return true;
      },
    );
  });
});
