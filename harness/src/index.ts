import { runTask } from "./runner/run_task.js";

const result = await runTask({
  task_id: "task_01",
  task_patch_file: "task_01_token_expiry_bypass",
  strategy_name: "dummy",
  run_id: "run_1",
});

console.log(JSON.stringify(result, null, 2));
