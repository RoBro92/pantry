"use client";

import { useRef, useState } from "react";
import type {
  AIProviderConfigResponse,
  AIProviderConfigSummary,
  AIProviderHealthResponse
} from "../lib/api-types";
import {
  AI_PROVIDER_API_KEY_REQUIRED,
  AI_PROVIDER_LABELS,
  type AIProviderType,
  getAIProviderSupport,
  getDefaultBaseUrl,
  getDefaultModel,
  normalizeAIProviderType
} from "../lib/ai-provider-config";
import { postToApi, putToApi } from "../lib/client-api";
import { getAIProviderLabel } from "../lib/admin-display";
import { AdminAIModelPickerModal } from "./admin-ai-model-picker-modal";

type AdminAIConfigFormProps = {
  initialConfigResponse: AIProviderConfigResponse;
};

type ProviderDraft = {
  providerType: AIProviderType;
  baseUrl: string;
  defaultModel: string;
  isEnabled: boolean;
};

function getInitialProviderType(config: AIProviderConfigSummary | null): AIProviderType {
  void config;
  return "openai";
}

function buildDraft(config: AIProviderConfigSummary | null): ProviderDraft {
  const providerType = getInitialProviderType(config);
  const usesVisibleProvider = normalizeAIProviderType(config?.provider_type) === providerType;
  return {
    providerType,
    baseUrl: usesVisibleProvider ? (config?.base_url ?? getDefaultBaseUrl(providerType)) : getDefaultBaseUrl(providerType),
    defaultModel: usesVisibleProvider
      ? (config?.default_model ?? getDefaultModel(providerType))
      : getDefaultModel(providerType),
    isEnabled: config?.is_enabled ?? true
  };
}

function buildVisibleConfigSummary(config: AIProviderConfigSummary | null): AIProviderConfigSummary | null {
  if (!config) {
    return null;
  }
  const draft = buildDraft(config);
  return {
    ...config,
    provider_type: draft.providerType,
    base_url: draft.baseUrl,
    default_model: draft.defaultModel
  };
}

