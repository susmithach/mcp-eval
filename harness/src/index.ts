import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { loadProjectEnv } from "./env.js";
import { McpStrategy } from "./strategies/mcp.js";
import { PromptOnlyStrategy } from "./strategies/prompt_only.js";
import type { Strategy } from "./strategies/strategy.js";
import { runTask } from "./runner/run_task.js";
import { summarise, saveSummary } from "./runner/aggregator.js";
import type { ResultSchema, TaskType } from "./runner/result_schema.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
// dist/ → ../results = harness/results
const RESULTS_DIR = resolve(__dirname, "../results");

loadProjectEnv();

// ---------------------------------------------------------------------------
// Task registry
// ---------------------------------------------------------------------------

interface TaskConfig {
  task_id: string;
  task_patch_file: string;
  task_type: TaskType;
  expected_failing_tests: string[];
}

const TASKS: TaskConfig[] = [
  {
    task_id: "task_01",
    task_patch_file: "task_01_token_expiry_bypass",
    task_type: "bug_fix",
    expected_failing_tests: ["tests/test_auth.py::TestTokens::test_decode_expired_token"],
  },
  {
    task_id: "task_02",
    task_patch_file: "task_02_project_tags_inverted",
    task_type: "bug_fix",
    expected_failing_tests: [
      "tests/test_projects.py::TestProjectTags::test_create_with_tags",
      "tests/test_projects.py::TestProjectTags::test_update_tags",
    ],
  },
  {
    task_id: "task_03",
    task_patch_file: "task_03_empty_name_accepted",
    task_type: "bug_fix",
    expected_failing_tests: [
      "tests/test_projects.py::TestCreateProject::test_create_empty_name_raises",
      "tests/test_tasks.py::TestCreateTask::test_create_empty_title_raises",
    ],
  },
  {
    task_id: "task_04",
    task_patch_file: "task_04_audit_count_broken",
    task_type: "bug_fix",
    expected_failing_tests: ["tests/test_audit.py::TestAuditService::test_count_total"],
  },
  {
    task_id: "task_05",
    task_patch_file: "task_05_email_exists_always_false",
    task_type: "bug_fix",
    expected_failing_tests: [
      "tests/test_users.py::TestCreateUser::test_create_duplicate_email_raises",
      "tests/test_auth.py::TestRegister::test_register_duplicate_email_raises",
    ],
  },
  {
    task_id: "task_06",
    task_patch_file: "task_06_user_search_stubbed",
    task_type: "feature",
    expected_failing_tests: [
      "tests/test_users.py::TestSearchUsers::test_search_by_username_substring",
      "tests/test_users.py::TestSearchUsers::test_search_by_email_substring",
      "tests/test_users.py::TestSearchUsers::test_search_returns_multiple_matches",
      "tests/test_users.py::TestSearchUsers::test_search_case_insensitive",
    ],
  },
  {
    task_id: "task_07",
    task_patch_file: "task_07_audit_purge_stubbed",
    task_type: "feature",
    expected_failing_tests: [
      "tests/test_audit.py::TestAuditServicePurge::test_purge_old_entries_deletes_stale",
    ],
  },
  {
    task_id: "task_08",
    task_patch_file: "task_08_test_role_assertion_wrong",
    task_type: "test_fix",
    expected_failing_tests: [
      "tests/test_users.py::TestCreateUser::test_create_default_role_is_member",
    ],
  },
  {
    task_id: "task_09",
    task_patch_file: "task_09_test_count_wrong",
    task_type: "test_fix",
    expected_failing_tests: ["tests/test_users.py::TestListUsers::test_list_returns_all"],
  },
];

// ---------------------------------------------------------------------------
// CLI arg parsers
// ---------------------------------------------------------------------------

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

function taskFromArgs(): TaskConfig {
  const arg = process.argv.find((a) => a.startsWith("--task="));
  const task_id = arg ? arg.split("=")[1] : "task_01";
  const config = TASKS.find((t) => t.task_id === task_id);
  if (!config) {
    const available = TASKS.map((t) => t.task_id).join(", ");
    console.error(`Unknown task "${task_id}". Available: ${available}`);
    process.exit(1);
  }
  return config;
}

function runsFromArgs(): number {
  const arg = process.argv.find((a) => a.startsWith("--runs="));
  if (!arg) return 3;
  const n = parseInt(arg.split("=")[1], 10);
  if (isNaN(n) || n < 1) {
    console.error(`Invalid --runs value. Must be a positive integer.`);
    process.exit(1);
  }
  return n;
}

// ---------------------------------------------------------------------------
// Summary table printer
// ---------------------------------------------------------------------------

function printSummaryTable(
  results: ResultSchema[],
  taskId: string,
  strategyName: string,
): void {
  const successes = results.filter((r) => r.success).length;
  const rate = ((successes / results.length) * 100).toFixed(0);
  const avgMs = Math.round(
    results.reduce((s, r) => s + r.runtime_ms, 0) / results.length,
  );
  const avgIter = (
    results.reduce((s, r) => s + r.iterations, 0) / results.length
  ).toFixed(1);

  console.log("\n┌─────────────────────────────────────────────┐");
  console.log(`│  Task:     ${taskId.padEnd(33)}│`);
  console.log(`│  Strategy: ${strategyName.padEnd(33)}│`);
  console.log(`│  Runs:     ${String(results.length).padEnd(33)}│`);
  console.log("├─────────────────────────────────────────────┤");
  console.log(`│  Success rate:   ${`${successes}/${results.length} (${rate}%)`.padEnd(27)}│`);
  console.log(`│  Avg runtime:    ${`${avgMs} ms`.padEnd(27)}│`);
  console.log(`│  Avg iterations: ${avgIter.padEnd(27)}│`);
  console.log("└─────────────────────────────────────────────┘\n");
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const { name: strategyName, instance: strategy } = strategyFromArgs();
const taskConfig = taskFromArgs();
const totalRuns = runsFromArgs();

console.log(
  `Running ${taskConfig.task_id} (${taskConfig.task_type}) ` +
  `with strategy=${strategyName}, runs=${totalRuns}\n`,
);

const allResults: ResultSchema[] = [];

for (let i = 1; i <= totalRuns; i++) {
  const run_id = `run_${i}`;
  console.log(`[${i}/${totalRuns}] ${run_id}...`);

  const result = await runTask({
    task_id: taskConfig.task_id,
    task_patch_file: taskConfig.task_patch_file,
    task_type: taskConfig.task_type,
    expected_failing_tests: taskConfig.expected_failing_tests,
    strategy_name: strategyName,
    run_id,
    strategy,
  });

  allResults.push(result);
  const status = result.success ? "✓ passed" : "✗ failed";
  console.log(`       ${status} (${result.runtime_ms} ms, ${result.iterations} iterations)`);
}

// Aggregate and persist summary
const summary = summarise(
  taskConfig.task_id,
  taskConfig.task_type,
  strategyName,
  allResults,
);
await saveSummary(RESULTS_DIR, taskConfig.task_id, strategyName, summary);

printSummaryTable(allResults, taskConfig.task_id, strategyName);
console.log(`Results saved to results/${taskConfig.task_id}/${strategyName}/`);
