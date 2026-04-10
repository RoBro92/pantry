"use client";

import { useMemo, useRef, useState } from "react";
import type {
  AIProviderConfigResponse,
  AIProviderConfigSummary,
  AIProviderHealthResponse
} from "../lib/api-types";
import {
  AI_PROVIDER_API_KEY_REQUIRED,
  AI_PROVIDER_LABELS,
  AI_PROVIDER_OPTIONS,
  type AIProviderType,
  getDefaultBaseUrl,
  getDefaultModel,
  normalizeAIProviderType
} from "../lib/ai-provider-config";
import { postToApi, putToApi } from "../lib/client-api";
import { getAIProviderLabel } from "../lib/admin-display";
import { ModalShell } from "./modal-shell";

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
  return normalizeAIProviderType(config?.provider_type) ?? "ollama";
}

function buildDraft(config: AIProviderConfigSummary | null): ProviderDraft {
  const providerType = getInitialProviderType(config);
  return {
    providerType,
    baseUrl: config?.base_url ?? getDefaultBaseUrl(providerType),
    defaultModel: config?.default_model ?? getDefaultModel(providerType),
    isEnabled: config?.is_enabled ?? true
  };
}

export function AdminAIConfigForm({
  initialConfigResponse
}: AdminAIConfigFormProps) {
  const initialDraft = buildDraft(initialConfigResponse.config);
  const [config, setConfig] = useState<AIProviderConfigSummary | null>(
    initialConfigResponse.config
      ? {
          ...initialConfigResponse.config,
          provider_type: getInitialProviderType(initialConfigResponse.config)
        }
      : null
  );
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
  const [modelQuery, setModelQuery] = useState("");
  const [draftModelSelection, setDraftModelSelection] = useState(initialDraft.defaultModel);
  const latestIssuedSaveIdRef = useRef(0);
  const latestAppliedSaveIdRef = useRef(0);

  const featureEnabled = initialConfigResponse.feature_enabled;
  const providerRequiresApiKey = AI_PROVIDER_API_KEY_REQUIRED[providerType];
  const availableModels = health?.models ?? [];
  const filteredModels = useMemo(() => {
    const normalizedQuery = modelQuery.trim().toLowerCase();
    if (!normalizedQuery) {
      return availableModels;
    }
    return availableModels.filter((model) => model.toLowerCase().includes(normalizedQuery));
  }, [availableModels, modelQuery]);

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
    setConfig({
      ...nextConfig,
      provider_type: nextProviderType
    });
    setProviderType(nextProviderType);
    setBaseUrl(nextConfig.base_url);
    setDefaultModel(nextConfig.default_model);
    setIsEnabled(nextConfig.is_enabled);
    setDraftModelSelection(nextConfig.default_model);
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
        setConfig({
          ...response.config,
          provider_type: getInitialProviderType(response.config)
        });
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

  async function handleProviderChange(nextProviderType: AIProviderType) {
    const nextBaseUrl = getDefaultBaseUrl(nextProviderType);
    const nextDefaultModel = getDefaultModel(nextProviderType);
    const nextDraft = buildCurrentDraft({
      providerType: nextProviderType,
      baseUrl: nextBaseUrl,
      defaultModel: nextDefaultModel
    });
    setProviderType(nextProviderType);
    setBaseUrl(nextBaseUrl);
    setDefaultModel(nextDefaultModel);
    setDraftModelSelection(nextDefaultModel);
    setStatusMessage(null);
    setErrorMessage(null);

    if (canPersistDraft(nextDraft)) {
      await saveDraft(nextDraft, { syncLocalState: false });
    }
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
    const saved = await saveDraft(buildCurrentDraft(), { syncLocalState: true });
    if (saved) {
      await runAutoHealthCheck();
    }
  }

  async function handleSaveModelSelection() {
    const nextDraft = buildCurrentDraft({ defaultModel: draftModelSelection });
    setDefaultModel(draftModelSelection);

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
      setIsModelPickerOpen(false);
    }
  }

  const minimumFieldsPresent =
    baseUrl.trim().length > 0 &&
    defaultModel.trim().length > 0 &&
    (!providerRequiresApiKey || Boolean(config?.has_api_key));
  const savedProviderType = normalizeAIProviderType(config?.provider_type) ?? null;
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

  return (
    <div className="stack" data-testid="admin-ai-config-page">
      <section className="panel">
        <p className="eyebrow">Instance AI Provider</p>
        <h1>Provider Setup</h1>
        <p>
          The self hosted installation uses provider details configured here. Changes save
          automatically, secrets are not shown after save, and secrets are never written to logs.
        </p>
        {!featureEnabled ? (
          <p className="error-text">AI features are disabled for this deployment.</p>
        ) : null}
        {isSaving ? <p className="status-note">Saving changes...</p> : null}
        {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
        {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
        <div className="content-grid">
          <label className="field">
            <span>Provider type</span>
            <select
              className="ai-provider-field-control"
              value={providerType}
              onChange={(event) => void handleProviderChange(event.target.value as AIProviderType)}
            >
              {AI_PROVIDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Base URL</span>
            <input
              className="ai-provider-field-control"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              onBlur={() => void handleBaseUrlBlur()}
            />
          </label>
          <label className="field">
            <span>Default model</span>
            <input
              className="ai-provider-field-control"
              value={defaultModel}
              readOnly
              aria-readonly="true"
              placeholder={getDefaultModel(providerType)}
            />
          </label>
          <label className="field">
            <span>API key</span>
            <input
              className="ai-provider-field-control"
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              onBlur={() => void handleApiKeyBlur()}
              placeholder={
                config?.has_api_key
                  ? "Stored. Enter a new key to replace it."
                  : providerRequiresApiKey
                    ? `${AI_PROVIDER_LABELS[providerType]} requires an API key`
                    : "Not required for Ollama"
              }
            />
          </label>
        </div>
        <div className="page-actions" style={{ justifyContent: "flex-start" }}>
          <button
            type="button"
            className="ghost-button"
            onClick={() => {
              setModelQuery(defaultModel);
              setDraftModelSelection(defaultModel);
              setIsModelPickerOpen(true);
            }}
          >
            Choose model
          </button>
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
          <h2>{health?.status ?? config?.health_status ?? "unknown"}</h2>
          <p>{health?.message ?? config?.health_error ?? "No health check has been recorded yet."}</p>
        </article>
        <article className="status-card">
          <p className="eyebrow">Models</p>
          <h2>{String(health?.models.length ?? config?.available_model_count ?? 0)}</h2>
          <p>Run health check to refresh the searchable model list for this provider.</p>
        </article>
      </section>

      {health && health.models.length > 0 ? (
        <section className="panel">
          <p className="eyebrow">Discovered Models</p>
          <div className="tag-row">
            {health.models.map((model) => (
              <span key={model} className="tag">
                {model}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      {isModelPickerOpen ? (
        <ModalShell
          title={`Choose ${AI_PROVIDER_LABELS[providerType]} model`}
          description="Search the discovered models or enter a model name manually. Save is the only explicit confirmation step on this page."
          onClose={() => setIsModelPickerOpen(false)}
          closeOnBackdropClick={false}
          showCloseButton={false}
          panelClassName="modal-panel modal-panel-wide"
        >
          <div className="stack">
            <label className="field">
              <span>Model name</span>
              <input
                value={draftModelSelection}
                onChange={(event) => {
                  setDraftModelSelection(event.target.value);
                  setModelQuery(event.target.value);
                }}
                placeholder={getDefaultModel(providerType)}
                autoFocus
              />
            </label>

            <section className="panel">
              <p className="eyebrow">Available Models</p>
              {filteredModels.length > 0 ? (
                <div className="tag-row">
                  {filteredModels.map((model) => (
                    <button
                      key={model}
                      type="button"
                      className="ghost-button"
                      onClick={() => {
                        setDraftModelSelection(model);
                        setModelQuery(model);
                      }}
                    >
                      {model}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="status-note">
                  {availableModels.length > 0
                    ? "No discovered models match the current search."
                    : "Run health check to populate the discovered model list, or enter a model manually."}
                </p>
              )}
            </section>

            <div className="page-actions">
              <button
                type="button"
                className="ghost-button"
                disabled={isSaving}
                onClick={() => setIsModelPickerOpen(false)}
              >
                Back
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={isSaving || !draftModelSelection.trim()}
                onClick={() => void handleSaveModelSelection()}
              >
                {isSaving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </ModalShell>
      ) : null}
    </div>
  );
}
