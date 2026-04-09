"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { postToApi } from "../lib/client-api";
import { formatQuantityWithUnit } from "../lib/quantity-format";
import { ModalShell } from "./modal-shell";

type ShoppingListAddDialogProps = {
  householdExternalId: string;
  productExternalId: string;
  productName: string;
  sourceType: string;
  defaultQuantity?: string;
  defaultUnit: string;
  defaultNote?: string | null;
  defaultLocationExternalId?: string | null;
  onClose: () => void;
};

export function ShoppingListAddDialog({
  householdExternalId,
  productExternalId,
  productName,
  sourceType,
  defaultQuantity = "1",
  defaultUnit,
  defaultNote = null,
  defaultLocationExternalId = null,
  onClose,
}: ShoppingListAddDialogProps) {
  const router = useRouter();
  const [quantity, setQuantity] = useState(defaultQuantity);
  const [unit, setUnit] = useState(defaultUnit);
  const [note, setNote] = useState(defaultNote ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);

    try {
      await postToApi(`/api/households/${householdExternalId}/shopping-list/items`, {
        product_external_id: productExternalId,
        quantity,
        unit,
        note: note.trim() || null,
        pantry_location_external_id: defaultLocationExternalId,
        source_type: sourceType,
      });
      router.refresh();
      onClose();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not add this item to the shopping list.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <ModalShell
      title={`Add ${productName} to shopping list`}
      description={`Choose the amount to add. Defaulting to ${formatQuantityWithUnit(defaultQuantity, defaultUnit, "1")} keeps the request explicit.`}
      onClose={onClose}
    >
      <form className="stack" onSubmit={handleSubmit}>
        <div className="content-grid">
          <label className="field">
            <span>Quantity</span>
            <input
              type="number"
              min="0.001"
              step="0.001"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              required
            />
          </label>
          <label className="field">
            <span>Unit</span>
            <input value={unit} onChange={(event) => setUnit(event.target.value)} required />
          </label>
        </div>
        <label className="field">
          <span>Note</span>
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Optional note"
          />
        </label>
        {error ? <p className="error-text">{error}</p> : null}
        <div className="page-actions">
          <button type="submit" className="primary-button" disabled={pending}>
            {pending ? "Adding..." : "Add to shopping list"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}
