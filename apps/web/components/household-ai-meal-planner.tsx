"use client";

import Link from "next/link";
import { useState } from "react";
import type {
  AIHouseholdMemberSummary,
  AIMealPlannerResponse,
  AIMealSuggestion,
  AIMealSuggestionIngredient,
  AIMealSuggestionResponse,
  CompleteAIMealSuggestionResponse,
} from "../lib/api-types";
import {
  getAIProviderSupport,
  normalizeAIProviderType,
} from "../lib/ai-provider-config";
import { postToApi } from "../lib/client-api";
import { formatQuantityValue, formatQuantityWithUnit } from "../lib/quantity-format";
import { MealSuggestionCompleteDialog } from "./meal-suggestion-complete-dialog";
import { TextTagInput } from "./text-tag-input";

const DIETARY_SUGGESTIONS = [
  "Vegan",
  "Vegetarian",
  "Pescatarian",
  "Dairy-free",
  "Gluten-free",
  "Nut allergy",
  "Egg-free",
];

type HouseholdAIMealPlannerProps = {
  householdExternalId: string;
  initialPlanner: AIMealPlannerResponse;
  isPlatformAdmin: boolean;
};

function dedupe(values: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  values.forEach((rawValue) => {
    const value = rawValue.trim();
    if (!value) {
      return;
    }
    const key = value.toLowerCase();
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    result.push(value);
  });
  return result;
}

function collectBasePreferencePills(
  selectedUserExternalIds: string[],
  members: AIHouseholdMemberSummary[],
  householdDietaryPreferences: string[],
): string[] {
  const selectedMembers = members.filter((member) =>
    selectedUserExternalIds.includes(member.user_external_id),
  );
  return dedupe([
    ...householdDietaryPreferences,
    ...selectedMembers.flatMap((member) => member.dietary_preferences),
  ]);
}

function formatMealTime(totalTimeMinutes: number | null): string {
  if (!totalTimeMinutes) {
    return "Flexible timing";
  }
  return `${totalTimeMinutes} min total`;
}

function updateSuggestionAfterCompletion(
  suggestion: AIMealSuggestion,
  completion: CompleteAIMealSuggestionResponse,
): AIMealSuggestion {
  const consumedById = new Map(
    completion.consumed_ingredients.map((ingredient) => [ingredient.ingredient_id, ingredient]),
  );
  const ingredients = suggestion.ingredients.map((ingredient) => {
    const consumed = consumedById.get(ingredient.id);
    if (!consumed) {
      return ingredient;
    }
    const nextAvailable = Math.max(
      Number(ingredient.pantry_available_quantity) - Number(consumed.consumed_quantity),
      0,
    ).toFixed(3);
    const nextCovered = Math.max(
      Number(ingredient.covered_quantity) - Number(consumed.consumed_quantity),
      0,
    ).toFixed(3);
    const nextMissing = Math.max(
      Number(ingredient.quantity) - Number(nextCovered),
      0,
    ).toFixed(3);
    const availabilityStatus: AIMealSuggestionIngredient["availability_status"] =
      Number(nextCovered) === 0
        ? "missing"
        : Number(nextMissing) === 0
          ? "available"
          : "partial";
    return {
      ...ingredient,
      pantry_available_quantity: nextAvailable,
      covered_quantity: nextCovered,
      missing_quantity: nextMissing,
      availability_status: availabilityStatus,
      can_consume_from_pantry: Number(nextCovered) > 0,
    };
  });

  return {
    ...suggestion,
    ingredients,
    pantry_ingredients_available: dedupe(
      ingredients
        .filter((ingredient) => Number(ingredient.covered_quantity) > 0)
        .map((ingredient) => ingredient.name),
    ),
    extra_ingredients_needed: dedupe(
      ingredients
        .filter(
          (ingredient) =>
            ingredient.is_extra_ingredient ||
            ["missing", "unmatched", "unit_mismatch"].includes(ingredient.availability_status),
        )
        .map((ingredient) => ingredient.name),
    ),
  };
}

