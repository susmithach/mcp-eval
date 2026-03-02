import type { ResultSchema } from "./result_schema.js";

export class MetricsTracker {
  private readonly startedAt: number;
  private _iterations = 0;
  private _toolCallsByName: Record<string, number> = {};
  private _tokensIn = 0;
  private _tokensOut = 0;

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

  finish(success: boolean, error?: string): ResultSchema {
    const runtime_ms = Math.round(Date.now() - this.startedAt);
    const tool_calls_total = Object.values(this._toolCallsByName).reduce(
      (sum, n) => sum + n,
      0,
    );
    return {
      success,
      error: error ?? null,
      runtime_ms,
      iterations: this._iterations,
      tool_calls_total,
      tool_calls_by_name: { ...this._toolCallsByName },
      tokens_in: this._tokensIn,
      tokens_out: this._tokensOut,
    };
  }
}
