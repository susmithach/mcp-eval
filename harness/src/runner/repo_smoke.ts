import { applyTask, resetRepo } from "./repo.js";

await resetRepo();
await applyTask("task_01_token_expiry_bypass");
console.log("applied");

await resetRepo();
console.log("reset");
