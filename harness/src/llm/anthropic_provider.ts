import Anthropic from "@anthropic-ai/sdk";
import type {
  MessageParam,
  Tool as AnthropicTool,
  ToolResultBlockParam,
  ToolUseBlock,
} from "@anthropic-ai/sdk/resources/messages.js";
import type {
  LlmConversationMessage,
  LlmProvider,
  LlmTextResponse,
  LlmToolCall,
  LlmToolDefinition,
  LlmToolResponse,
} from "./types.js";

function toAnthropicTools(tools: LlmToolDefinition[]): AnthropicTool[] {
  return tools.map((tool) => ({
    name: tool.name,
    description: tool.description,
    input_schema: tool.inputSchema,
  }));
}

function toAnthropicMessages(
  messages: LlmConversationMessage[],
): MessageParam[] {
  return messages.map((message) => {
    if (message.kind === "text") {
      return { role: "user", content: message.text };
    }

    if (message.kind === "assistant") {
      const content: Array<
        | { type: "text"; text: string }
        | { type: "tool_use"; id: string; name: string; input: Record<string, unknown> }
      > = [];

      if (message.text.trim().length > 0) {
        content.push({ type: "text", text: message.text });
      }

      for (const toolCall of message.toolCalls) {
        content.push({
          type: "tool_use",
          id: toolCall.id,
          name: toolCall.name,
          input: toolCall.input,
        });
      }

      return { role: "assistant", content };
    }

    const content: ToolResultBlockParam[] = message.results.map((result) => ({
      type: "tool_result",
      tool_use_id: result.toolCallId,
      content: result.content,
    }));

    return { role: "user", content };
  });
}

function extractText(blocks: Array<{ type: string; text?: string }>): string {
  return blocks
    .filter((block) => block.type === "text" && typeof block.text === "string")
    .map((block) => block.text ?? "")
    .join("");
}

export class AnthropicProvider implements LlmProvider {
  private readonly client: Anthropic;

  constructor(
    private readonly model: string,
    apiKey: string,
  ) {
    this.client = new Anthropic({ apiKey });
  }

  async createText(input: {
    systemPrompt: string;
    userMessage: string;
    maxTokens: number;
  }): Promise<LlmTextResponse> {
    const response = await this.client.messages.create({
      model: this.model,
      max_tokens: input.maxTokens,
      system: input.systemPrompt,
      messages: [{ role: "user", content: input.userMessage }],
    });

    return {
      text: extractText(response.content),
      usage: {
        inputTokens: response.usage.input_tokens,
        outputTokens: response.usage.output_tokens,
      },
    };
  }

  async createToolResponse(input: {
    systemPrompt: string;
    messages: LlmConversationMessage[];
    tools: LlmToolDefinition[];
    maxTokens: number;
  }): Promise<LlmToolResponse> {
    const response = await this.client.messages.create({
      model: this.model,
      max_tokens: input.maxTokens,
      system: input.systemPrompt,
      tools: toAnthropicTools(input.tools),
      messages: toAnthropicMessages(input.messages),
    });

    const toolCalls: LlmToolCall[] = response.content
      .filter((block): block is ToolUseBlock => block.type === "tool_use")
      .map((block) => ({
        id: block.id,
        name: block.name,
        input: block.input as Record<string, unknown>,
      }));

    return {
      text: extractText(response.content),
      toolCalls,
      usage: {
        inputTokens: response.usage.input_tokens,
        outputTokens: response.usage.output_tokens,
      },
    };
  }
}
