"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  PantryProductOptionSummary,
  RecipeDetailResponse
} from "../lib/api-types";
import { postToApi, putToApi } from "../lib/client-api";

type RecipeFormProps = {
  householdExternalId: string;
  products: PantryProductOptionSummary[];
  mode: "create" | "edit";
  initialValue?: {
    recipeExternalId: string;
    title: string;
    notes: string | null;
    ingredients: Array<{
      name: string;
      quantity: string;
      unit: string;
      note: string | null;
      product_external_id: string | null;
    }>;
  };
};

type InitialIngredient = {
  name: string;
  quantity: string;
  unit: string;
  note: string | null;
  product_external_id: string | null;
};

type IngredientDraft = {
  key: number;
  name: string;
  quantity: string;
  unit: string;
  note: string;
  product_external_id: string;
};

function buildInitialIngredients(ingredients: InitialIngredient[]): IngredientDraft[] {
  if (!ingredients || ingredients.length === 0) {
    return [{ key: 1, name: "", quantity: "", unit: "", note: "", product_external_id: "" }];
  }

  return ingredients.map((ingredient, index) => ({
    key: index + 1,
    name: ingredient.name,
    quantity: ingredient.quantity,
    unit: ingredient.unit,
    note: ingredient.note ?? "",
    product_external_id: ingredient.product_external_id ?? ""
  }));
}

export function RecipeForm({
  householdExternalId,
  products,
  mode,
  initialValue
}: RecipeFormProps) {
  const router = useRouter();
  const [title, setTitle] = useState(initialValue?.title ?? "");
  const [notes, setNotes] = useState(initialValue?.notes ?? "");
  const [ingredients, setIngredients] = useState<IngredientDraft[]>(
    buildInitialIngredients(initialValue?.ingredients ?? [])
  );
  const [nextKey, setNextKey] = useState(ingredients.length + 1);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateIngredient(key: number, field: keyof Omit<IngredientDraft, "key">, value: string) {
    setIngredients((current) =>
      current.map((ingredient) =>
        ingredient.key === key ? { ...ingredient, [field]: value } : ingredient
      )
    );
  }

  function addIngredientRow() {
    setIngredients((current) => [
      ...current,
      {
        key: nextKey,
        name: "",
        quantity: "",
        unit: "",
        note: "",
        product_external_id: ""
      }
    ]);
    setNextKey((current) => current + 1);
  }

  function removeIngredientRow(key: number) {
    setIngredients((current) =>
      current.length === 1 ? current : current.filter((ingredient) => ingredient.key !== key)
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);

    const payload = {
      title,
      notes: notes.trim() || null,
      ingredients: ingredients.map((ingredient) => ({
        name: ingredient.name,
        quantity: ingredient.quantity,
        unit: ingredient.unit,
        note: ingredient.note.trim() || null,
        product_external_id: ingredient.product_external_id || null
      }))
    };

    try {
      const response =
        mode === "create"
          ? await postToApi<RecipeDetailResponse>(
              `/api/households/${householdExternalId}/recipes`,
              payload
            )
          : await putToApi<RecipeDetailResponse>(
              `/api/households/${householdExternalId}/recipes/${initialValue?.recipeExternalId}`,
              payload
            );

      router.push(
        `/app/households/${householdExternalId}/recipes/${response.recipe.external_id}`
      );
      router.refresh();
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Request failed.");
      setPending(false);
    }
  }

  return (
    <form className="panel recipe-form" onSubmit={handleSubmit} data-testid={`recipe-form-${mode}`}>
      <p className="eyebrow">Recipe Editor</p>
      <h1>{mode === "create" ? "Create recipe" : "Edit recipe"}</h1>
      <label className="field">
        <span>Title</span>
        <input value={title} onChange={(event) => setTitle(event.target.value)} required />
      </label>
      <label className="field">
        <span>Notes</span>
        <textarea
          rows={5}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Optional prep notes, timing, or context"
        />
      </label>

      <div className="stack">
        <div className="page-actions">
          <div>
            <p className="eyebrow">Ingredients</p>
            <p className="section-copy">
              Link ingredients to product records when known. Leaving the link blank keeps the
              ingredient in the recipe and lets the API fall back to deterministic name matching.
            </p>
          </div>
          <button
            type="button"
            className="secondary-link button-link"
            onClick={addIngredientRow}
          >
            Add ingredient
          </button>
        </div>
        {products.length === 0 ? (
          <p className="section-copy">
            No product records exist yet. You can still create the recipe now and rely on name-based
            matching later, or add products from the inventory page first.
          </p>
        ) : null}

        <div className="recipe-ingredient-list">
          {ingredients.map((ingredient, index) => (
            <article key={ingredient.key} className="recipe-ingredient-card">
              <div className="page-actions">
                <strong>Ingredient {index + 1}</strong>
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => removeIngredientRow(ingredient.key)}
                  disabled={ingredients.length === 1}
                >
                  Remove
                </button>
              </div>

              <div className="recipe-form-grid">
                <label className="field">
                  <span>Name</span>
                  <input
                    value={ingredient.name}
                    onChange={(event) =>
                      updateIngredient(ingredient.key, "name", event.target.value)
                    }
                    required
                  />
                </label>
                <label className="field">
                  <span>Quantity</span>
                  <input
                    type="number"
                    min="0.001"
                    step="0.001"
                    value={ingredient.quantity}
                    onChange={(event) =>
                      updateIngredient(ingredient.key, "quantity", event.target.value)
                    }
                    required
                  />
                </label>
                <label className="field">
                  <span>Unit</span>
                  <input
                    value={ingredient.unit}
                    onChange={(event) =>
                      updateIngredient(ingredient.key, "unit", event.target.value)
                    }
                    required
                  />
                </label>
                <label className="field">
                  <span>Product record</span>
                  <select
                    value={ingredient.product_external_id}
                    onChange={(event) =>
                      updateIngredient(ingredient.key, "product_external_id", event.target.value)
                    }
                  >
                    <option value="">Auto match by ingredient name when possible</option>
                    {products.map((product) => (
                      <option key={product.external_id} value={product.external_id}>
                        {product.name} ({product.default_unit})
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <label className="field">
                <span>Optional note</span>
                <input
                  value={ingredient.note}
                  onChange={(event) => updateIngredient(ingredient.key, "note", event.target.value)}
                  placeholder="Chopped, drained, room temperature"
                />
              </label>
            </article>
          ))}
        </div>
      </div>

      {error ? <p className="error-text">{error}</p> : null}

      <div className="page-actions">
        <button type="submit" className="primary-button" disabled={pending}>
          {pending ? "Saving..." : mode === "create" ? "Create recipe" : "Save recipe"}
        </button>
      </div>
    </form>
  );
}
