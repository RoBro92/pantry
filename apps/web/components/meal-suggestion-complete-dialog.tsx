"use client";

import { useState } from "react";
import type {
  AIMealSuggestion,
  CompleteAIMealSuggestionResponse,
} from "../lib/api-types";
import { postToApi } from "../lib/client-api";
import { formatQuantityValue, formatQuantityWithUnit } from "../lib/quantity-format";
import { ModalShell } from "./modal-shell";

type MealSuggestionCompleteDialogProps = {
  householdExternalId: string;
  suggestion: AIMealSuggestion;
  onClose: () => void;
  onCompleted: (response: CompleteAIMealSuggestionResponse) => void;
};

function buildInitialQuantities(suggestion: AIMealSuggestion): Record<string, string> {
  const next: Record<string, string> = {};
  suggestion.ingredients.forEach((ingredient) => {
    next[ingredient.id] = ingredient.can_consume_from_pantry
      ? formatQuantityValue(ingredient.covered_quantity)
      : "0";
  });
  return next;
}

export function MealSuggestionCompleteDialog({
  householdExternalId,
  suggestion,
  onClose,
  onCompleted,
}: MealSuggestionCompleteDialogProps) {
  const [quantities, setQuantities] = useState<Record<string, string>>(
    buildInitialQuantities(suggestion),
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    setPending(true);
    setError(null);
    try {
      const response = await postToApi<CompleteAIMealSuggestionResponse>(
        `/api/households/${householdExternalId}/ai/meal-suggestions/complete`,
        {
          suggestion_id: suggestion.id,
          suggestion_title: suggestion.title,
          ingredients: suggestion.ingredients.map((ingredient) => ({
            ingredient_id: ingredient.id,
            name: ingredient.name,
            quantity: ingredient.quantity,
            unit: ingredient.unit,
            pantry_product_external_id: ingredient.pantry_product_external_id,
            consume_quantity: quantities[ingredient.id] || "0",
          })),
        },
      );
      onCompleted(response);
      onClose();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not complete this recipe deduction.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <ModalShell
      title="Complete recipe"
      description={`Confirm what Pantry should deduct for ${suggestion.title}.`}
      onClose={onClose}
      panelClassName="modal-panel meal-complete-panel"
    >
      <div className="stack">
        <p className="helper-text">
          Pantry only deducts matched ingredients with compatible pantry units. Missing or extra
          ingredients stay informational and will not fail the completion flow.
        </p>
        <div className="meal-complete-list">
          {suggestion.ingredients.map((ingredient) => {
            const maxQuantity = formatQuantityValue(ingredient.covered_quantity);
            const canConsume = ingredient.can_consume_from_pantry;
            return (
              <article key={ingredient.id} className="meal-complete-item">
                <div className="page-actions">
                  <div className="stack compact-stack">
                    <strong>{ingredient.name}</strong>
                    <p className="helper-text">
                      Recipe uses {formatQuantityWithUnit(ingredient.quantity, ingredient.unit)}.
                    </p>
                  </div>
                  <span
                    className={
                      canConsume ? "tag" : "tag subtle-tag"
                    }
                  >
                    {ingredient.availability_status.replaceAll("_", " ")}
                  </span>
                </div>
                <div className="meal-complete-grid">
                  <div className="stack compact-stack">
                    <span className="helper-text">Pantry match</span>
                    <strong>{ingredient.pantry_product_name ?? "No pantry match"}</strong>
                  </div>
                  <div className="stack compact-stack">
                    <span className="helper-text">Available now</span>
                    <strong>
                      {formatQuantityWithUnit(
                        ingredient.pantry_available_quantity,
                        ingredient.unit,
                        "Not available",
                      )}
                    </strong>
                  </div>
                  <label className="field">
                    <span>Deduct from Pantry</span>
                    <input
                      type="number"
                      min="0"
                      step="0.001"
                      max={maxQuantity || undefined}
                      value={quantities[ingredient.id] ?? "0"}
                      disabled={!canConsume || pending}
                      onChange={(event) =>
                        setQuantities((current) => ({
                          ...current,
                          [ingredient.id]: event.target.value,
                        }))
                      }
                    />
                  </label>
                </div>
                {ingredient.note ? <p className="helper-text">{ingredient.note}</p> : null}
                {ingredient.uses_near_expiry_item ? (
                  <p className="helper-text">This ingredient uses a near-expiry pantry item.</p>
                ) : null}
                {!canConsume ? (
                  <p className="helper-text">
                    Pantry cannot deduct this ingredient automatically because it is missing,
                    unmatched, or uses a different pantry unit.
                  </p>
                ) : null}
              </article>
            );
          })}
        </div>
        {error ? <p className="error-text">{error}</p> : null}
        <div className="page-actions">
          <button type="button" className="ghost-button" onClick={onClose} disabled={pending}>
            Cancel
          </button>
          <button
            type="button"
            className="primary-button"
            onClick={() => void handleConfirm()}
            disabled={pending}
          >
            {pending ? "Completing..." : "Confirm deduction"}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
