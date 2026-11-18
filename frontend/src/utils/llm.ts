import type { LlmProvider, LlmSettingsResponse } from "../api/types";

export const LLM_PROVIDER_LABEL: Record<LlmProvider, string> = {
  groq: "Groq",
  openai: "OpenAI",
  openrouter: "OpenRouter",
};

/** The last four characters of the server's hint, when it has them. */
export function llmKeyTail(keyHint: string): string {
  const match = keyHint.match(/([A-Za-z0-9]{4})$/);
  return match ? match[1] : keyHint;
}

/** One line for the settings overview row. */
export function llmStatusText(settings: LlmSettingsResponse | null, failed: boolean): string {
  if (settings === null) return failed ? "Could not load" : "Loading…";
  if (!settings.configured || settings.provider === null) return "Using the app's shared model";
  return `Using your ${LLM_PROVIDER_LABEL[settings.provider]} key ending ${llmKeyTail(settings.key_hint)}`;
}
