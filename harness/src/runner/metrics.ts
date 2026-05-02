import type {
  FailureCategory,
  ResultSchema,
  TaskType,
} from "./result_schema.js";

interface ContextMetrics {
  context_files_count: number;
  context_test_files_count: number;
  context_source_files_count: number;
  context_total_chars: number;
  context_total_lines: number;
}

interface RetrievalMetrics {
  retrieved_chunks_count: number;
  retrieved_files_count: number;
  retrieved_paths: string[];
}

interface AccessMetrics {
  files_read_count: number;
  files_read_paths: string[];
  search_queries_count: number;
}

interface DiffStats {
  files_changed_count: number;
  files_changed_paths: string[];
  lines_added: number;
  lines_deleted: number;
}

function countLines(text: string): number {
  if (text.length === 0) return 0;
  return text.split("\n").length;
}

function parseDiffStats(diff: string): DiffStats {
  if (diff.trim().length === 0) {
    return {
      files_changed_count: 0,
      files_changed_paths: [],
      lines_added: 0,
      lines_deleted: 0,
    };
  }

  const changedPaths: string[] = [];
  let linesAdded = 0;
  let linesDeleted = 0;

  for (const line of diff.split("\n")) {
    if (line.startsWith("diff --git a/")) {
      const match = line.match(/^diff --git a\/(.+?) b\/.+$/);
      if (match) {
        changedPaths.push(match[1]);
      }
      continue;
    }

    if (line.startsWith("+++ ") || line.startsWith("--- ")) {
      continue;
    }

    if (line.startsWith("+")) {
      linesAdded++;
      continue;
    }

    if (line.startsWith("-")) {
      linesDeleted++;
    }
  }

  return {
    files_changed_count: changedPaths.length,
    files_changed_paths: changedPaths,
    lines_added: linesAdded,
    lines_deleted: linesDeleted,
  };
}

function inferFailureCategory(args: {
  success: boolean;
  error: string | undefined;
  explicit: FailureCategory | null;
  patchGenerated: boolean;
  patchApplied: boolean;
  finalDiff: string;
}): FailureCategory | null {
  if (args.success) return null;
  if (args.explicit) return args.explicit;

  const error = (args.error ?? "").toLowerCase();
  if (error.length > 0) {
    if (
      error.includes("429") ||
      error.includes("rate limit") ||
      error.includes("credit balance") ||
      error.includes("provider")
    ) {
      return "provider_error";
    }
    if (
      error.includes("git apply") ||
      error.includes("patch") ||
      error.includes("apply_patch")
    ) {
      return "patch_apply_failure";
    }
    if (
      error.includes("working tree is not clean") ||
      error.includes("enoent") ||
      error.includes("no such file") ||
      error.includes("pytest")
    ) {
      return "environment_error";
    }
    return "runtime_error";
  }

  // Fix #5: use git diff as the authoritative source of truth.
  // patchApplied is a bookkeeping flag that can be false even when the Codex
  // fallback successfully wrote the file (it returns applied:false on error
  // paths). The diff never lies — if it's non-empty, the patch landed.
  const diffPresent = args.finalDiff.trim().length > 0;

  if (!args.patchGenerated && !diffPresent) {
    return "no_patch";
  }
  if (!diffPresent) {
    // Something was attempted (patchGenerated=true) but nothing changed on disk.
    return "patch_apply_failure";
  }
  // Diff is non-empty → file was changed. Tests still failed → wrong fix.
  return "wrong_logic";
}

export class MetricsTracker {
  private readonly startedAt: number;
  private _iterations = 0;
  private _toolCallsByName: Record<string, number> = {};
  private _tokensIn = 0;
  private _tokensOut = 0;
  private _finalDiff = "";
  private _contextMetrics: ContextMetrics = {
    context_files_count: 0,
    context_test_files_count: 0,
    context_source_files_count: 0,
    context_total_chars: 0,
    context_total_lines: 0,
  };
  private _retrievalMetrics: RetrievalMetrics = {
    retrieved_chunks_count: 0,
    retrieved_files_count: 0,
    retrieved_paths: [],
  };
  private _accessMetrics: AccessMetrics = {
    files_read_count: 0,
    files_read_paths: [],
    search_queries_count: 0,
  };
  private _patchGenerated = false;
  private _patchApplied = false;
  private _finalTestsPassed = false;
  private _failureCategory: FailureCategory | null = null;

