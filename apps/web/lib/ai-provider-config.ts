export type AIProviderType = "openai" | "claude" | "ollama" | "custom";

type ProviderRecommendation = {
  model: string;
  label: string;
  description: string;
};

type ProviderConfigDefinition = {
  label: string;
  description: string;
  defaultBaseUrl: string | null;
  apiKeyRequired: boolean;
  manualModelEntry: boolean;
  modelPlaceholder: string;
  quickPicks: ProviderRecommendation[];
};

export const AI_PROVIDER_DEFINITIONS: Record<AIProviderType, ProviderConfigDefinition> = {
  openai: {
    label: "OpenAI",
    description: "Use OpenAI directly with the standard API base URL and an API key.",
    defaultBaseUrl: "https://api.openai.com/v1",
    apiKeyRequired: true,
    manualModelEntry: false,
    modelPlaceholder: "Choose a model after checking the connection",
    quickPicks: [
      {
        model: "gpt-5-mini",
        label: "Fast / low cost",
        description: "Good default for lightweight Pantry suggestions."
      },
      {
        model: "gpt-4.1",
        label: "Balanced",
        description: "A steady middle ground for quality and cost."
      },
      {
        model: "gpt-5.2",
        label: "Stronger",
        description: "Use when you want better reasoning at higher cost."
      }
    ]
  },
  claude: {
    label: "Claude",
    description: "Use Anthropic’s Claude API with an API key and native Claude model IDs.",
    defaultBaseUrl: "https://api.anthropic.com",
    apiKeyRequired: true,
    manualModelEntry: false,
    modelPlaceholder: "Choose a Claude model after checking the connection",
    quickPicks: [
      {
        model: "claude-3-5-haiku-20241022",
        label: "Fast / low cost",
        description: "Fast and affordable for compact Pantry suggestions."
      },
      {
        model: "claude-sonnet-4-20250514",
        label: "Balanced",
        description: "A strong default for quality and responsiveness."
      },
      {
        model: "claude-opus-4-20250514",
        label: "Stronger",
        description: "Use when you want the strongest Claude option."
      }
    ]
  },
  ollama: {
    label: "Ollama",
    description: "Connect to a local or remote Ollama host. No API key is required.",
    defaultBaseUrl: "http://host.docker.internal:11434",
    apiKeyRequired: false,
    manualModelEntry: false,
    modelPlaceholder: "Choose an installed Ollama model after checking the connection",
    quickPicks: [
      {
        model: "llama3.2:3b",
        label: "Fast / low cost",
        description: "Good fit for small local inference if it is installed."
      },
      {
        model: "qwen2.5:7b-instruct",
        label: "Balanced",
        description: "A practical middle-ground local model if available."
      },
      {
        model: "llama3.1:8b-instruct",
        label: "Stronger",
        description: "A stronger local model if your host can support it."
      }
    ]
  },
  custom: {
    label: "Custom",
    description: "Manual provider path for OpenAI-compatible endpoints and other custom setups.",
    defaultBaseUrl: null,
    apiKeyRequired: false,
    manualModelEntry: true,
    modelPlaceholder: "Enter a model name or use fetched models after checking the connection",
    quickPicks: []
  }
};

export function getAIProviderLabel(provider: AIProviderType) {
  return AI_PROVIDER_DEFINITIONS[provider].label;
}

export function getDefaultAIBaseUrl(provider: AIProviderType) {
  return AI_PROVIDER_DEFINITIONS[provider].defaultBaseUrl;
}

export function providerRequiresApiKey(provider: AIProviderType) {
  return AI_PROVIDER_DEFINITIONS[provider].apiKeyRequired;
}

export function providerSupportsManualModelEntry(provider: AIProviderType) {
  return AI_PROVIDER_DEFINITIONS[provider].manualModelEntry;
}

export function getModelPlaceholder(provider: AIProviderType) {
  return AI_PROVIDER_DEFINITIONS[provider].modelPlaceholder;
}

export function getProviderDescription(provider: AIProviderType) {
  return AI_PROVIDER_DEFINITIONS[provider].description;
}

function normalizeModelId(value: string) {
  return value.trim().toLowerCase();
}

function resolveRecommendedModel(
  availableModels: string[],
  desiredModel: string,
) {
  const desired = normalizeModelId(desiredModel);
  const exactMatch = availableModels.find((model) => normalizeModelId(model) === desired);
  if (exactMatch) {
    return exactMatch;
  }

  return (
    availableModels.find((model) => normalizeModelId(model).includes(desired)) ?? desiredModel
  );
}

export function getRecommendedModels(
  provider: AIProviderType,
  availableModels: string[],
): ProviderRecommendation[] {
  return AI_PROVIDER_DEFINITIONS[provider].quickPicks.map((pick) => ({
    ...pick,
    model: resolveRecommendedModel(availableModels, pick.model)
  }));
}
