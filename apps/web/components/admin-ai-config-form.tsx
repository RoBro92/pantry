"use client";

import { useState } from "react";
import type {
  AIProviderConfigResponse,
  AIProviderConfigSummary,
  AIProviderHealthResponse
} from "../lib/api-types";
import { postToApi, putToApi } from "../lib/client-api";

type AdminAIConfigFormProps = {
  initialConfigResponse: AIProviderConfigResponse;
};

export function AdminAIConfigForm({
  initialConfigResponse
}: AdminAIConfigFormProps) {
  const [config, setConfig] = useState<AIProviderConfigSummary | null>(
    initialConfigResponse.config
  );
  const [featureEnabled] = useState(initialConfigResponse.feature_enabled);
  const [providerType, setProviderType] = useState(config?.provider_type ?? "ollama");
  const [baseUrl, setBaseUrl] = useState(config?.base_url ?? "http://host.docker.internal:11434");
  const [defaultModel, setDefaultModel] = useState(config?.default_model ?? "");
  const [apiKey, setApiKey] = useState("");
  const [isEnabled, setIsEnabled] = useState(config?.is_enabled ?? true);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [health, setHealth] = useState<AIProviderHealthResponse["health"] | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);

  async function handleSave() {
    setIsSaving(true);
    setStatusMessage(null);

    try {
      const response = await putToApi<AIProviderConfigResponse>(
        "/api/platform-admin/ai/provider-config",
        {
          provider_type: providerType,
          base_url: baseUrl,
          default_model: defaultModel,
          api_key: apiKey || null,
          is_enabled: isEnabled
        }
      );
      setConfig(response.config);
      setStatusMessage("Provider configuration saved.");
      setApiKey("");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Save failed.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleHealthCheck() {
    setIsCheckingHealth(true);
    setStatusMessage(null);

    try {
      const response = await postToApi<AIProviderHealthResponse>(
        "/api/platform-admin/ai/provider-config/health-check",
        {}
      );
      setConfig(response.config);
      setHealth(response.health);
      setStatusMessage(response.health.is_healthy ? "Health check passed." : "Health check failed.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Health check failed.");
    } finally {
      setIsCheckingHealth(false);
    }
  }

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Instance AI Provider</p>
        <h1>Provider Configuration</h1>
        <p>
          The self-hosted installation only uses provider details configured here. Secrets are not
          shown after save and are never written to logs.
        </p>
        {!featureEnabled ? (
          <p className="error-text">AI features are disabled for this deployment.</p>
        ) : null}
        {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
        <div className="content-grid">
          <label className="field">
            <span>Provider type</span>
            <select
              value={providerType}
              onChange={(event) =>
                setProviderType(event.target.value as "ollama" | "openai_compatible")
              }
            >
              <option value="ollama">Ollama</option>
              <option value="openai_compatible">OpenAI-compatible</option>
            </select>
          </label>
          <label className="field">
            <span>Base URL</span>
            <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} />
          </label>
          <label className="field">
            <span>Default model</span>
            <input
              value={defaultModel}
              onChange={(event) => setDefaultModel(event.target.value)}
              placeholder={providerType === "ollama" ? "llama3.2" : "gpt-4o-mini"}
            />
          </label>
          <label className="field">
            <span>API key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={config?.has_api_key ? "Stored. Enter a new key to replace it." : "Optional for Ollama"}
            />
          </label>
        </div>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={(event) => setIsEnabled(event.target.checked)}
          />
          <span>Enable this provider for household AI requests.</span>
        </label>
        <div className="page-actions">
          <button
            type="button"
            className="primary-button"
            disabled={isSaving}
            onClick={handleSave}
          >
            {isSaving ? "Saving..." : "Save configuration"}
          </button>
          <button
            type="button"
            className="ghost-button"
            disabled={isCheckingHealth || !config}
            onClick={handleHealthCheck}
          >
            {isCheckingHealth ? "Checking..." : "Run health check"}
          </button>
        </div>
      </section>

      <section className="status-grid">
        <article className="status-card">
          <p className="eyebrow">Configured Provider</p>
          <h2>{config?.provider_type ?? "none"}</h2>
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
          <p>Model listing is used for a lightweight provider capability check.</p>
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
    </div>
  );
}
