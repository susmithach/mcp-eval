import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

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

  getToolCallCount(): number {
    return this.toolCallCount;
  }
}
