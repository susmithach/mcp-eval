export type TaskType = "bug_fix" | "feature" | "test_fix";
export type FailureCategory =
  | "provider_error"
  | "patch_apply_failure"
  | "no_patch"
  | "wrong_logic"
  | "runtime_error"
  | "environment_error"
  | "unknown";

export interface ResultSchema {
  // Task metadata
  task_type: TaskType;

  // Outcome
  success: boolean;
  error: string | null;

  // Timing (integer milliseconds)
  runtime_ms: number;

  // Iteration count (strategy-defined unit, e.g. LLM round-trips)
  iterations: number;

  // Tool usage
  tool_calls_total: number;
  tool_calls_by_name: Record<string, number>;

  // Token usage (populated when an LLM is involved; default 0)
  tokens_in: number;
  tokens_out: number;

  // Context / retrieval / access metrics
  context_files_count: number;
  context_test_files_count: number;
  context_source_files_count: number;
  context_total_chars: number;
  context_total_lines: number;
  retrieved_chunks_count: number;
  retrieved_files_count: number;
  retrieved_paths: string[];
  files_read_count: number;
  files_read_paths: string[];
  search_queries_count: number;

  // Patch and outcome refinement
  patch_generated: boolean;
  patch_applied: boolean;
  final_tests_passed: boolean;
  failure_category: FailureCategory | null;

  // Final diff-derived patch scope
  files_changed_count: number;
  files_changed_paths: string[];
  lines_added: number;
  lines_deleted: number;

  // Final unified diff of all changes the agent made (empty string if none)
  final_diff: string;

  // Derived efficiency metrics
  tokens_total: number;       // tokens_in + tokens_out
  context_precision: number;  // files_changed / files_accessed (0–1); 0 when no change
}
