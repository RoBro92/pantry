"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { PantryLocationSummary } from "../lib/api-types";
import { postToApi } from "../lib/client-api";
import { formatQuantityValue } from "../lib/quantity-format";
import { ModalShell } from "./modal-shell";

type StockLotMoveDialogProps = {
  householdExternalId: string;
  lotExternalId: string;
  currentLocationExternalId: string;
  currentQuantity: string;
  locations: PantryLocationSummary[];
  onClose: () => void;
};

export function StockLotMoveDialog({
  householdExternalId,
  lotExternalId,
  currentLocationExternalId,
  currentQuantity,
  locations,
  onClose,
}: StockLotMoveDialogProps) {
  const router = useRouter();
  const [quantity, setQuantity] = useState(formatQuantityValue(currentQuantity));
  const [destinationLocationExternalId, setDestinationLocationExternalId] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);

    try {
      await postToApi(`/api/households/${householdExternalId}/stock-lots/${lotExternalId}/move`, {
        quantity,
        destination_location_external_id: destinationLocationExternalId,
      });
      router.refresh();
      onClose();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not move this stock lot.");
    } finally {
      setPending(false);
    }
  }

  return (
    <ModalShell title="Move stock lot" description="Move all or part of this lot to another storage location." onClose={onClose}>
      <form className="stack" onSubmit={handleSubmit}>
        <div className="content-grid">
          <label className="field">
            <span>Quantity to move</span>
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
            <span>Destination</span>
            <select
              value={destinationLocationExternalId}
              onChange={(event) => setDestinationLocationExternalId(event.target.value)}
              required
            >
              <option value="">Select destination</option>
              {locations
                .filter((location) => location.external_id !== currentLocationExternalId)
                .map((location) => (
                  <option key={location.external_id} value={location.external_id}>
                    {location.location_group_name} / {location.name}
                  </option>
                ))}
            </select>
          </label>
        </div>
        {error ? <p className="error-text">{error}</p> : null}
        <div className="page-actions">
          <button type="submit" className="primary-button" disabled={pending}>
            {pending ? "Moving..." : "Move stock"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}
