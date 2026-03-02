import { McpHarnessClient } from "./client.js";

const client = new McpHarnessClient();
await client.connect();
const tools = await client.listTools();
for (const name of tools) {
  console.log(name);
}
await client.close();
