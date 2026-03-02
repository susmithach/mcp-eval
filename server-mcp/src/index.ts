import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from "@modelcontextprotocol/sdk/types.js";
import { ZodError } from "zod";

import { applyPatch } from "./tools/apply_patch.js";
import { gitDiff } from "./tools/git_diff.js";
import { listFiles } from "./tools/list_files.js";
import { readFile } from "./tools/read_file.js";
import { runTests } from "./tools/run_tests.js";
import { searchInFiles } from "./tools/search_in_files.js";

// ---------------------------------------------------------------------------
// Server instance
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "server-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } },
);

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "list_files",
      description:
        "List files and directories at the given path inside the target repository.",
      inputSchema: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description:
              'Relative path inside the target repository (e.g. "." or "src/").',
          },
        },
        required: ["path"],
        additionalProperties: false,
      },
    },
    {
      name: "read_file",
      description:
        "Read the content of a file inside the target repository (max 200 KB).",
      inputSchema: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description:
              "Relative path to the file inside the target repository.",
          },
        },
        required: ["path"],
        additionalProperties: false,
      },
    },
    {
      name: "search_in_files",
      description:
        "Search for a text query across all files under the given path.",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: "Text to search for." },
          path: {
            type: "string",
            description: "Root path to search under (relative to target-repo).",
          },
          limit: {
            type: "number",
            description:
              "Maximum number of matches to return (1–500, default 50).",
          },
        },
        required: ["query", "path"],
        additionalProperties: false,
      },
    },
    {
      name: "run_tests",
      description:
        "Run pytest inside the target repository. Only pytest / python -m pytest commands are allowed.",
      inputSchema: {
        type: "object",
        properties: {
          command: {
            type: "string",
            description:
              'Test command to run, e.g. "pytest" or "python -m pytest tests/".',
          },
        },
        required: ["command"],
        additionalProperties: false,
      },
    },
    {
      name: "apply_patch",
      description:
        "Apply a unified diff patch to the target repository using git apply.",
      inputSchema: {
        type: "object",
        properties: {
          patch: {
            type: "string",
            description: "Unified diff patch content.",
          },
        },
        required: ["patch"],
        additionalProperties: false,
      },
    },
    {
      name: "git_diff",
      description:
        "Return the current git diff (unstaged changes) of the target repository.",
      inputSchema: {
        type: "object",
        properties: {},
        additionalProperties: false,
      },
    },
  ],
}));

// ---------------------------------------------------------------------------
// Tool dispatch
// ---------------------------------------------------------------------------

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result: unknown;

    switch (name) {
      case "list_files":
        result = await listFiles(args);
        break;
      case "read_file":
        result = await readFile(args);
        break;
      case "search_in_files":
        result = await searchInFiles(args);
        break;
      case "run_tests":
        result = await runTests(args);
        break;
      case "apply_patch":
        result = await applyPatch(args);
        break;
      case "git_diff":
        result = await gitDiff(args);
        break;
      default:
        throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: "${name}"`);
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  } catch (err) {
    // Re-throw McpErrors as-is (they carry the correct error code)
    if (err instanceof McpError) throw err;

    // Zod validation errors → InvalidParams
    if (err instanceof ZodError) {
      throw new McpError(
        ErrorCode.InvalidParams,
        `Invalid arguments: ${err.errors.map((e) => `${e.path.join(".")}: ${e.message}`).join("; ")}`,
      );
    }

    // All other errors → InternalError (never crash the server)
    throw new McpError(
      ErrorCode.InternalError,
      err instanceof Error ? err.message : String(err),
    );
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // Do NOT write to stdout — it is used by the MCP protocol.
  // Use the log file (logs/mcp.log) for diagnostics.
}

main().catch((err) => {
  // Last-resort: write to stderr and exit
  process.stderr.write(
    `Fatal error: ${err instanceof Error ? err.message : String(err)}\n`,
  );
  process.exit(1);
});