  constructor() {
    this.startedAt = Date.now();
  }

  recordToolCall(name: string): void {
    this._toolCallsByName[name] = (this._toolCallsByName[name] ?? 0) + 1;
  }

  incrementIterations(): void {
    this._iterations++;
  }

  addTokens(tokensIn: number, tokensOut: number): void {
    this._tokensIn += tokensIn;
    this._tokensOut += tokensOut;
  }

  setFinalDiff(diff: string): void {
    this._finalDiff = diff;
  }

  setContextMetrics(metrics: Partial<ContextMetrics>): void {
    this._contextMetrics = {
      ...this._contextMetrics,
      ...metrics,
    };
  }

  setRetrievalMetrics(metrics: Partial<RetrievalMetrics>): void {
    this._retrievalMetrics = {
      ...this._retrievalMetrics,
      ...metrics,
      retrieved_paths:
        metrics.retrieved_paths === undefined
          ? this._retrievalMetrics.retrieved_paths
          : [...metrics.retrieved_paths],
    };
  }

  setAccessMetrics(metrics: Partial<AccessMetrics>): void {
    this._accessMetrics = {
      ...this._accessMetrics,
      ...metrics,
      files_read_paths:
        metrics.files_read_paths === undefined
          ? this._accessMetrics.files_read_paths
          : [...metrics.files_read_paths],
    };
  }

  setPatchGenerated(value: boolean): void {
    this._patchGenerated = value;
  }

  setPatchApplied(value: boolean): void {
    this._patchApplied = value;
  }

  setFinalTestsPassed(value: boolean): void {
    this._finalTestsPassed = value;
  }

  setFailureCategory(value: FailureCategory | null): void {
    this._failureCategory = value;
  }

  finish(task_type: TaskType, success: boolean, error?: string): ResultSchema {
    const runtime_ms = Math.round(Date.now() - this.startedAt);
    const tool_calls_total = Object.values(this._toolCallsByName).reduce(
      (sum, n) => sum + n,
      0,
    );
    const diffStats = parseDiffStats(this._finalDiff);

    const tokens_total = this._tokensIn + this._tokensOut;

    // Prefer MCP files_read > RAG retrieved_files > prompt context_files
    const filesAccessed =
      this._accessMetrics.files_read_count ||
      this._retrievalMetrics.retrieved_files_count ||
      this._contextMetrics.context_files_count;
    const context_precision =
      filesAccessed > 0 && diffStats.files_changed_count > 0
        ? Math.min(1, diffStats.files_changed_count / filesAccessed)
        : 0;

    const failureCategory = inferFailureCategory({
      success,
      error,
      explicit: this._failureCategory,
      patchGenerated: this._patchGenerated,
      patchApplied: this._patchApplied,
      finalDiff: this._finalDiff,
    });
    return {
      task_type,
      success,
      error: error ?? null,
      runtime_ms,
      iterations: this._iterations,
      tool_calls_total,
      tool_calls_by_name: { ...this._toolCallsByName },
      tokens_in: this._tokensIn,
      tokens_out: this._tokensOut,
      context_files_count: this._contextMetrics.context_files_count,
      context_test_files_count: this._contextMetrics.context_test_files_count,
      context_source_files_count: this._contextMetrics.context_source_files_count,
      context_total_chars: this._contextMetrics.context_total_chars,
      context_total_lines: this._contextMetrics.context_total_lines,
      retrieved_chunks_count: this._retrievalMetrics.retrieved_chunks_count,
      retrieved_files_count: this._retrievalMetrics.retrieved_files_count,
      retrieved_paths: [...this._retrievalMetrics.retrieved_paths],
      files_read_count: this._accessMetrics.files_read_count,
      files_read_paths: [...this._accessMetrics.files_read_paths],
      search_queries_count: this._accessMetrics.search_queries_count,
      patch_generated: this._patchGenerated,
      patch_applied: this._patchApplied,
      final_tests_passed: this._finalTestsPassed,
      failure_category: failureCategory,
      files_changed_count: diffStats.files_changed_count,
      files_changed_paths: diffStats.files_changed_paths,
      lines_added: diffStats.lines_added,
      lines_deleted: diffStats.lines_deleted,
      final_diff: this._finalDiff,
      tokens_total,
      context_precision,
    };
  }
}
