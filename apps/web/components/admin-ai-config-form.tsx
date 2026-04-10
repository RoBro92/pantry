"use client";

import { useEffect, useRef, useState } from "react";
import type {
  AIProviderConfigResponse,
  AIProviderConfigSummary,
  AIProviderHealthResponse
} from "../lib/api-types";
import type { AIProviderType } from "../lib/ai-provider-config";
import {
  AI_PROVIDER_DEFINITIONS,
  getAIProviderLabel,
  getDefaultAIBaseUrl,
  getModelPlaceholder,
  getProviderDescription,
  providerRequiresApiKey
} from "../lib/ai-provider-config";
import { postToApi, putToApi } from "../lib/client-api";
import { AdminAIModelPickerModal } from "./admin-ai-model-picker-modal";

type AdminAIConfigFormProps = {
  initialConfigResponse: AIProviderConfigResponse;
};

type DraftState = {
  providerType: AIProviderType;
  baseUrl: string;
  defaultModel: string;
  isEnabled: boolean;
};

type FeedbackState = {
  tone: "error" | "success";
  text: string;
} | null;

const DEFAULT_PROVIDER: AIProviderType = "openai";

function buildDraft(config: AIProviderConfigSummary | null): DraftState {
  const providerType = config?.provider_type ?? DEFAULT_PROVIDER;
  return {
    providerType,
    baseUrl: config?.base_url ?? getDefaultAIBaseUrl(providerType) ?? "",
    defaultModel: config?.default_model ?? "",
    isEnabled: config?.is_enabled ?? true
  };
}

function getProviderButtonLabel(providerType: AIProviderType) {
  return providerType === "custom" ? "Browse or enter model" : "Choose model";
}

