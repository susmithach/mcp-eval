export interface LlmUsage {
  inputTokens: number;
  outputTokens: number;
}

export interface LlmToolDefinition {
  name: string;
  description: string;
  inputSchema: {
    type: "object";
    properties: Record<string, unknown>;
    required?: string[];
  };
}

export interface LlmToolCall {
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export interface LlmToolResult {
  toolCallId: string;
  content: string;
}

export type LlmConversationMessage =
  | {
      role: "user";
      kind: "text";
      text: string;
    }
  | {
      role: "assistant";
      kind: "assistant";
      text: string;
      toolCalls: LlmToolCall[];
    }
  | {
      role: "user";
      kind: "tool_results";
      results: LlmToolResult[];
    };

export interface LlmTextResponse {
  text: string;
  usage: LlmUsage;
}

export interface LlmToolResponse {
  text: string;
  toolCalls: LlmToolCall[];
  usage: LlmUsage;
}

export interface LlmProvider {
  createText(input: {
    systemPrompt: string;
    userMessage: string;
    maxTokens: number;
  }): Promise<LlmTextResponse>;

  createToolResponse(input: {
    systemPrompt: string;
    messages: LlmConversationMessage[];
    tools: LlmToolDefinition[];
    maxTokens: number;
  }): Promise<LlmToolResponse>;
}
