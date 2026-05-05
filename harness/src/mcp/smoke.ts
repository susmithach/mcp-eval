import { McpHarnessClient } from "./client.js";

const client = new McpHarnessClient();
try {
  await client.connect();

  // Tool list
  const tools = await client.listTools();
  console.log("tools:", tools.join(", "));

  // listFiles
  const listing = await client.listFiles(".");
  const total = listing.files.length + listing.directories.length;
  console.log(`listFiles("."): ${total} entries`);

  // readFile — try README.md, fall back to pyproject.toml
  let snippet: string;
  try {
    const rf = await client.readFile("README.md");
    snippet = rf.content.slice(0, 80);
  } catch {
    const rf = await client.readFile("pyproject.toml");
    snippet = rf.content.slice(0, 80);
  }
  console.log(`readFile snippet: ${JSON.stringify(snippet)}`);

  // runTests
  const tests = await client.runTests();
  console.log(`runTests: passed=${tests.passed} exitCode=${tests.exit_code}`);

  // gitDiff
  const diff = await client.gitDiff();
  console.log(`gitDiff: ${diff.diff.length} chars`);

  console.log(`total tool calls: ${client.getToolCallCount()}`);
} finally {
  await client.close();
}
