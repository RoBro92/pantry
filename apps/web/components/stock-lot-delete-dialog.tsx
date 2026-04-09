"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { postToApi } from "../lib/client-api";
import { formatQuantityWithUnit } from "../lib/quantity-format";
import { ModalShell } from "./modal-shell";

type StockLotDeleteDialogProps = {
  householdExternalId: string;
  lotExternalId: string;
  productName: string;
  quantity: string;
  unit: string;
  onClose: () => void;
};

export function StockLotDeleteDialog({
  householdExternalId,
  lotExternalId,
  productName,
  quantity,
  unit,
  onClose,
}: StockLotDeleteDialogProps) {
  const router = useRouter();
  const [pendingAction, setPendingAction] = useState<"delete" | "buy_more" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete(action: "delete" | "buy_more") {
    setPendingAction(action);
    setError(null);
    try {
      if (action === "buy_more") {
        await postToApi(`/api/households/${householdExternalId}/stock-lots/${lotExternalId}/buy-more`, {});
      } else {
        await postToApi(`/api/households/${householdExternalId}/stock-lots/${lotExternalId}/remove`, {
          quantity,
        });
      }
      router.refresh();
      onClose();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not remove this lot.");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <ModalShell
      title="Remove stock lot"
      description={`Remove ${formatQuantityWithUnit(quantity, unit)} of ${productName}. You can also add it to the shopping list first.`}
      onClose={onClose}
    >
      <div className="stack">
        <p className="helper-text">
          Delete removes the remaining stock lot. Buy more adds the product to the active shopping list before depleting this lot.
        </p>
        {error ? <p className="error-text">{error}</p> : null}
        <div className="page-actions">
          <button
            type="button"
            className="ghost-button"
            disabled={pendingAction !== null}
            onClick={() => void handleDelete("delete")}
          >
            {pendingAction === "delete" ? "Deleting..." : "Delete"}
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={pendingAction !== null}
            onClick={() => void handleDelete("buy_more")}
          >
            {pendingAction === "buy_more" ? "Adding..." : "Buy more"}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
