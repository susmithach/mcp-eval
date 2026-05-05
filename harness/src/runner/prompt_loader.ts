import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { TaskType } from "./result_schema.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
// dist/runner/ → ../../prompts/
const PROMPTS_DIR = resolve(__dirname, "../../prompts");

/**
 * Load and render a prompt template for the given task type.
 *
 * Reads `prompts/{task_type}.txt`, substitutes `{{task_id}}` with the
 * provided value, and returns the rendered string.
 *
 * @throws If the template file cannot be read.
 */
export async function loadPrompt(
  task_type: TaskType,
  task_id: string,
): Promise<string> {
  const file = resolve(PROMPTS_DIR, `${task_type}.txt`);
  const template = await readFile(file, "utf8");
  return template.replaceAll("{{task_id}}", task_id);
}
