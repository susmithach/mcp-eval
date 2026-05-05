import { AnthropicProvider } from "./anthropic_provider.js";
import { OpenAiProvider } from "./openai_provider.js";
import type { LlmProvider } from "./types.js";

export interface LlmRuntimeConfig {
  providerName: "anthropic" | "openai";
  model: string;
}

export function createLlmProvider(): {
  provider: LlmProvider;
  config: LlmRuntimeConfig;
} {
  const providerNameRaw = process.env["LLM_PROVIDER"]?.trim().toLowerCase() ?? "anthropic";

  switch (providerNameRaw) {
    case "anthropic": {
      const apiKey = process.env["ANTHROPIC_API_KEY"];
      if (!apiKey) {
        throw new Error(
          "ANTHROPIC_API_KEY environment variable is not set for LLM_PROVIDER=anthropic",
        );
      }

      const model =
        process.env["LLM_MODEL"] ??
        process.env["ANTHROPIC_MODEL"] ??
        "claude-sonnet-4-6";

      return {
        provider: new AnthropicProvider(model, apiKey),
        config: { providerName: "anthropic", model },
      };
    }

    case "openai": {
      const apiKey = process.env["OPENAI_API_KEY"];
      if (!apiKey) {
        throw new Error(
          "OPENAI_API_KEY environment variable is not set for LLM_PROVIDER=openai",
        );
      }

      const model =
        process.env["LLM_MODEL"] ??
        process.env["OPENAI_MODEL"] ??
        "gpt-4.1";
      const baseUrl = (
        process.env["OPENAI_BASE_URL"] ??
        "https://api.openai.com/v1"
      ).replace(/\/+$/, "");

      return {
        provider: new OpenAiProvider(model, apiKey, baseUrl),
        config: { providerName: "openai", model },
      };
    }

    default:
      throw new Error(
        `Unsupported LLM_PROVIDER "${providerNameRaw}". Use "anthropic" or "openai".`,
      );
  }
}
