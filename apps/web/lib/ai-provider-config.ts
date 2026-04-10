export type AIProviderType = "openai" | "claude" | "gemini" | "ollama";

type ProviderRecommendation = {
  model: string;
  label: string;
  description: string;
};

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

const AI_PROVIDER_RECOMMENDED_MODELS: Record<AIProviderType, ProviderRecommendation[]> = {
  openai: [
    {
      model: "gpt-4o-mini",
      label: "Fast / low cost",
      description: "Good default for lightweight Pantry suggestions."
    },
    {
      model: "gpt-4.1",
      label: "Balanced",
      description: "A steady middle ground for quality and cost."
    }
  ],
  claude: [
    {
      model: "claude-3-5-haiku-latest",
      label: "Fast / low cost",
      description: "Fast and affordable for compact Pantry suggestions."
    },
    {
      model: "claude-sonnet-4-0",
      label: "Balanced",
      description: "A strong default for quality and responsiveness."
    }
  ],
  gemini: [
    {
      model: "gemini-2.0-flash",
      label: "Fast / low cost",
      description: "Good default for lightweight Pantry suggestions."
    },
    {
      model: "gemini-2.5-pro",
      label: "Stronger",
      description: "Use when you want stronger reasoning quality."
    }
  ],
  ollama: [
    {
      model: "llama3.2",
      label: "Fast / local",
      description: "Good default if it is installed locally."
    },
    {
      model: "qwen2.5:7b-instruct",
      label: "Balanced",
      description: "A practical local model if available."
    }
  ]
};

export function getDefaultBaseUrl(providerType: AIProviderType) {
  return AI_PROVIDER_DEFAULT_BASE_URLS[providerType];
}

export function getDefaultModel(providerType: AIProviderType) {
  return AI_PROVIDER_DEFAULT_MODELS[providerType];
}

export function getAIProviderLabel(providerType: AIProviderType) {
  return AI_PROVIDER_LABELS[providerType];
}

export function providerSupportsManualModelEntry(_providerType: AIProviderType) {
  return true;
}

function normalizeModelId(value: string) {
  return value.trim().toLowerCase();
}

function resolveRecommendedModel(availableModels: string[], desiredModel: string) {
  const desired = normalizeModelId(desiredModel);
  const exactMatch = availableModels.find((model) => normalizeModelId(model) === desired);
  if (exactMatch) {
    return exactMatch;
  }
  return availableModels.find((model) => normalizeModelId(model).includes(desired)) ?? desiredModel;
}

export function getRecommendedModels(providerType: AIProviderType, availableModels: string[]) {
  return AI_PROVIDER_RECOMMENDED_MODELS[providerType].map((pick) => ({
    ...pick,
    model: resolveRecommendedModel(availableModels, pick.model)
  }));
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
