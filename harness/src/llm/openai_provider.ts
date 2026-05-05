import type {
  LlmConversationMessage,
  LlmProvider,
  LlmTextResponse,
  LlmToolCall,
  LlmToolDefinition,
  LlmToolResponse,
} from "./types.js";

interface OpenAiChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content?: string | null;
  tool_call_id?: string;
  tool_calls?: Array<{
    id: string;
    type: "function";
    function: {
      name: string;
      arguments: string;
    };
  }>;
}

interface OpenAiChatCompletionResponse {
  choices: Array<{
    message: {
      content: string | null;
      tool_calls?: Array<{
        id: string;
        type: "function";
        function: {
          name: string;
          arguments: string;
        };
      }>;
    };
  }>;
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
  };
}

function toOpenAiMessages(
  systemPrompt: string,
  messages: LlmConversationMessage[],
): OpenAiChatMessage[] {
  const openAiMessages: OpenAiChatMessage[] = [
    { role: "system", content: systemPrompt },
  ];

  for (const message of messages) {
    if (message.kind === "text") {
      openAiMessages.push({ role: "user", content: message.text });
      continue;
    }

    if (message.kind === "assistant") {
      openAiMessages.push({
        role: "assistant",
        content: message.text || null,
        tool_calls: message.toolCalls.map((toolCall) => ({
          id: toolCall.id,
          type: "function",
          function: {
            name: toolCall.name,
            arguments: JSON.stringify(toolCall.input),
          },
        })),
      });
      continue;
    }

    for (const result of message.results) {
      openAiMessages.push({
        role: "tool",
        tool_call_id: result.toolCallId,
        content: result.content,
      });
    }
  }

  return openAiMessages;
}

function toOpenAiTools(tools: LlmToolDefinition[]): Array<Record<string, unknown>> {
  return tools.map((tool) => ({
    type: "function",
    function: {
      name: tool.name,
      description: tool.description,
      parameters: tool.inputSchema,
    },
  }));
}

function parseToolArguments(raw: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(raw) as unknown;
    return typeof parsed === "object" && parsed !== null
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

export class OpenAiProvider implements LlmProvider {
  constructor(
    private readonly model: string,
    private readonly apiKey: string,
    private readonly baseUrl: string,
  ) {}

  async createText(input: {
    systemPrompt: string;
    userMessage: string;
    maxTokens: number;
  }): Promise<LlmTextResponse> {
    const response = await this.createChatCompletion({
      messages: [
        { role: "system", content: input.systemPrompt },
        { role: "user", content: input.userMessage },
      ],
      max_tokens: input.maxTokens,
    });

    const choice = response.choices[0]?.message;
    return {
      text: choice?.content ?? "",
      usage: {
        inputTokens: response.usage?.prompt_tokens ?? 0,
        outputTokens: response.usage?.completion_tokens ?? 0,
      },
    };
  }

  async createToolResponse(input: {
    systemPrompt: string;
    messages: LlmConversationMessage[];
    tools: LlmToolDefinition[];
    maxTokens: number;
  }): Promise<LlmToolResponse> {
    const response = await this.createChatCompletion({
      messages: toOpenAiMessages(input.systemPrompt, input.messages),
      tools: toOpenAiTools(input.tools),
      tool_choice: "auto",
      max_tokens: input.maxTokens,
    });

    const choice = response.choices[0]?.message;
    const toolCalls: LlmToolCall[] = (choice?.tool_calls ?? []).map((toolCall) => ({
      id: toolCall.id,
      name: toolCall.function.name,
      input: parseToolArguments(toolCall.function.arguments),
    }));

    return {
      text: choice?.content ?? "",
      toolCalls,
      usage: {
        inputTokens: response.usage?.prompt_tokens ?? 0,
        outputTokens: response.usage?.completion_tokens ?? 0,
      },
    };
  }

  private async createChatCompletion(
    body: Record<string, unknown>,
  ): Promise<OpenAiChatCompletionResponse> {
    const response = await fetch(`${this.baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        ...body,
      }),
    });

    const rawText = await response.text();

    if (!response.ok) {
      throw new Error(`OpenAI API error (${response.status}): ${rawText}`);
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(rawText);
    } catch {
      throw new Error(`OpenAI API returned non-JSON response: ${rawText.slice(0, 200)}`);
    }

    const result = parsed as OpenAiChatCompletionResponse;
    if (!Array.isArray(result.choices)) {
      throw new Error(
        `OpenAI API response missing 'choices' array. Raw: ${rawText.slice(0, 400)}`,
      );
    }

    return result;
  }
}
