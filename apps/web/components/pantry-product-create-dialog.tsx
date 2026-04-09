"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { PantryCatalogProductSummary } from "../lib/api-types";
import { postToApi } from "../lib/client-api";
import { ModalShell } from "./modal-shell";

type PantryProductCreateDialogProps = {
  householdExternalId: string;
  initialName: string;
  initialUnit: string;
  quantitySummary: string | null;
  note: string | null;
  onCompleted: (product: PantryCatalogProductSummary) => Promise<void> | void;
  onClose: () => void;
};

export function PantryProductCreateDialog({
  householdExternalId,
  initialName,
  initialUnit,
  quantitySummary,
  note,
  onCompleted,
  onClose,
}: PantryProductCreateDialogProps) {
  const router = useRouter();
  const [name, setName] = useState(initialName);
  const [unit, setUnit] = useState(initialUnit);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);

    try {
      const product = await postToApi<PantryCatalogProductSummary>(
        `/api/households/${householdExternalId}/products`,
        {
          name,
          default_unit: unit,
          aliases: [],
          barcodes: [],
          manual_ingredient_tags: [],
        },
      );
      router.refresh();
      await onCompleted(product);
      onClose();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not create this Pantry product.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <ModalShell
      title="Create Pantry product"
      description="Create the missing product so reconciliation can write the purchased stock back into Pantry."
      onClose={onClose}
    >
      <form className="stack" onSubmit={handleSubmit}>
        <div className="inline-status-card">
          <strong>{initialName}</strong>
          <p className="helper-text">
            {quantitySummary ? `Purchased: ${quantitySummary}` : "Purchased quantity not set yet."}
          </p>
          {note ? <p className="helper-text">Note: {note}</p> : null}
        </div>
        <div className="content-grid">
          <label className="field">
            <span>Product name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          <label className="field">
            <span>Default unit</span>
            <input value={unit} onChange={(event) => setUnit(event.target.value)} required />
          </label>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
        <div className="page-actions">
          <button type="submit" className="primary-button" disabled={pending}>
            {pending ? "Creating..." : "Create product"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}
