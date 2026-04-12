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
  openai: "gpt-4.1-mini",
  claude: "claude-sonnet-4-6",
  gemini: "gemini-2.5-flash",
  ollama: "qwen3:8b"
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
      description: "Good for lightweight Pantry prompts and cheaper high-volume runs."
    },
    {
      model: "gpt-4.1-mini",
      label: "Balanced",
      description: "Pantry’s default OpenAI pick for classification and everyday reasoning."
    },
    {
      model: "gpt-4.1",
      label: "Higher quality",
      description: "Use when Pantry should favour stronger categorisation quality."
    }
  ],
  claude: [
    {
      model: "claude-haiku-4-5",
      label: "Fast / low cost",
      description: "Fast and affordable for compact Pantry suggestions and classifications."
    },
    {
      model: "claude-sonnet-4-6",
      label: "Balanced",
      description: "Pantry’s default Anthropic option for speed and quality."
    },
    {
      model: "claude-opus-4-6",
      label: "Higher quality",
      description: "Use when Pantry should prioritise quality over cost and latency."
    }
  ],
  gemini: [
    {
      model: "gemini-2.5-flash-lite",
      label: "Fast / low cost",
      description: "The lightest Pantry-supported Gemini option."
    },
    {
      model: "gemini-2.5-flash",
      label: "Balanced",
      description: "Pantry’s default Gemini choice for classification and suggestions."
    },
    {
      model: "gemini-2.5-pro",
      label: "Higher quality",
      description: "Use when you want stronger Gemini reasoning quality."
    }
  ],
  ollama: [
    {
      model: "llama3.2",
      label: "Fast / local",
      description: "Good default if it is installed locally."
    },
    {
      model: "qwen3:8b",
      label: "Balanced",
      description: "Pantry’s default local model when it is available."
    },
    {
      model: "llama3.3",
      label: "Higher quality",
      description: "Use when a stronger local model is worth the extra latency."
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
