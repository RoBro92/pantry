"use client";

import { useState } from "react";
import type {
  AIFeatureStatus,
  AISuggestionResponse,
  RecipeListItem
} from "../lib/api-types";
import { postToApi } from "../lib/client-api";

type HouseholdAISuggestionsProps = {
  householdExternalId: string;
  householdName: string;
  initialStatus: AIFeatureStatus;
  recipes: RecipeListItem[];
};

export function HouseholdAISuggestions({
  householdExternalId,
  householdName,
  initialStatus,
  recipes
}: HouseholdAISuggestionsProps) {
  const [status] = useState(initialStatus);
  const [kind, setKind] = useState<
    "meal_suggestions" | "expiry_first" | "buy_a_few_extra" | "recipe_gap"
  >("meal_suggestions");
  const [limit, setLimit] = useState("3");
  const [recipeExternalId, setRecipeExternalId] = useState<string>("");
  const [result, setResult] = useState<AISuggestionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleGenerate() {
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await postToApi<AISuggestionResponse>(
        `/api/households/${householdExternalId}/ai/suggestions`,
        {
          kind,
          limit: Number(limit),
          recipe_external_id: kind === "recipe_gap" ? recipeExternalId || null : null
        }
      );
      setResult(response);
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Suggestion request failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Household AI</p>
        <h1>{householdName}</h1>
        <p>
          Suggestions are read-only. They use structured pantry and recipe context, and they do not
          change pantry stock, imports, or recipes automatically.
        </p>
        <div className="tag-row">
          <span className="tag">{status.provider_type ?? "no provider"}</span>
          <span className="tag subtle-tag">{status.default_model ?? "no model"}</span>
          <span className="tag subtle-tag">{status.health_status ?? "unknown"}</span>
        </div>
        {!status.available ? (
          <p className="error-text">{status.reason ?? "AI is unavailable for this household."}</p>
        ) : null}
      </section>

      <section className="panel">
        <p className="eyebrow">Generate Suggestions</p>
        {error ? <p className="error-text">{error}</p> : null}
        <div className="content-grid">
          <label className="field">
            <span>Suggestion type</span>
            <select
              value={kind}
              onChange={(event) =>
                setKind(
                  event.target.value as
                    | "meal_suggestions"
                    | "expiry_first"
                    | "buy_a_few_extra"
                    | "recipe_gap"
                )
              }
            >
              <option value="meal_suggestions">Pantry-aware meals</option>
              <option value="expiry_first">Expiry-first</option>
              <option value="buy_a_few_extra">Buy a few extra</option>
              <option value="recipe_gap">Recipe gap explanation</option>
            </select>
          </label>
          <label className="field">
            <span>Suggestion count</span>
            <select value={limit} onChange={(event) => setLimit(event.target.value)}>
              <option value="2">2</option>
              <option value="3">3</option>
              <option value="4">4</option>
              <option value="5">5</option>
            </select>
          </label>
          {kind === "recipe_gap" ? (
            <label className="field">
              <span>Recipe</span>
              <select
                value={recipeExternalId}
                onChange={(event) => setRecipeExternalId(event.target.value)}
              >
                <option value="">Select a recipe</option>
                {recipes.map((recipe) => (
                  <option key={recipe.external_id} value={recipe.external_id}>
                    {recipe.title}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
        <button
          type="button"
          className="primary-button"
          disabled={isSubmitting || !status.feature_enabled || !status.available}
          onClick={handleGenerate}
        >
          {isSubmitting ? "Generating..." : "Generate suggestions"}
        </button>
      </section>

      {result ? (
        <>
          <section className="status-grid">
            <article className="status-card">
              <p className="eyebrow">Pantry Products</p>
              <h2>{String(result.context_snapshot.pantry_product_count)}</h2>
              <p>Current structured product set sent to the provider.</p>
            </article>
            <article className="status-card">
              <p className="eyebrow">Active Lots</p>
              <h2>{String(result.context_snapshot.active_lot_count)}</h2>
              <p>Read-only stock-lot summary included in the request context.</p>
            </article>
            <article className="status-card">
              <p className="eyebrow">Near Expiry</p>
              <h2>{String(result.context_snapshot.near_expiry_lot_count)}</h2>
              <p>Lots expiring soon that can be prioritized in suggestions.</p>
            </article>
          </section>

          <section className="panel">
            <p className="eyebrow">Results</p>
            {result.suggestions.length === 0 ? (
              <p>No structured suggestions were returned.</p>
            ) : (
              <div className="product-list">
                {result.suggestions.map((suggestion, index) => (
                  <article key={`${suggestion.title}-${index}`} className="product-card">
                    <div className="product-card-header">
                      <div>
                        <h2>{suggestion.title}</h2>
                        <p>{suggestion.summary}</p>
                      </div>
                    </div>
                    <p>{suggestion.rationale}</p>
                    <div className="tag-row">
                      {suggestion.pantry_product_names.map((item) => (
                        <span key={`${suggestion.title}-${item}`} className="tag">
                          {item}
                        </span>
                      ))}
                      {suggestion.expiring_product_names.map((item) => (
                        <span key={`${suggestion.title}-expiry-${item}`} className="tag subtle-tag">
                          expiring: {item}
                        </span>
                      ))}
                    </div>
                    {suggestion.missing_product_names.length > 0 ? (
                      <p>
                        Missing: {suggestion.missing_product_names.join(", ")}
                      </p>
                    ) : null}
                    {suggestion.extra_ingredient_names.length > 0 ? (
                      <p>
                        Extra ingredients: {suggestion.extra_ingredient_names.join(", ")}
                      </p>
                    ) : null}
                    {suggestion.substitution_ideas.length > 0 ? (
                      <p>
                        Substitutions: {suggestion.substitution_ideas.join(", ")}
                      </p>
                    ) : null}
                    {suggestion.caution ? <p className="status-note">{suggestion.caution}</p> : null}
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
