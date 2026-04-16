"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { PantryProductSummary } from "../lib/api-types";
import { deleteToApi } from "../lib/client-api";
import { ModalShell } from "./modal-shell";

type PantryProductDeleteDialogProps = {
  householdExternalId: string;
  product: PantryProductSummary;
  onClose: () => void;
  onDeleted?: () => void;
};

export function PantryProductDeleteDialog({
  householdExternalId,
  product,
  onClose,
  onDeleted,
}: PantryProductDeleteDialogProps) {
  const router = useRouter();
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete() {
    setPending(true);
    setError(null);

    try {
      await deleteToApi<{ message: string }>(
        `/api/households/${householdExternalId}/products/${product.product_external_id}`,
      );
      router.refresh();
      onDeleted?.();
      onClose();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not delete this product record.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <ModalShell
      title={`Delete ${product.product_name}`}
      description="This permanently removes the product record itself, not just one stock lot."
      onClose={onClose}
    >
      <div className="stack">
        <div className="warning-callout">
          <strong>Delete the whole product record</strong>
          <p>
            This will remove <strong>{product.product_name}</strong>, its {product.lot_count} active
            stock lot{product.lot_count === 1 ? "" : "s"}, linked enrichment, aliases, barcodes,
            and related product metadata.
          </p>
          <p>Remaining stock will not be returned to the shopping list in this flow.</p>
        </div>

        <label className="field">
          <span>Type the product name to confirm</span>
          <input
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            placeholder={product.product_name}
          />
        </label>

        {error ? <p className="error-text">{error}</p> : null}

        <div className="page-actions">
          <button
            type="button"
            className="ghost-button"
            disabled={pending}
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={pending || confirmation !== product.product_name}
            onClick={() => void handleDelete()}
          >
            {pending ? "Deleting..." : "Delete product"}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
