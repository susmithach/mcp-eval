import type { Tool, ToolResultBlockParam } from "@anthropic-ai/sdk/resources/messages.js";
import type { McpHarnessClient } from "../mcp/client.js";

// ---------------------------------------------------------------------------
// Tool definitions — mirrors the MCP server's input schemas
// ---------------------------------------------------------------------------

export const MCP_TOOL_DEFINITIONS: Tool[] = [
  {
    name: "list_files",
    description:
      "List files and directories at the given path inside the target repository.",
    input_schema: {
      type: "object" as const,
      properties: {
        path: {
          type: "string",
          description: "Relative path inside the repository (e.g. '.' or 'pyservicelab/')",
        },
      },
      required: ["path"],
    },
  },
  {
    name: "read_file",
    description: "Read the full contents of a file inside the target repository.",
    input_schema: {
      type: "object" as const,
      properties: {
        path: {
          type: "string",
          description: "Relative path to the file",
        },
      },
      required: ["path"],
    },
  },
  {
    name: "search_in_files",
    description:
      "Search for a string pattern across files in the target repository. Results are sorted alphabetically.",
    input_schema: {
      type: "object" as const,
      properties: {
        query: {
          type: "string",
          description: "String to search for",
        },
        path: {
          type: "string",
          description: "Directory to restrict the search to (default '.')",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "run_tests",
    description:
      "Run the full pytest suite and return exit_code, stdout, stderr, and passed (boolean).",
    input_schema: {
      type: "object" as const,
      properties: {},
    },
  },
  {
    name: "apply_patch",
    description:
      "Apply a unified diff patch to modify source files. The patch must be in standard unified diff format.",
    input_schema: {
      type: "object" as const,
      properties: {
        patch: {
          type: "string",
          description: "Unified diff patch content",
        },
      },
      required: ["patch"],
    },
  },
  {
    name: "git_diff",
    description: "Return the current git diff of all changes made so far.",
    input_schema: {
      type: "object" as const,
      properties: {},
    },
  },
];

// ---------------------------------------------------------------------------
// Tool dispatcher — translates Claude tool_use blocks to MCP client calls
// ---------------------------------------------------------------------------

export async function dispatchTool(
  client: McpHarnessClient,
  name: string,
  input: Record<string, unknown>,
): Promise<ToolResultBlockParam> {
  let content: string;
  try {
    let result: unknown;
    switch (name) {
      case "list_files":
        result = await client.listFiles(input["path"] as string);
        break;
      case "read_file":
        result = await client.readFile(input["path"] as string);
        break;
      case "search_in_files":
        result = await client.searchInFiles(
          input["query"] as string,
          input["path"] as string | undefined,
        );
        break;
      case "run_tests":
        result = await client.runTests();
        break;
      case "apply_patch":
        result = await client.applyPatch(input["patch"] as string);
        break;
      case "git_diff":
        result = await client.gitDiff();
        break;
      default:
        throw new Error(`Unknown tool: "${name}"`);
    }
    content = JSON.stringify(result);
  } catch (err) {
    content = JSON.stringify({ error: err instanceof Error ? err.message : String(err) });
  }

  return { type: "tool_result", tool_use_id: "", content };
}
