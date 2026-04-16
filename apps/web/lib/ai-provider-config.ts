export type AIProviderType = "openai" | "claude" | "gemini" | "ollama";

type ProviderRecommendation = {
  model: string;
  label: string;
  description: string;
};

type ProviderSupportMetadata = {
  isCurrentlySupported: boolean;
  statusLabel: string;
  description: string;
};

export const AI_PROVIDER_OPTIONS: Array<{ value: AIProviderType; label: string }> = [
  { value: "openai", label: "OpenAI" },
  { value: "claude", label: "Claude (not currently supported)" },
  { value: "gemini", label: "Gemini (not currently supported)" },
  { value: "ollama", label: "Ollama (not currently supported)" }
];

export const VISIBLE_AI_PROVIDER_OPTIONS: Array<{ value: AIProviderType; label: string }> = [
  { value: "openai", label: "OpenAI" }
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
  openai: "gpt-5.4-mini",
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
      model: "gpt-4.1-mini",
      label: "Fastest / cheapest",
      description: "Lowest-cost supported option for light Pantro AI runs."
    },
    {
      model: "gpt-5.4-mini",
      label: "Recommended default",
      description: "Best balance for Pantro suggestions and product intelligence."
    },
    {
      model: "gpt-5.4",
      label: "Best quality",
      description: "Stronger output quality, with more latency and cost."
    }
  ],
  claude: [
    {
      model: "claude-haiku-4-5",
      label: "Fast / low cost",
      description: "Fast and affordable for compact Pantro suggestions and classifications."
    },
    {
      model: "claude-sonnet-4-6",
      label: "Balanced",
      description: "Pantro’s default Anthropic option for speed and quality."
    },
    {
      model: "claude-opus-4-6",
      label: "Higher quality",
      description: "Use when Pantro should prioritise quality over cost and latency."
    }
  ],
  gemini: [
    {
      model: "gemini-2.5-flash-lite",
      label: "Fast / low cost",
      description: "The lightest Pantro-supported Gemini option."
    },
    {
      model: "gemini-2.5-flash",
      label: "Balanced",
      description: "Pantro’s default Gemini choice for classification and suggestions."
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
      description: "Pantro’s default local model when it is available."
    },
    {
      model: "llama3.3",
      label: "Higher quality",
      description: "Use when a stronger local model is worth the extra latency."
    }
  ]
};

const AI_PROVIDER_SUPPORT: Record<AIProviderType, ProviderSupportMetadata> = {
  openai: {
    isCurrentlySupported: true,
    statusLabel: "Supported",
    description:
      "OpenAI is Pantro’s currently supported provider for product classification and guided meal suggestions."
  },
  claude: {
    isCurrentlySupported: false,
    statusLabel: "Foundation only",
    description:
      "Anthropic groundwork remains in the codebase, but Claude is not currently supported for Pantro’s normal AI flows."
  },
  gemini: {
    isCurrentlySupported: false,
    statusLabel: "Foundation only",
    description:
      "Gemini setup and runtime groundwork remain available, but Gemini is not currently supported for Pantro’s normal AI flows."
  },
  ollama: {
    isCurrentlySupported: false,
    statusLabel: "Foundation only",
    description:
      "Ollama setup and local-model groundwork remain available, but Ollama is not currently supported for Pantro’s normal AI flows."
  }
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

export function getAIProviderSupport(providerType: AIProviderType) {
  return AI_PROVIDER_SUPPORT[providerType];
}

export function isAIProviderCurrentlySupported(providerType: AIProviderType) {
  return AI_PROVIDER_SUPPORT[providerType].isCurrentlySupported;
}

export function providerSupportsManualModelEntry(_providerType: AIProviderType) {
  return true;
}

function normalizeModelId(value: string) {
  const normalized = value.trim().toLowerCase();
  if (normalized.startsWith("models/")) {
    return normalized.slice("models/".length);
  }
  if (normalized.startsWith("openai/")) {
    return normalized.slice("openai/".length);
  }
  return normalized;
}

function matchesRecommendedModel(candidate: string, recommendedModel: string) {
  const normalizedCandidate = normalizeModelId(candidate);
  const normalizedRecommended = normalizeModelId(recommendedModel);
  return (
    normalizedCandidate === normalizedRecommended ||
    normalizedCandidate.startsWith(`${normalizedRecommended}:`) ||
    normalizedCandidate.startsWith(`${normalizedRecommended}-`)
  );
}

function resolveRecommendedModel(availableModels: string[], desiredModel: string) {
  const exactMatch = availableModels.find((model) => matchesRecommendedModel(model, desiredModel));
  if (exactMatch) {
    return exactMatch;
  }
  return availableModels.find((model) => normalizeModelId(model).includes(normalizeModelId(desiredModel))) ?? desiredModel;
}

export function getRecommendedModels(providerType: AIProviderType, availableModels: string[]) {
  if (!isAIProviderCurrentlySupported(providerType)) {
    return [];
  }
  return AI_PROVIDER_RECOMMENDED_MODELS[providerType].map((pick) => ({
    ...pick,
    model: resolveRecommendedModel(availableModels, pick.model)
  }));
}

export function isRecommendedModel(providerType: AIProviderType, model: string) {
  return AI_PROVIDER_RECOMMENDED_MODELS[providerType].some(
    (pick) => matchesRecommendedModel(model, pick.model)
  );
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
