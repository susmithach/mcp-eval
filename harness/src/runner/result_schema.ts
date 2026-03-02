/**
 * Canonical result record for a single evaluation run.
 * All fields are always present so downstream consumers can rely on a fixed shape.
 * Timestamps are intentionally omitted — only duration (runtime_ms) is stored.
 */
export interface ResultSchema {
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
}
