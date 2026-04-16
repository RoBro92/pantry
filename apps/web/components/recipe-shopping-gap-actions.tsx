"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import type { RecipeShoppingGapItem } from "../lib/api-types";
import { postToApi } from "../lib/client-api";

type RecipeShoppingGapActionsProps = {
  householdExternalId: string;
  recipeTitle: string;
  items: RecipeShoppingGapItem[];
};

export function RecipeShoppingGapActions({
  householdExternalId,
  recipeTitle,
  items,
}: RecipeShoppingGapActionsProps) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  async function addAllShoppingGaps() {
    if (items.length === 0) {
      return;
    }

    setPending(true);
    setError(null);
    setStatusMessage(null);

    try {
      for (const item of items) {
        await postToApi(`/api/households/${householdExternalId}/shopping-list/items`, {
          product_external_id: item.product_external_id,
          label: item.product_external_id ? null : item.label,
          quantity: item.quantity,
          unit: item.unit,
          note: `Recipe gap · ${recipeTitle}`,
          source_type: "recipe_gap",
        });
      }
      setStatusMessage(
        items.length === 1
          ? "Added the recipe gap to the active shopping list."
          : `Added ${items.length} recipe gaps to the active shopping list.`,
      );
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not add these recipe gaps to the shopping list.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="stack compact-stack">
      <div className="page-actions">
        <button
          type="button"
          className="primary-button"
          disabled={pending || items.length === 0}
          onClick={() => void addAllShoppingGaps()}
        >
          {pending
            ? "Adding gaps..."
            : items.length === 1
              ? "Add gap to shopping list"
              : "Add gaps to shopping list"}
        </button>
        <Link
          href={`/app/households/${householdExternalId}/shopping-list`}
          className="secondary-link compact-link"
        >
          Open shopping list
        </Link>
      </div>
      {error ? <p className="error-text">{error}</p> : null}
      {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
    </div>
  );
}
