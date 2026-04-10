export type AIProviderType = "openai" | "claude" | "gemini" | "ollama";

export const AI_PROVIDER_OPTIONS: Array<{ value: AIProviderType; label: string }> = [
  { value: "openai", label: "OpenAI" },
  { value: "claude", label: "Claude" },
  { value: "gemini", label: "Gemini" },
  { value: "ollama", label: "Ollama" }
];

export const AI_PROVIDER_LABELS: Record<AIProviderType, string> = {
  openai: "OpenAI",
  claude: "Claude",
  gemini: "Gemini",
  ollama: "Ollama"
};

export const AI_PROVIDER_DEFAULT_BASE_URLS: Record<AIProviderType, string> = {
  openai: "https://api.openai.com/v1",
  claude: "https://api.anthropic.com",
  gemini: "https://generativelanguage.googleapis.com",
  ollama: "http://localhost:11434"
};

export const AI_PROVIDER_DEFAULT_MODELS: Record<AIProviderType, string> = {
  openai: "gpt-4o-mini",
  claude: "claude-3-5-haiku-latest",
  gemini: "gemini-2.0-flash",
  ollama: "llama3.2"
};

export const AI_PROVIDER_API_KEY_REQUIRED: Record<AIProviderType, boolean> = {
  openai: true,
  claude: true,
  gemini: true,
  ollama: false
};

export function getDefaultBaseUrl(providerType: AIProviderType) {
  return AI_PROVIDER_DEFAULT_BASE_URLS[providerType];
}

export function getDefaultModel(providerType: AIProviderType) {
  return AI_PROVIDER_DEFAULT_MODELS[providerType];
}

export function normalizeAIProviderType(providerType: string | null | undefined): AIProviderType | null {
  if (!providerType) {
    return null;
  }
  if (providerType === "openai_compatible") {
    return "openai";
  }
  return AI_PROVIDER_OPTIONS.some((option) => option.value === providerType)
    ? (providerType as AIProviderType)
    : null;
}
