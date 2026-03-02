import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

// ---------------------------------------------------------------------------
// Result types (mirror server-mcp response shapes)
// ---------------------------------------------------------------------------

export interface ListFilesResult {
  files: string[];
  directories: string[];
}

export interface ReadFileResult {
  content: string;
  size: number;
}

export interface SearchMatch {
  file: string;
  line: number;
  content: string;
}

export interface SearchInFilesResult {
  matches: SearchMatch[];
}

export interface RunTestsResult {
  exit_code: number;
  stdout: string;
  stderr: string;
  passed: boolean;
}

export interface GitDiffResult {
  diff: string;
}

export interface ApplyPatchResult {
  applied: boolean;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

export class McpHarnessClient {
  private client: Client;
  private transport: StdioClientTransport;
  private toolCallCount = 0;

  constructor() {
    this.transport = new StdioClientTransport({
      command: "node",
      args: ["../server-mcp/build/index.js"],
    });
    this.client = new Client({ name: "harness", version: "0.1.0" });
  }

  async connect(): Promise<void> {
    await this.client.connect(this.transport);
  }

  async close(): Promise<void> {
    await this.client.close();
  }

  async listTools(): Promise<string[]> {
    this.toolCallCount++;
    const result = await this.client.listTools();
    return result.tools.map((t) => t.name).sort();
  }

  private async callTool<T>(
    name: string,
    args: Record<string, unknown>,
  ): Promise<T> {
    this.toolCallCount++;
    const raw = await this.client.callTool({ name, arguments: args });
    // The SDK return type carries a `[x: string]: unknown` index signature that
    // widens all property accesses to `unknown`, so we cast content explicitly.
    const content = raw.content as Array<{ type: string; text?: string }>;
    const first = content[0];
    if (!first || first.type !== "text" || first.text === undefined) {
      throw new Error(`Unexpected response from tool "${name}": no text content`);
    }
    return JSON.parse(first.text) as T;
  }

  async listFiles(directory: string): Promise<ListFilesResult> {
    return this.callTool<ListFilesResult>("list_files", { path: directory });
  }

  async readFile(path: string): Promise<ReadFileResult> {
    return this.callTool<ReadFileResult>("read_file", { path });
  }

  async searchInFiles(
    query: string,
    directory = ".",
  ): Promise<SearchInFilesResult> {
    return this.callTool<SearchInFilesResult>("search_in_files", {
      query,
      path: directory,
    });
  }

  async runTests(): Promise<RunTestsResult> {
    const raw = await this.callTool<{
      exit_code: number;
      stdout: string;
      stderr: string;
    }>("run_tests", { command: "python -m pytest" });
    return { ...raw, passed: raw.exit_code === 0 };
  }

  async gitDiff(): Promise<GitDiffResult> {
    return this.callTool<GitDiffResult>("git_diff", {});
  }

  async applyPatch(patchText: string): Promise<ApplyPatchResult> {
    return this.callTool<ApplyPatchResult>("apply_patch", { patch: patchText });
  }

  getToolCallCount(): number {
    return this.toolCallCount;
  }
}