export function HouseholdAIMealPlanner({
  householdExternalId,
  initialPlanner,
  isPlatformAdmin,
}: HouseholdAIMealPlannerProps) {
  const members = initialPlanner.members;
  const [peopleCount, setPeopleCount] = useState(
    Math.max(1, Math.min(members.length || 2, 4)),
  );
  const [selectedUserExternalIds, setSelectedUserExternalIds] = useState<string[]>(
    members.slice(0, Math.min(members.length, 2)).map((member) => member.user_external_id),
  );
  const [mealType, setMealType] = useState<"breakfast" | "lunch" | "dinner">("dinner");
  const [hasExtraPortions, setHasExtraPortions] = useState(false);
  const [extraPortionCount, setExtraPortionCount] = useState(0);
  const [maxTotalMinutes, setMaxTotalMinutes] = useState("45");
  const [prioritizeNearExpiry, setPrioritizeNearExpiry] = useState(
    initialPlanner.pantry_summary.near_expiry_lot_count > 0,
  );
  const [allowExtraIngredients, setAllowExtraIngredients] = useState(true);
  const [pantryOnly, setPantryOnly] = useState(false);
  const [removedPreferencePills, setRemovedPreferencePills] = useState<string[]>([]);
  const [temporaryIncludePreferences, setTemporaryIncludePreferences] = useState<string[]>([]);
  const [temporaryExcludePreferences, setTemporaryExcludePreferences] = useState<string[]>([]);
  const [includeDraft, setIncludeDraft] = useState("");
  const [excludeDraft, setExcludeDraft] = useState("");
  const [result, setResult] = useState<AIMealSuggestionResponse | null>(null);
  const [selectedSuggestionId, setSelectedSuggestionId] = useState<string | null>(null);
  const [completionSummary, setCompletionSummary] =
    useState<CompleteAIMealSuggestionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [completeSuggestionId, setCompleteSuggestionId] = useState<string | null>(null);

  const basePreferencePills = collectBasePreferencePills(
    selectedUserExternalIds,
    members,
    initialPlanner.household_dietary_preferences,
  );
  const selectedSuggestion =
    result?.suggestions.find((suggestion) => suggestion.id === selectedSuggestionId) ?? null;
  const completionSuggestion =
    result?.suggestions.find((suggestion) => suggestion.id === completeSuggestionId) ?? null;
  const normalizedProviderType = normalizeAIProviderType(initialPlanner.feature.provider_type);
  const providerSupport = normalizedProviderType
    ? getAIProviderSupport(normalizedProviderType)
    : null;

  async function handleGenerate() {
    if (members.length > 0 && selectedUserExternalIds.length === 0) {
      setError("Select at least one household member for this meal suggestion.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setCompletionSummary(null);

    try {
      const response = await postToApi<AIMealSuggestionResponse>(
        `/api/households/${householdExternalId}/ai/meal-suggestions`,
        {
          people_count: peopleCount,
          selected_user_external_ids: selectedUserExternalIds,
          meal_type: mealType,
          extra_portion_count: hasExtraPortions ? extraPortionCount : 0,
          max_total_minutes: maxTotalMinutes ? Number(maxTotalMinutes) : null,
          prioritize_near_expiry: prioritizeNearExpiry,
          allow_extra_ingredients: pantryOnly ? false : allowExtraIngredients,
          pantry_only: pantryOnly,
          temporary_include_preferences: temporaryIncludePreferences,
          temporary_exclude_preferences: temporaryExcludePreferences,
          removed_preference_pills: removedPreferencePills,
        },
      );
      setResult(response);
      setSelectedSuggestionId(response.suggestions[0]?.id ?? null);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Meal suggestion request failed.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Guided AI Meal Suggestions</p>
        <h1>{initialPlanner.household_name}</h1>
        <p className="section-copy">
          Build a shortlist around the people eating, pantry stock on hand, near-expiry items, and
          dietary preferences already stored in Pantry.
        </p>
        <div className="tag-row">
          <span className="tag">{initialPlanner.feature.provider_type ?? "no provider"}</span>
          <span className="tag subtle-tag">
            {initialPlanner.feature.default_model ?? "no model"}
          </span>
          <span className="tag subtle-tag">
            {initialPlanner.feature.health_status ?? "unknown"}
          </span>
          <span className="tag subtle-tag">
            {initialPlanner.pantry_summary.pantry_product_count} pantry products
          </span>
          <span className="tag subtle-tag">
            {initialPlanner.pantry_summary.local_recipe_count} local recipes
          </span>
        </div>
        {providerSupport && !providerSupport.isCurrentlySupported ? (
          <p className="helper-text is-error">{providerSupport.description}</p>
        ) : null}
        {!initialPlanner.feature.available ? (
          <div className="stack">
            <p className="error-text">
              {initialPlanner.feature.reason ?? "AI is unavailable for this household."}
            </p>
            {isPlatformAdmin ? (
              <p className="section-copy">
                <Link href="/admin/ai" className="inline-link">
                  Open AI configuration
                </Link>{" "}
                to review provider settings and run a health check.
              </p>
            ) : (
              <p className="section-copy">
                Ask a platform admin to review the installation AI provider settings.
              </p>
            )}
          </div>
        ) : null}
      </section>

      <section className="panel meal-planner-panel">
        <div className="stack compact-stack">
          <p className="eyebrow">Plan The Meal</p>
          <h2 className="section-heading">One guided request</h2>
          <p className="section-copy">
            Start with a shortlist, then open one recipe and optionally deduct what you actually
            used from Pantry.
          </p>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
        <div className="meal-planner-grid">
          <label className="field">
            <span>Number of people</span>
            <input
              type="number"
              min="1"
              max="12"
              value={peopleCount}
              onChange={(event) => setPeopleCount(Number(event.target.value) || 1)}
            />
          </label>
          <label className="field">
            <span>Meal type</span>
            <select
              value={mealType}
              onChange={(event) =>
                setMealType(event.target.value as "breakfast" | "lunch" | "dinner")
              }
            >
              <option value="breakfast">Breakfast</option>
              <option value="lunch">Lunch</option>
              <option value="dinner">Dinner</option>
            </select>
          </label>
          <label className="field">
            <span>Maximum total time (minutes)</span>
            <input
              type="number"
              min="5"
              max="360"
              step="5"
              value={maxTotalMinutes}
              onChange={(event) => setMaxTotalMinutes(event.target.value)}
            />
          </label>
          <div className="field">
            <span>Extra portions</span>
            <div className="inline-toggle-row">
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={hasExtraPortions}
                  onChange={(event) => {
                    setHasExtraPortions(event.target.checked);
                    if (!event.target.checked) {
                      setExtraPortionCount(0);
                    } else if (extraPortionCount === 0) {
                      setExtraPortionCount(1);
                    }
                  }}
                />
                <span>Make extra portions</span>
              </label>
              <select
                value={String(extraPortionCount)}
                onChange={(event) => setExtraPortionCount(Number(event.target.value))}
                disabled={!hasExtraPortions}
              >
                <option value="1">1 extra</option>
                <option value="2">2 extra</option>
                <option value="3">3 extra</option>
                <option value="4">4 extra</option>
              </select>
            </div>
          </div>
        </div>

        <div className="stack compact-stack">
          <span className="field-label">Who is this for?</span>
          <div className="member-pill-grid">
            {members.map((member) => {
              const selected = selectedUserExternalIds.includes(member.user_external_id);
              return (
                <button
                  key={member.user_external_id}
                  type="button"
                  className={selected ? "member-pill is-selected" : "member-pill"}
                  onClick={() => {
                    const nextSelected = selected
                      ? selectedUserExternalIds.filter(
                          (userExternalId) => userExternalId !== member.user_external_id,
                        )
                      : [...selectedUserExternalIds, member.user_external_id];
                    setSelectedUserExternalIds(nextSelected);
                    setRemovedPreferencePills((current) =>
                      current.filter((pill) =>
                        collectBasePreferencePills(
                          nextSelected,
                          members,
                          initialPlanner.household_dietary_preferences,
                        )
                          .map((value) => value.toLowerCase())
                          .includes(pill.toLowerCase()),
                      ),
                    );
                    if (nextSelected.length > peopleCount) {
                      setPeopleCount(nextSelected.length);
                    }
                  }}
                >
                  <strong>{member.display_name}</strong>
                  <span>
                    {member.dietary_preferences.length > 0
                      ? member.dietary_preferences.join(", ")
                      : "No stored preferences"}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="stack compact-stack">
          <span className="field-label">Preference pills for this request</span>
          <div className="tag-row">
            {basePreferencePills.length === 0 ? (
              <span className="helper-text">
                Select one or more users to pull through stored dietary preferences.
              </span>
            ) : (
              basePreferencePills.map((pill) => {
                const removed = removedPreferencePills.some(
                  (value) => value.toLowerCase() === pill.toLowerCase(),
                );
                return (
                  <button
                    key={pill}
                    type="button"
                    className={removed ? "tag subtle-tag is-removable" : "tag is-removable"}
                    onClick={() =>
                      setRemovedPreferencePills((current) =>
                        removed
                          ? current.filter((value) => value.toLowerCase() !== pill.toLowerCase())
                          : [...current, pill],
                      )
                    }
                  >
                    {pill}
                    <span>{removed ? "Restore" : "Remove"}</span>
                  </button>
                );
              })
            )}
          </div>
          <TextTagInput
            label="Add temporary preferences to include"
            tags={temporaryIncludePreferences}
            newValue={includeDraft}
            onNewValueChange={setIncludeDraft}
            onAddTag={(value) => {
              const normalized = value.trim();
              if (!normalized) {
                return;
              }
              setTemporaryIncludePreferences((current) => dedupe([...current, normalized]));
              setIncludeDraft("");
            }}
            onRemoveTag={(value) =>
              setTemporaryIncludePreferences((current) =>
                current.filter((item) => item.toLowerCase() !== value.toLowerCase()),
              )
            }
            placeholder="High-protein, kid-friendly, spicy"
            inputName="meal_suggestion_include"
            suggestions={DIETARY_SUGGESTIONS}
            helperText="These are temporary for this one suggestion request."
          />
          <TextTagInput
            label="Add temporary exclusions"
            tags={temporaryExcludePreferences}
            newValue={excludeDraft}
            onNewValueChange={setExcludeDraft}
            onAddTag={(value) => {
              const normalized = value.trim();
              if (!normalized) {
                return;
              }
              setTemporaryExcludePreferences((current) => dedupe([...current, normalized]));
              setExcludeDraft("");
            }}
            onRemoveTag={(value) =>
              setTemporaryExcludePreferences((current) =>
                current.filter((item) => item.toLowerCase() !== value.toLowerCase()),
              )
            }
            placeholder="Peanuts, mushrooms, shellfish"
            inputName="meal_suggestion_exclude"
            suggestions={DIETARY_SUGGESTIONS}
            helperText="Use this for one-off allergies, dislikes, or temporary constraints."
          />
        </div>

        <div className="content-grid">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={prioritizeNearExpiry}
              onChange={(event) => setPrioritizeNearExpiry(event.target.checked)}
            />
            <span>
              Prioritise near-expiry items
              {initialPlanner.pantry_summary.near_expiry_product_names.length > 0
                ? ` (${initialPlanner.pantry_summary.near_expiry_product_names.join(", ")})`
                : ""}
            </span>
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={pantryOnly}
              onChange={(event) => {
                const nextPantryOnly = event.target.checked;
                setPantryOnly(nextPantryOnly);
                if (nextPantryOnly) {
                  setAllowExtraIngredients(false);
                }
              }}
            />
            <span>Pantry-only mode</span>
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={allowExtraIngredients}
              disabled={pantryOnly}
              onChange={(event) => setAllowExtraIngredients(event.target.checked)}
            />
            <span>Allow a few extra ingredients</span>
          </label>
        </div>

        <div className="page-actions">
          <button
            type="button"
            className="primary-button"
            onClick={() => void handleGenerate()}
            disabled={!initialPlanner.feature.available || isSubmitting}
          >
            {isSubmitting ? "Building shortlist..." : "Build meal shortlist"}
          </button>
        </div>
      </section>

      {result ? (
        <>
          <section className="status-grid">
            <article className="status-card">
              <p className="eyebrow">Shortlist</p>
              <h2>{String(result.suggestions.length)}</h2>
              <p>Meal suggestions returned for this request.</p>
            </article>
            <article className="status-card">
              <p className="eyebrow">Selected Users</p>
              <h2>{String(result.context_snapshot.selected_user_count)}</h2>
              <p>Household members included in the dietary context.</p>
            </article>
            <article className="status-card">
              <p className="eyebrow">Pantry Mode</p>
              <h2>{result.context_snapshot.pantry_only ? "Only" : "Plus extras"}</h2>
              <p>
                {result.context_snapshot.effective_preference_count} effective dietary preference
                pills were applied.
              </p>
            </article>
          </section>

          <section className="panel">
            <div className="stack compact-stack">
              <p className="eyebrow">Shortlist</p>
              <h2 className="section-heading">Choose one to open</h2>
            </div>
            <div className="meal-shortlist-grid">
              {result.suggestions.map((suggestion) => {
                const selected = selectedSuggestionId === suggestion.id;
                return (
                  <article
                    key={suggestion.id}
                    className={selected ? "recipe-card is-selected" : "recipe-card"}
                  >
                    <div className="recipe-card-header">
                      <div>
                        <h3>{suggestion.title}</h3>
                        <p>{suggestion.short_summary}</p>
                      </div>
                      <span className="tag">{formatMealTime(suggestion.total_time_minutes)}</span>
                    </div>
                    <p>{suggestion.why_it_matches}</p>
                    <p className="helper-text">{suggestion.dietary_fit_summary}</p>
                    <div className="tag-row">
                      {suggestion.pantry_ingredients_available.slice(0, 5).map((item) => (
                        <span key={`${suggestion.id}-${item}`} className="tag">
                          {item}
                        </span>
                      ))}
                      {suggestion.extra_ingredients_needed.slice(0, 4).map((item) => (
                        <span key={`${suggestion.id}-extra-${item}`} className="tag subtle-tag">
                          extra: {item}
                        </span>
                      ))}
                    </div>
                    {suggestion.near_expiry_note ? (
                      <p className="helper-text">{suggestion.near_expiry_note}</p>
                    ) : null}
                    <div className="page-actions">
                      <button
                        type="button"
                        className="primary-button"
                        onClick={() => setSelectedSuggestionId(suggestion.id)}
                      >
                        {selected ? "Opened" : "View recipe"}
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        </>
      ) : null}

      {selectedSuggestion ? (
        <section className="panel meal-detail-panel">
          <div className="page-actions">
            <div className="stack compact-stack">
              <p className="eyebrow">Recipe Detail</p>
              <h2 className="section-heading">{selectedSuggestion.title}</h2>
              <p className="section-copy">{selectedSuggestion.short_summary}</p>
            </div>
            <div className="stack compact-stack meal-detail-actions">
              <span className="tag">{formatMealTime(selectedSuggestion.total_time_minutes)}</span>
              <button
                type="button"
                className="primary-button"
                onClick={() => setCompleteSuggestionId(selectedSuggestion.id)}
              >
                Complete recipe
              </button>
            </div>
          </div>
          <p>{selectedSuggestion.why_it_matches}</p>
          <div className="tag-row">
            <span className="tag">{selectedSuggestion.source.label}</span>
            {selectedSuggestion.source.recipe_external_id ? (
              <Link
                href={`/app/households/${householdExternalId}/recipes/${selectedSuggestion.source.recipe_external_id}`}
                className="secondary-link compact-link"
              >
                View linked local recipe
              </Link>
            ) : null}
            {selectedSuggestion.source.recipe_url ? (
              <a
                href={selectedSuggestion.source.recipe_url}
                className="secondary-link compact-link"
                target="_blank"
                rel="noreferrer"
              >
                Open source
              </a>
            ) : null}
          </div>

          {completionSummary && completionSummary.suggestion_id === selectedSuggestion.id ? (
            <div className="info-callout">
              <strong>Recipe completion saved</strong>
              <p>
                {completionSummary.completed
                  ? "Pantry stock was deducted for the matched ingredients you confirmed."
                  : "The recipe was marked complete, but nothing could be deducted automatically."}
              </p>
              {completionSummary.warnings.length > 0 ? (
                <ul className="callout-list">
                  {completionSummary.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}

          <div className="content-grid meal-detail-grid">
            <article className="panel meal-detail-subpanel">
              <p className="eyebrow">Ingredients</p>
              <div className="meal-ingredient-list">
                {selectedSuggestion.ingredients.map((ingredient) => (
                  <article key={ingredient.id} className="meal-ingredient-card">
                    <div className="page-actions">
                      <div className="stack compact-stack">
                        <strong>{ingredient.name}</strong>
                        <span className="helper-text">
                          {formatQuantityWithUnit(ingredient.quantity, ingredient.unit)}
                        </span>
                      </div>
                      <span
                        className={
                          ingredient.availability_status === "available"
                            ? "tag"
                            : ingredient.availability_status === "partial"
                              ? "tag subtle-tag"
                              : "tag subtle-tag"
                        }
                      >
                        {ingredient.availability_status.replaceAll("_", " ")}
                      </span>
                    </div>
                    <p className="helper-text">
                      {ingredient.pantry_product_name
                        ? `Pantry match: ${ingredient.pantry_product_name}`
                        : "No pantry match"}
                    </p>
                    <p className="helper-text">
                      Available:{" "}
                      {formatQuantityWithUnit(
                        ingredient.pantry_available_quantity,
                        ingredient.unit,
                        "Not available",
                      )}
                    </p>
                    {ingredient.missing_quantity !== "0.000" ? (
                      <p className="helper-text">
                        Missing: {formatQuantityWithUnit(ingredient.missing_quantity, ingredient.unit)}
                      </p>
                    ) : null}
                    {ingredient.note ? <p className="helper-text">{ingredient.note}</p> : null}
                    {ingredient.uses_near_expiry_item ? (
                      <p className="helper-text">Uses a near-expiry pantry item.</p>
                    ) : null}
                  </article>
                ))}
              </div>
            </article>

            <article className="panel meal-detail-subpanel">
              <p className="eyebrow">Steps</p>
              <ol className="detail-list numbered-detail-list">
                {selectedSuggestion.steps.map((step) => (
                  <li key={step}>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </article>
          </div>
        </section>
      ) : null}

      {completionSuggestion ? (
        <MealSuggestionCompleteDialog
          householdExternalId={householdExternalId}
          suggestion={completionSuggestion}
          onClose={() => setCompleteSuggestionId(null)}
          onCompleted={(completion) => {
            setCompletionSummary(completion);
            setResult((current) =>
              current
                ? {
                    ...current,
                    suggestions: current.suggestions.map((suggestion) =>
                      suggestion.id === completion.suggestion_id
                        ? updateSuggestionAfterCompletion(suggestion, completion)
                        : suggestion,
                    ),
                  }
                : current,
            );
          }}
        />
      ) : null}
    </div>
  );
}