export function AdminAIConfigForm({
  initialConfigResponse
}: AdminAIConfigFormProps) {
  const initialDraft = buildDraft(initialConfigResponse.config);
  const [config, setConfig] = useState<AIProviderConfigSummary | null>(buildVisibleConfigSummary(initialConfigResponse.config));
  const [providerType, setProviderType] = useState<AIProviderType>(initialDraft.providerType);
  const [baseUrl, setBaseUrl] = useState(initialDraft.baseUrl);
  const [defaultModel, setDefaultModel] = useState(initialDraft.defaultModel);
  const [apiKey, setApiKey] = useState("");
  const [isEnabled, setIsEnabled] = useState(initialDraft.isEnabled);
  const [health, setHealth] = useState<AIProviderHealthResponse["health"] | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [isModelPickerOpen, setIsModelPickerOpen] = useState(false);
  const latestIssuedSaveIdRef = useRef(0);
  const latestAppliedSaveIdRef = useRef(0);

  const featureEnabled = initialConfigResponse.feature_enabled;
  const providerRequiresApiKey = AI_PROVIDER_API_KEY_REQUIRED[providerType];
  const providerSupport = getAIProviderSupport(providerType);
  const availableModels = health?.models ?? [];

  function buildCurrentDraft(overrides?: Partial<ProviderDraft>): ProviderDraft {
    return {
      providerType,
      baseUrl,
      defaultModel,
      isEnabled,
      ...overrides
    };
  }

  function syncDraftFromConfig(nextConfig: AIProviderConfigSummary) {
    const nextProviderType = getInitialProviderType(nextConfig);
    setConfig(buildVisibleConfigSummary(nextConfig));
    setProviderType(nextProviderType);
    setBaseUrl(nextConfig.base_url);
    setDefaultModel(nextConfig.default_model);
    setIsEnabled(nextConfig.is_enabled);
  }

  function resolveApiKeyForSave() {
    const trimmedApiKey = apiKey.trim();
    return trimmedApiKey ? trimmedApiKey : null;
  }

  function canPersistDraft(draft: ProviderDraft) {
    if (!draft.baseUrl.trim() || !draft.defaultModel.trim()) {
      return false;
    }
    if (!AI_PROVIDER_API_KEY_REQUIRED[draft.providerType]) {
      return true;
    }
    return Boolean(resolveApiKeyForSave() || config?.has_api_key);
  }

  async function saveDraft(
    draft: ProviderDraft,
    options?: {
      successMessage?: string | null;
      syncLocalState?: boolean;
    }
  ) {
    if (!canPersistDraft(draft)) {
      return false;
    }

    const saveId = latestIssuedSaveIdRef.current + 1;
    latestIssuedSaveIdRef.current = saveId;
    setIsSaving(true);
    setErrorMessage(null);

    const apiKeyForSave = resolveApiKeyForSave();

    try {
      const response = await putToApi<AIProviderConfigResponse>(
        "/api/platform-admin/ai/provider-config",
        {
          provider_type: draft.providerType,
          base_url: draft.baseUrl,
          default_model: draft.defaultModel,
          api_key: apiKeyForSave,
          is_enabled: draft.isEnabled
        }
      );

      if (!response.config || saveId < latestAppliedSaveIdRef.current) {
        return true;
      }

      latestAppliedSaveIdRef.current = saveId;
      setHealth(null);
      if (options?.syncLocalState !== false) {
        syncDraftFromConfig(response.config);
      } else {
        setConfig(buildVisibleConfigSummary(response.config));
      }
      if (apiKeyForSave) {
        setApiKey((currentValue) => (currentValue.trim() === apiKeyForSave ? "" : currentValue));
      }
      if (options?.successMessage) {
        setStatusMessage(options.successMessage);
      }
      return true;
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Save failed.");
      return false;
    } finally {
      if (saveId === latestIssuedSaveIdRef.current) {
        setIsSaving(false);
      }
    }
  }

  async function handleHealthCheck() {
    setIsCheckingHealth(true);
    setErrorMessage(null);
    setStatusMessage(null);

    try {
      const response = await postToApi<AIProviderHealthResponse>(
        "/api/platform-admin/ai/provider-config/health-check",
        {}
      );
      syncDraftFromConfig(response.config);
      setHealth(response.health);
      setStatusMessage(response.health.is_healthy ? "Health check passed." : "Health check failed.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Health check failed.");
    } finally {
      setIsCheckingHealth(false);
    }
  }

  async function runAutoHealthCheck() {
    if (!featureEnabled || isCheckingHealth) {
      return;
    }
    await handleHealthCheck();
  }

  async function handleEnabledChange(nextIsEnabled: boolean) {
    const nextDraft = buildCurrentDraft({ isEnabled: nextIsEnabled });
    setIsEnabled(nextIsEnabled);
    setStatusMessage(null);
    setErrorMessage(null);

    if (canPersistDraft(nextDraft)) {
      await saveDraft(nextDraft, { syncLocalState: false });
    }
  }

  async function handleBaseUrlBlur() {
    await saveDraft(buildCurrentDraft(), { syncLocalState: true });
  }

  async function handleApiKeyBlur() {
    if (!resolveApiKeyForSave()) {
      return;
    }
    setIsModelPickerOpen(false);
    const saved = await saveDraft(buildCurrentDraft(), { syncLocalState: true });
    if (saved) {
      await runAutoHealthCheck();
    }
  }

  async function handleSaveModelSelection(nextModel: string) {
    const normalizedModel = nextModel.trim();
    const nextDraft = buildCurrentDraft({ defaultModel: normalizedModel });
    setDefaultModel(normalizedModel);

    if (!canPersistDraft(nextDraft)) {
      setStatusMessage("Model selected. Finish the remaining fields to autosave this provider.");
      setIsModelPickerOpen(false);
      return;
    }

    const saved = await saveDraft(nextDraft, {
      successMessage: "Model saved.",
      syncLocalState: true
    });
    if (saved) {
      await runAutoHealthCheck();
      setIsModelPickerOpen(false);
    }
  }

  const minimumFieldsPresent =
    baseUrl.trim().length > 0 &&
    defaultModel.trim().length > 0 &&
    (!providerRequiresApiKey || Boolean(config?.has_api_key));
  const savedProviderType = normalizeAIProviderType(config?.provider_type) ?? null;
  const hasStoredApiKeyForSelectedProvider =
    savedProviderType === providerType && Boolean(config?.has_api_key);
  const hasUnsavedChanges =
    savedProviderType !== providerType ||
    (config?.base_url ?? "") !== baseUrl ||
    (config?.default_model ?? "") !== defaultModel ||
    (config?.is_enabled ?? true) !== isEnabled ||
    apiKey.trim().length > 0;
  const canRunHealthCheck =
    featureEnabled &&
    !isSaving &&
    !isCheckingHealth &&
    Boolean(config) &&
    minimumFieldsPresent &&
    !hasUnsavedChanges;
  const effectiveHealthStatus = health?.status ?? config?.health_status ?? "unknown";
  const effectiveHealthMessage =
    health?.message ??
    config?.health_error ??
    (
      effectiveHealthStatus === "unknown"
        ? "No health check has been recorded yet. Pantry rechecks provider health when AI requests run."
        : "No issues reported."
    );

  return (
    <div className="stack" data-testid="admin-ai-config-page">
      <section className="panel">
        <p className="eyebrow">Instance AI Provider</p>
        <h1>Provider Setup</h1>
        <p>
          The self hosted installation uses provider details configured here. Changes save
          automatically, secrets are not shown after save, and secrets are never written to logs.
        </p>
        <p className="helper-text">
          Pantry records provider health when you save or explicitly recheck it here, and AI requests
          also perform a fresh health check before they run.
        </p>
        <p className={`helper-text${providerSupport.isCurrentlySupported ? "" : " is-error"}`}>
          {providerSupport.statusLabel}. {providerSupport.description}
        </p>
        {!featureEnabled ? (
          <p className="error-text">AI features are disabled for this deployment.</p>
        ) : null}
        {isSaving ? <p className="status-note">Saving changes...</p> : null}
        {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
        {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
        <div className="content-grid ai-provider-top-grid">
          <label className="field ai-provider-top-field">
            <span>Provider</span>
            <div className="ai-provider-readonly-value" aria-label="Provider type">
              OpenAI
            </div>
          </label>
          <label className="field ai-provider-top-field">
            <span>Base URL</span>
            <div className="ai-provider-readonly-value" aria-label="Base URL">
              {baseUrl}
            </div>
          </label>
          <label className="field ai-provider-top-field">
            <span>Default model</span>
            <div className="ai-provider-readonly-value" aria-label="Default model">
              {defaultModel || getDefaultModel(providerType)}
            </div>
            <div className="ai-provider-model-action">
              <button
                type="button"
                className="ghost-button"
                onClick={() => {
                  setIsModelPickerOpen(true);
                }}
              >
                Choose model
              </button>
            </div>
          </label>
          <label className="field ai-provider-top-field">
            <span>API key</span>
            <input
              className="ai-provider-field-control"
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              onBlur={() => void handleApiKeyBlur()}
              placeholder={
                hasStoredApiKeyForSelectedProvider
                  ? "Stored. Enter a new key to replace it."
                  : providerRequiresApiKey
                    ? `${AI_PROVIDER_LABELS[providerType]} requires an API key`
                    : "Not required for this provider"
              }
            />
          </label>
        </div>
        <div className="stack" style={{ gap: "0.75rem", marginTop: "1rem" }}>
          <label className="checkbox-row" style={{ margin: 0 }}>
            <input
              type="checkbox"
              checked={isEnabled}
              onChange={(event) => void handleEnabledChange(event.target.checked)}
            />
            <span>Enable this provider for household AI requests.</span>
          </label>
          <div className="page-actions" style={{ justifyContent: "flex-start" }}>
            <button
              type="button"
              className="ghost-button"
              disabled={!canRunHealthCheck}
              onClick={() => void handleHealthCheck()}
            >
              {isCheckingHealth ? "Checking..." : "Run health check"}
            </button>
          </div>
        </div>
        {!minimumFieldsPresent ? (
          <p className="status-note">
            Add a base URL and {providerRequiresApiKey ? "save an API key" : "finish autosaving"} before running the health check.
          </p>
        ) : hasUnsavedChanges ? (
          <p className="status-note">
            Health check uses the current autosaved configuration. Finish autosaving the latest
            changes first.
          </p>
        ) : !providerSupport.isCurrentlySupported ? (
          <p className="status-note">
            Pantry keeps this provider visible for future validation, but OpenAI is the supported
            choice for classification and guided meal suggestions right now.
          </p>
        ) : null}
      </section>

      <section className="status-grid">
        <article className="status-card">
          <p className="eyebrow">Configured Provider</p>
          <h2>{getAIProviderLabel(config?.provider_type)}</h2>
          <p>{config ? `${config.base_url} · ${config.default_model}` : "No provider configured yet."}</p>
        </article>
        <article className="status-card">
          <p className="eyebrow">Health</p>
          <h2>{effectiveHealthStatus}</h2>
          <p>{effectiveHealthMessage}</p>
        </article>
        <article className="status-card">
          <p className="eyebrow">Models</p>
          <h2>{String(health?.models.length ?? config?.available_model_count ?? 0)}</h2>
          <p>Save or re-run the health check to refresh the searchable model list for this provider.</p>
        </article>
      </section>

      {isModelPickerOpen ? (
        <AdminAIModelPickerModal
          providerType={providerType}
          availableModels={availableModels}
          selectedModel={defaultModel || getDefaultModel(providerType)}
          isSaving={isSaving}
          onClose={() => setIsModelPickerOpen(false)}
          onConfirm={(model) => handleSaveModelSelection(model)}
        />
      ) : null}
    </div>
  );
}
