/**
 * Deterministic MCP smoke test client.
 *
 * Spawns the server, connects via StdioClientTransport, calls every tool once
 * with safe/read-only inputs, prints a structured JSON report, and exits.
 *
 * Exit code: 0 = all MCP calls returned responses, 1 = any call threw.
 *
 * Run (from server-mcp/):
 *   npx tsc -p tsconfig.scripts.json && node build/scripts/smoke_client.js
 */

"use strict";

import * as path from "node:path";
import * as url from "node:url";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ToolResult {
  tool: string;
  input: Record<string, unknown>;
  ok: boolean;
  output?: unknown;
  error?: string;
}

interface SmokeReport {
  server: string;
  tools_registered: number;
  registered_names: string[];
  results: ToolResult[];
  summary: { passed: number; failed: number };
}

// Local alias for the text-content shape returned by callTool.
interface TextContentItem {
  type: "text";
  text: string;
}

// ---------------------------------------------------------------------------
// Tool cases — safe, deterministic, read-only inputs
// ---------------------------------------------------------------------------

interface ToolCase {
  tool: string;
  input: Record<string, unknown>;
}

const TOOL_CASES: readonly ToolCase[] = [
  {
    tool: "list_files",
    input: { path: "." },
  },
  {
    tool: "read_file",
    input: { path: "README.md" },
  },
  {
    tool: "search_in_files",
    input: { query: "pyservicelab", path: ".", limit: 5 },
  },
  {
    // pytest --collect-only discovers tests without executing them.
    // runProcess always resolves, so the MCP call succeeds even if pytest is
    // unavailable (the tool returns exit_code:1 in that case).
    tool: "run_tests",
    input: { command: "pytest --collect-only -q" },
  },
  {
    // Intentionally non-applicable patch: git apply will reject it, returning
    // { applied: false, error: "..." }. No files are modified. The MCP call
    // itself still succeeds (no exception thrown by the server).
    tool: "apply_patch",
    input: {
      patch:
        "--- a/SMOKE_TEST_PROBE\n" +
        "+++ b/SMOKE_TEST_PROBE\n" +
        "@@ -1 +1 @@\n" +
        "-PROBE\n" +
        "+PROBE\n",
    },
  },
  {
    // No required inputs.
    tool: "git_diff",
    input: {},
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Parse the first text-content item from a callTool response. */
function extractOutput(
  content: unknown[]
): unknown {
  if (content.length === 0) return null;
  const first = content[0];
  if (
    first !== null &&
    typeof first === "object" &&
    "type" in first &&
    (first as TextContentItem).type === "text" &&
    "text" in first
  ) {
    const text = (first as TextContentItem).text;
    try {
      return JSON.parse(text) as unknown;
    } catch {
      return text;
    }
  }
  return first;
}

function emit(report: SmokeReport): void {
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  // Resolve build/index.js from the compiled script location.
  // Compiled layout: server-mcp/build/scripts/smoke_client.js
  //                  server-mcp/build/index.js
  const __filename = url.fileURLToPath(import.meta.url);
  const serverRoot = path.resolve(path.dirname(__filename), "..", "..");
  const serverEntry = path.join(serverRoot, "build", "index.js");

  const transport = new StdioClientTransport({
    command: "node",
    args: [serverEntry],
    // Pipe server stderr so it doesn't pollute the structured JSON output.
    stderr: "pipe",
  });

  const client = new Client(
    { name: "smoke-client", version: "1.0.0" },
    { capabilities: {} }
  );

  let connected = false;

  try {
    // connect() performs the MCP initialize / initialized handshake,
    // confirming server readiness before we proceed.
    await client.connect(transport);
    connected = true;

    // 1. Verify tool registration.
    const { tools } = await client.listTools();
    const registeredNames = tools.map((t) => t.name);

    // 2. Call each tool once.
    const results: ToolResult[] = [];

    for (const tc of TOOL_CASES) {
      let result: ToolResult;
      try {
        const response = await client.callTool({
          name: tc.tool,
          arguments: tc.input,
        });
        const output = extractOutput(
          Array.isArray(response.content) ? (response.content as unknown[]) : []
        );
        result = { tool: tc.tool, input: tc.input, ok: true, output };
      } catch (err: unknown) {
        result = {
          tool: tc.tool,
          input: tc.input,
          ok: false,
          error: err instanceof Error ? err.message : String(err),
        };
      }
      results.push(result);
    }

    const passed = results.filter((r) => r.ok).length;
    const failed = results.filter((r) => !r.ok).length;

    const report: SmokeReport = {
      server: "server-mcp@1.0.0",
      tools_registered: tools.length,
      registered_names: registeredNames,
      results,
      summary: { passed, failed },
    };

    emit(report);
    process.exitCode = failed > 0 ? 1 : 0;
  } catch (err: unknown) {
    const report: SmokeReport = {
      server: "server-mcp@1.0.0",
      tools_registered: 0,
      registered_names: [],
      results: [],
      summary: { passed: 0, failed: TOOL_CASES.length },
    };
    process.stderr.write(
      `Fatal: ${err instanceof Error ? err.message : String(err)}\n`
    );
    emit(report);
    process.exitCode = 1;
  } finally {
    // Ensure the server process is always killed, even on error.
    if (connected) {
      await client.close();
    } else {
      // Transport not yet handed to client — close it directly.
      await transport.close();
    }
  }
}

main().catch((err: unknown) => {
  process.stderr.write(
    `Uncaught: ${err instanceof Error ? err.message : String(err)}\n`
  );
  process.exit(1);
});