export function AdminAIConfigForm({
  initialConfigResponse
}: AdminAIConfigFormProps) {
  const [config, setConfig] = useState<AIProviderConfigSummary | null>(
    initialConfigResponse.config
  );
  const [draft, setDraft] = useState<DraftState>(buildDraft(initialConfigResponse.config));
  const [apiKey, setApiKey] = useState("");
  const [featureEnabled] = useState(initialConfigResponse.feature_enabled);
  const [health, setHealth] = useState<AIProviderHealthResponse["health"] | null>(null);
  const [feedback, setFeedback] = useState<FeedbackState>(null);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [isCheckingConnection, setIsCheckingConnection] = useState(false);
  const [isModelPickerOpen, setIsModelPickerOpen] = useState(false);
  const [saveState, setSaveState] = useState<"idle" | "saved" | "error" | "saving">("idle");

  const editVersionRef = useRef(0);
  const hasUnsavedChangesRef = useRef(false);
  const saveQueueRef = useRef(Promise.resolve<AIProviderConfigSummary | null>(null));

  function syncFromConfig(
    nextConfig: AIProviderConfigSummary | null,
    options: { overwriteDraft: boolean }
  ) {
    setConfig(nextConfig);
    if (options.overwriteDraft) {
      setDraft(buildDraft(nextConfig));
      setApiKey("");
      hasUnsavedChangesRef.current = false;
    }
  }

  useEffect(() => {
    syncFromConfig(initialConfigResponse.config, { overwriteDraft: true });
    setHealth(null);
    setAvailableModels([]);
    setFeedback(null);
    setSaveState("idle");
  }, [initialConfigResponse.config]);

  const providerDefinition = AI_PROVIDER_DEFINITIONS[draft.providerType];
  const hasStoredApiKey = Boolean(
    config?.has_api_key && config.provider_type === draft.providerType
  );
  const typedApiKey = apiKey.trim();
  const requiresApiKey = providerRequiresApiKey(draft.providerType);
  const connectionReady =
    draft.baseUrl.trim().length > 0 && (!requiresApiKey || hasStoredApiKey || typedApiKey.length > 0);
  const canOpenModelPicker = health?.is_healthy ?? false;

  function markDirty(clearConnectionState = false) {
    editVersionRef.current += 1;
    hasUnsavedChangesRef.current = true;
    setSaveState("idle");
    if (clearConnectionState) {
      setHealth(null);
      setAvailableModels([]);
    }
  }

  function getSavePayload(snapshot: DraftState, apiKeyValue: string) {
    return {
      provider_type: snapshot.providerType,
      base_url: snapshot.baseUrl.trim(),
      default_model: snapshot.defaultModel.trim(),
      api_key: apiKeyValue.trim() || null,
      is_enabled: snapshot.isEnabled
    };
  }

  async function persistDraft(
    snapshot: DraftState,
    apiKeyValue: string,
    saveVersion: number,
    options: {
      force?: boolean;
      successMessage?: string;
    } = {}
  ) {
    if (!snapshot.baseUrl.trim()) {
      return config;
    }
    if (!options.force && !hasUnsavedChangesRef.current) {
      return config;
    }

    setIsSaving(true);
    setSaveState("saving");
    try {
      const response = await putToApi<AIProviderConfigResponse>(
        "/api/platform-admin/ai/provider-config",
        getSavePayload(snapshot, apiKeyValue)
      );
      setConfig(response.config);
      if (saveVersion === editVersionRef.current) {
        syncFromConfig(response.config, { overwriteDraft: true });
        setSaveState("saved");
        if (options.successMessage) {
          setFeedback({ tone: "success", text: options.successMessage });
        }
      }
      return response.config;
    } catch (error) {
      if (saveVersion === editVersionRef.current) {
        setSaveState("error");
        setFeedback({
          tone: "error",
          text: error instanceof Error ? error.message : "Save failed."
        });
      }
      throw error;
    } finally {
      setIsSaving(false);
    }
  }

  function enqueueSave(
    snapshot: DraftState,
    apiKeyValue: string,
    options: {
      force?: boolean;
      successMessage?: string;
    } = {}
  ) {
    const saveVersion = editVersionRef.current;
    const task = async () => persistDraft(snapshot, apiKeyValue, saveVersion, options);
    const queued = saveQueueRef.current.then(task, task);
    saveQueueRef.current = queued.catch(() => null);
    return queued;
  }

  function handleProviderChange(nextProviderType: AIProviderType) {
    const nextBaseUrl = getDefaultAIBaseUrl(nextProviderType);
    const shouldClearCustomBaseUrl =
      nextProviderType === "custom" &&
      Object.values(AI_PROVIDER_DEFINITIONS)
        .map((provider) => provider.defaultBaseUrl)
        .includes(draft.baseUrl);
    const nextDraft: DraftState = {
      providerType: nextProviderType,
      baseUrl:
        nextProviderType === "custom"
          ? shouldClearCustomBaseUrl
            ? ""
            : draft.baseUrl
          : nextBaseUrl ?? draft.baseUrl,
      defaultModel: "",
      isEnabled: draft.isEnabled
    };

    setDraft(nextDraft);
    setApiKey("");
    setFeedback(null);
    markDirty(true);
    void enqueueSave(nextDraft, "", { successMessage: "Provider settings saved." });
  }

  function handleEnabledChange(nextIsEnabled: boolean) {
    const nextDraft = { ...draft, isEnabled: nextIsEnabled };
    setDraft(nextDraft);
    setFeedback(null);
    markDirty(false);
    void enqueueSave(nextDraft, apiKey, { successMessage: "Provider settings saved." });
  }

  async function handleCheckConnection() {
    const snapshot = { ...draft };
    const apiKeyValue = apiKey;
    setIsCheckingConnection(true);
    setFeedback(null);

    try {
      await enqueueSave(snapshot, apiKeyValue, { force: true });
      const response = await postToApi<AIProviderHealthResponse>(
        "/api/platform-admin/ai/provider-config/health-check",
        {}
      );
      setConfig(response.config);
      setHealth(response.health);
      setAvailableModels(response.health.models);
      if (response.health.is_healthy) {
        setFeedback({
          tone: "success",
          text: "Connection looks good. Choose a model next."
        });
        setIsModelPickerOpen(true);
      } else {
        setFeedback({
          tone: "error",
          text: response.health.message ?? "Connection check failed."
        });
      }
    } catch (error) {
      setFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Connection check failed."
      });
    } finally {
      setIsCheckingConnection(false);
    }
  }

  async function handleModelSave(model: string) {
    const nextDraft = { ...draft, defaultModel: model };
    setDraft(nextDraft);
    markDirty(false);
    await enqueueSave(nextDraft, apiKey, {
      force: true,
      successMessage: "Default model saved."
    });
    setIsModelPickerOpen(false);
  }

  return (
    <div className="stack" data-testid="admin-ai-config-page">
      <section className="panel ai-settings-panel">
        <div className="ai-settings-header">
          <div className="stack compact-stack">
            <p className="eyebrow">Instance AI Provider</p>
            <h1>AI setup</h1>
            <p className="section-copy">
              Choose a provider, add credentials, check the connection, then pick the model Pantry
              should use for suggestions.
            </p>
          </div>
          <div className="ai-settings-save-indicator">
            {saveState === "saving" ? <span className="pill">Saving…</span> : null}
            {saveState === "saved" ? <span className="pill is-success">Saved</span> : null}
            {saveState === "error" ? <span className="pill is-danger">Save failed</span> : null}
          </div>
        </div>

        {!featureEnabled ? (
          <p className="error-text">AI features are disabled for this deployment.</p>
        ) : null}
        {feedback ? (
          <p className={feedback.tone === "error" ? "error-text" : "status-note"}>{feedback.text}</p>
        ) : null}

        <div className="ai-setup-steps">
          <article className="ai-setup-step">
            <strong>1. Choose provider</strong>
            <span>Built-in providers prefill the known API host.</span>
          </article>
          <article className="ai-setup-step">
            <strong>2. Add credentials</strong>
            <span>Changes autosave when fields blur or toggles change.</span>
          </article>
          <article className="ai-setup-step">
            <strong>3. Check and choose model</strong>
            <span>Pick a recommended or searched model after a successful connection.</span>
          </article>
        </div>

        <div className="ai-provider-layout">
          <div className="stack">
            <label className="field">
              <span>Provider</span>
              <select
                value={draft.providerType}
                onChange={(event) => handleProviderChange(event.target.value as AIProviderType)}
              >
                {Object.entries(AI_PROVIDER_DEFINITIONS).map(([providerType, definition]) => (
                  <option key={providerType} value={providerType}>
                    {definition.label}
                  </option>
                ))}
              </select>
            </label>

            <div className="ai-provider-callout">
              <strong>{getAIProviderLabel(draft.providerType)}</strong>
              <p>{getProviderDescription(draft.providerType)}</p>
              {providerDefinition.defaultBaseUrl ? (
                <span className="pill">Default URL: {providerDefinition.defaultBaseUrl}</span>
              ) : (
                <span className="pill">Manual setup</span>
              )}
            </div>
          </div>

          <div className="stack">
            <div className="content-grid">
              <label className="field">
                <span>Base URL</span>
                <input
                  value={draft.baseUrl}
                  onChange={(event) => {
                    setDraft((current) => ({ ...current, baseUrl: event.target.value }));
                    setFeedback(null);
                    markDirty(true);
                  }}
                  onBlur={() =>
                    void enqueueSave({ ...draft }, apiKey, { successMessage: "Provider settings saved." })
                  }
                  placeholder={providerDefinition.defaultBaseUrl ?? "https://provider.example.com/v1"}
                />
              </label>

              {draft.providerType === "custom" ? (
                <label className="field">
                  <span>Model</span>
                  <input
                    value={draft.defaultModel}
                    onChange={(event) => {
                      setDraft((current) => ({ ...current, defaultModel: event.target.value }));
                      setFeedback(null);
                      markDirty(false);
                    }}
                    onBlur={() =>
                      void enqueueSave({ ...draft }, apiKey, { successMessage: "Provider settings saved." })
                    }
                    placeholder={getModelPlaceholder(draft.providerType)}
                  />
                </label>
              ) : null}

              {draft.providerType !== "ollama" ? (
                <label className="field">
                  <span>API key</span>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(event) => {
                      setApiKey(event.target.value);
                      setFeedback(null);
                      markDirty(true);
                    }}
                    onBlur={() =>
                      void enqueueSave({ ...draft }, apiKey, { successMessage: "Provider settings saved." })
                    }
                    placeholder={
                      hasStoredApiKey
                        ? "Stored. Enter a new key to replace it."
                        : requiresApiKey
                          ? "Required"
                          : "Optional"
                    }
                  />
                </label>
              ) : (
                <div className="ai-provider-callout is-muted">
                  <strong>No API key needed</strong>
                  <p>Ollama connections use the configured host directly.</p>
                </div>
              )}
            </div>

            {draft.providerType !== "ollama" && hasStoredApiKey ? (
              <p className="helper-text">An API key is stored for this provider. Leave the field blank to keep it.</p>
            ) : null}

            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={draft.isEnabled}
                onChange={(event) => handleEnabledChange(event.target.checked)}
              />
              <span>Enable this provider for household AI suggestions.</span>
            </label>

            {draft.providerType !== "custom" ? (
              <div className="ai-model-summary">
                <div className="stack compact-stack">
                  <span className="eyebrow">Default Model</span>
                  <strong>{draft.defaultModel || "No model selected yet"}</strong>
                  <p className="helper-text">
                    {draft.defaultModel
                      ? "You can re-run the connection check to review fetched models and switch later."
                      : getModelPlaceholder(draft.providerType)}
                  </p>
                </div>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={!canOpenModelPicker}
                  onClick={() => setIsModelPickerOpen(true)}
                >
                  {getProviderButtonLabel(draft.providerType)}
                </button>
              </div>
            ) : null}

            <div className="page-actions">
              <button
                type="button"
                className="primary-button"
                disabled={isCheckingConnection || !connectionReady}
                onClick={() => void handleCheckConnection()}
              >
                {isCheckingConnection ? "Checking..." : "Check connection"}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="status-grid">
        <article className="status-card">
          <p className="eyebrow">Provider</p>
          <h2>{config ? getAIProviderLabel(config.provider_type) : "Not saved yet"}</h2>
          <p>{config ? config.base_url : "Choose a provider and Pantry will autosave the configuration."}</p>
        </article>
        <article className="status-card">
          <p className="eyebrow">Connection</p>
          <h2>{health?.status ?? config?.health_status ?? "unknown"}</h2>
          <p>{health?.message ?? config?.health_error ?? "Run a connection check to confirm access and fetch models."}</p>
        </article>
        <article className="status-card">
          <p className="eyebrow">Model</p>
          <h2>{draft.defaultModel || "Not selected"}</h2>
          <p>
            {draft.defaultModel
              ? "This is the model Pantry will use for AI suggestions."
              : "No model has been selected yet."}
          </p>
        </article>
      </section>

      {isModelPickerOpen ? (
        <AdminAIModelPickerModal
          providerType={draft.providerType}
          availableModels={availableModels}
          selectedModel={draft.defaultModel}
          isSaving={isSaving}
          onClose={() => setIsModelPickerOpen(false)}
          onConfirm={(model) => handleModelSave(model)}
        />
      ) : null}
    </div>
  );
}
