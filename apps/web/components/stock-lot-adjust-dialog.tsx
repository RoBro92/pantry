"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { putToApi } from "../lib/client-api";
import { formatQuantityValue } from "../lib/quantity-format";
import { ModalShell } from "./modal-shell";

type StockLotAdjustDialogProps = {
  householdExternalId: string;
  lotExternalId: string;
  productName: string;
  quantity: string;
  unit: string;
  locationExternalId: string;
  purchasedOn: string | null;
  expiresOn: string | null;
  note: string | null;
  onClose: () => void;
};

export function StockLotAdjustDialog({
  householdExternalId,
  lotExternalId,
  productName,
  quantity,
  unit,
  locationExternalId,
  purchasedOn,
  expiresOn,
  note,
  onClose,
}: StockLotAdjustDialogProps) {
  const router = useRouter();
  const [nextQuantity, setNextQuantity] = useState(formatQuantityValue(quantity));
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);

    try {
      await putToApi(`/api/households/${householdExternalId}/stock-lots/${lotExternalId}`, {
        location_external_id: locationExternalId,
        quantity: nextQuantity,
        note,
        purchased_on: purchasedOn,
        expires_on: expiresOn,
      });
      router.refresh();
      onClose();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not adjust this stock lot.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <ModalShell
      title="Adjust quantity"
      description={`Update the remaining ${productName} amount in one step.`}
      onClose={onClose}
      panelClassName="modal-panel modal-panel-stock-lot"
    >
      <form className="stack" onSubmit={handleSubmit}>
        <label className="field">
          <span>Remaining quantity ({unit})</span>
          <input
            type="number"
            min="0.001"
            step="0.001"
            value={nextQuantity}
            onChange={(event) => setNextQuantity(event.target.value)}
            required
          />
        </label>
        {error ? <p className="error-text">{error}</p> : null}
        <div className="page-actions">
          <button type="submit" className="primary-button" disabled={pending}>
            {pending ? "Saving..." : "Save quantity"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}
