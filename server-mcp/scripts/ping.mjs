import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const transport = new StdioClientTransport({
  command: "node",
  args: ["build/index.js"], // if your entry is build/index.js
  stderr: "inherit", // so you can see server stderr
});

const client = new Client(
  { name: "ping-client", version: "0.0.1" },
  { capabilities: {} },
);

await client.connect(transport);

const tools = await client.listTools();
console.log("CONNECTED. Tools:");
for (const t of tools.tools ?? []) console.log("-", t.name);

await client.close();
process.exit(0);
