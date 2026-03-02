import { McpStrategy } from "./strategies/mcp.js";
import { PromptOnlyStrategy } from "./strategies/prompt_only.js";
import type { Strategy } from "./strategies/strategy.js";
import { runTask } from "./runner/run_task.js";

function strategyFromArgs(): { name: string; instance: Strategy } {
  const arg = process.argv.find((a) => a.startsWith("--strategy="));
  const name = arg ? arg.split("=")[1] : "mcp";
  switch (name) {
    case "mcp":
      return { name, instance: new McpStrategy() };
    case "prompt":
      return { name, instance: new PromptOnlyStrategy() };
    default:
      console.error(`Unknown strategy "${name}". Use --strategy=mcp|prompt`);
      process.exit(1);
  }
}

const { name: strategyName, instance: strategy } = strategyFromArgs();

const result = await runTask({
  task_id: "task_01",
  task_patch_file: "task_01_token_expiry_bypass",
  strategy_name: strategyName,
  run_id: "run_1",
  strategy,
});

console.log(JSON.stringify(result, null, 2));
