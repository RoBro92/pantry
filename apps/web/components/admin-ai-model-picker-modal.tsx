"use client";

import { useMemo, useState } from "react";
import type { AIProviderType } from "../lib/ai-provider-config";
import {
  getAIProviderLabel,
  getAIProviderSupport,
  getRecommendedModels,
  isRecommendedModel,
  providerSupportsManualModelEntry
} from "../lib/ai-provider-config";
import { ModalShell } from "./modal-shell";

type AdminAIModelPickerModalProps = {
  providerType: AIProviderType;
  availableModels: string[];
  selectedModel: string;
  isSaving: boolean;
  onClose: () => void;
  onConfirm: (model: string) => Promise<void> | void;
};

export function AdminAIModelPickerModal({
  providerType,
  availableModels,
  selectedModel,
  isSaving,
  onClose,
  onConfirm
}: AdminAIModelPickerModalProps) {
  const [query, setQuery] = useState(selectedModel);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const normalizedQuery = query.trim().toLowerCase();
  const filteredModels = useMemo(() => {
    if (!normalizedQuery) {
      return availableModels;
    }
    return availableModels.filter((model) => model.toLowerCase().includes(normalizedQuery));
  }, [availableModels, normalizedQuery]);
  const recommendations = useMemo(
    () => getRecommendedModels(providerType, availableModels),
    [availableModels, providerType]
  );
  const providerSupport = getAIProviderSupport(providerType);
  const canConfirm = query.trim().length > 0;
  const selectedModelValue = query.trim();
  const selectedModelIsRecommended = isRecommendedModel(providerType, selectedModelValue);

  async function handleConfirm() {
    if (!canConfirm) {
      setErrorMessage("Enter or choose a model before saving.");
      return;
    }
    setErrorMessage(null);
    await onConfirm(query.trim());
  }

  return (
    <ModalShell
      title={`Choose ${getAIProviderLabel(providerType)} model`}
      description="Pick one of Pantry’s supported models first, or choose another OpenAI model if you want to try an untested option."
      onClose={onClose}
      panelClassName="modal-panel modal-panel-wide"
      closeOnBackdropClick={false}
      showCloseButton={false}
    >
      <div className="modal-form-section">
        <p className={`helper-text${providerSupport.isCurrentlySupported ? "" : " is-error"}`}>
          {providerSupport.statusLabel}. {providerSupport.description}
        </p>
        <label className="field">
          <span>Model name</span>
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Start typing a model name"
          />
        </label>
        {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
        {selectedModelValue ? (
          <p className="helper-text">
            {selectedModelIsRecommended
              ? "Pantry-supported recommendation."
              : "Selectable, but not one of Pantry’s officially recommended OpenAI models yet."}
          </p>
        ) : null}
      </div>

      {recommendations.length > 0 ? (
        <div className="modal-form-section">
          <div className="stack compact-stack">
            <h3 className="modal-section-title">Recommended picks</h3>
            <p className="helper-text">These three OpenAI models are the Pantry-supported choices right now.</p>
          </div>
          <div className="ai-model-recommendations">
            {recommendations.map((pick) => (
              <button
                key={`${pick.label}-${pick.model}`}
                type="button"
                className={`ai-model-pill${query.trim() === pick.model ? " is-active" : ""}`}
                onClick={() => setQuery(pick.model)}
              >
                <strong>{pick.label}</strong>
                <span>{pick.model}</span>
                <small>{pick.description}</small>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="modal-form-section">
        <div className="stack compact-stack">
          <h3 className="modal-section-title">Other OpenAI models</h3>
          <p className="helper-text">
            {availableModels.length > 0
              ? "These remain selectable, but Pantry treats them as untested rather than recommended."
              : providerSupportsManualModelEntry(providerType)
                ? "No models were listed. You can still enter another OpenAI model manually if needed."
                : "No models were listed. You can still try a manual OpenAI model name if your provider supports it."}
          </p>
        </div>
        {filteredModels.length > 0 ? (
          <div className="ai-model-list" role="list">
            {filteredModels.map((model) => (
              <button
                key={model}
                type="button"
                className={`ai-model-option${query.trim() === model ? " is-selected" : ""}`}
                onClick={() => setQuery(model)}
              >
                {model}
              </button>
            ))}
          </div>
        ) : (
          <p className="helper-text">No fetched models match this search yet.</p>
        )}
      </div>

      <div className="page-actions">
        <button type="button" className="ghost-button" disabled={isSaving} onClick={onClose}>
          Back
        </button>
        <button
          type="button"
          className="primary-button"
          disabled={isSaving || !canConfirm}
          onClick={() => void handleConfirm()}
        >
          {isSaving ? "Saving..." : "Save"}
        </button>
      </div>
    </ModalShell>
  );
}
