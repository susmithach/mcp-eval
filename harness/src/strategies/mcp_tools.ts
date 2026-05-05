import type { McpHarnessClient } from "../mcp/client.js";
import type { LlmToolDefinition } from "../llm/types.js";
import type {
  ApplyPatchResult,
  GitDiffResult,
  ListFilesResult,
  ReadFileResult,
  RunTestsResult,
  SearchInFilesResult,
} from "../mcp/client.js";

export const MCP_TOOL_DEFINITIONS: LlmToolDefinition[] = [
  {
    name: "list_files",
    description:
      "List files and directories at the given path inside the target repository.",
    inputSchema: {
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
    inputSchema: {
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
    inputSchema: {
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
      "Run pytest and return exit_code, stdout, stderr, and passed (boolean). You may optionally provide a tests array of pytest node ids to run only the task's expected failing tests.",
    inputSchema: {
      type: "object" as const,
      properties: {
        tests: {
          type: "array",
          description: "Optional pytest node ids to run, such as tests/test_auth.py::TestTokens::test_decode_expired_token",
          items: {
            type: "string",
          },
        },
      },
    },
  },
  {
    name: "apply_patch",
    description:
      "Apply a unified diff patch to modify source files. Use standard unified diff format with repo-relative paths like a/pyservicelab/auth/tokens.py and b/pyservicelab/auth/tokens.py. Do not include a target-repo/ path prefix.",
    inputSchema: {
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
    inputSchema: {
      type: "object" as const,
      properties: {},
    },
  },
];

const TOOL_NAME_ALIASES: Record<string, string> = {
  file_read: "read_file",
  list_dir: "list_files",
  list_directory: "list_files",
  ls: "list_files",
  read: "read_file",
  run_pytest: "run_tests",
  search: "search_in_files",
  search_files: "search_in_files",
  show_diff: "git_diff",
  view_file: "read_file",
};

const READ_FILE_CHAR_LIMIT = 8_000;
const RUN_TESTS_CHAR_LIMIT = 6_000;
const GIT_DIFF_CHAR_LIMIT = 6_000;

function truncate(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  const head = text.slice(0, Math.floor(maxChars / 2));
  const tail = text.slice(-Math.floor(maxChars / 2));
  return `${head}\n... [truncated ${text.length - maxChars} chars] ...\n${tail}`;
}

function normalizeRawToolName(name: string): string {
  return name
    .trim()
    .replace(/<\|.*$/, "")
    .replace(/[ -]+/g, "_")
    .toLowerCase();
}

export function normalizeToolName(
  rawName: string,
  input: Record<string, unknown>,
): string | null {
  const normalized = normalizeRawToolName(rawName);

  if (MCP_TOOL_DEFINITIONS.some((tool) => tool.name === normalized)) {
    return normalized;
  }

  const alias = TOOL_NAME_ALIASES[normalized];
  if (alias) return alias;

  // Heuristics for weaker OpenAI-compatible models that emit generic file verbs.
  if (["open", "open_file", "show", "view"].includes(normalized)) {
    if (typeof input["path"] === "string") return "read_file";
    return null;
  }

  if (normalized === "grep" || normalized === "find_in_files") {
    return "search_in_files";
  }

  return null;
}

function formatListFilesResult(result: ListFilesResult): string {
  return JSON.stringify(result);
}

function formatReadFileResult(result: ReadFileResult): string {
  return JSON.stringify({
    content: truncate(result.content, READ_FILE_CHAR_LIMIT),
    size: result.size,
    truncated: result.content.length > READ_FILE_CHAR_LIMIT,
  });
}

function formatSearchResult(result: SearchInFilesResult): string {
  return JSON.stringify(result);
}

function formatRunTestsResult(result: RunTestsResult): string {
  return JSON.stringify({
    exit_code: result.exit_code,
    passed: result.passed,
    stdout: truncate(result.stdout, RUN_TESTS_CHAR_LIMIT),
    stderr: truncate(result.stderr, RUN_TESTS_CHAR_LIMIT),
    stdout_truncated: result.stdout.length > RUN_TESTS_CHAR_LIMIT,
    stderr_truncated: result.stderr.length > RUN_TESTS_CHAR_LIMIT,
  });
}

function formatApplyPatchResult(result: ApplyPatchResult): string {
  return JSON.stringify(result);
}

function formatGitDiffResult(result: GitDiffResult): string {
  return JSON.stringify({
    diff: truncate(result.diff, GIT_DIFF_CHAR_LIMIT),
    truncated: result.diff.length > GIT_DIFF_CHAR_LIMIT,
  });
}

function formatToolResult(name: string, result: unknown): string {
  switch (name) {
    case "list_files":
      return formatListFilesResult(result as ListFilesResult);
    case "read_file":
      return formatReadFileResult(result as ReadFileResult);
    case "search_in_files":
      return formatSearchResult(result as SearchInFilesResult);
    case "run_tests":
      return formatRunTestsResult(result as RunTestsResult);
    case "apply_patch":
      return formatApplyPatchResult(result as ApplyPatchResult);
    case "git_diff":
      return formatGitDiffResult(result as GitDiffResult);
    default:
      return JSON.stringify(result);
  }
}

export async function dispatchTool(
  client: McpHarnessClient,
  rawName: string,
  input: Record<string, unknown>,
): Promise<{ name: string | null; content: string; patchApplied?: boolean }> {
  const name = normalizeToolName(rawName, input);
  if (!name) {
    return {
      name: null,
      content: JSON.stringify({
        error: `Unknown tool: "${rawName}". Use one of: ${MCP_TOOL_DEFINITIONS.map((tool) => tool.name).join(", ")}`,
      }),
      patchApplied: undefined,
    };
  }

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
        result = await client.runTests(
          Array.isArray(input["tests"])
            ? (input["tests"] as string[])
            : undefined,
        );
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
    return {
      name,
      content: formatToolResult(name, result),
      patchApplied:
        name === "apply_patch"
          ? (result as ApplyPatchResult).applied
          : undefined,
    };
  } catch (err) {
    return {
      name,
      content: JSON.stringify({
        error: err instanceof Error ? err.message : String(err),
      }),
      patchApplied: undefined,
    };
  }
}
