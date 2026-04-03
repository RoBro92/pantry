"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { PantryLocationSummary } from "../lib/api-types";
import { postToApi } from "../lib/client-api";

type PantryLotActionsProps = {
  householdExternalId: string;
  lotExternalId: string;
  currentLocationExternalId: string;
  locations: PantryLocationSummary[];
};

export function PantryLotActions({
  householdExternalId,
  lotExternalId,
  currentLocationExternalId,
  locations
}: PantryLotActionsProps) {
  const router = useRouter();
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [moveError, setMoveError] = useState<string | null>(null);
  const [isRemoving, setIsRemoving] = useState(false);
  const [isMoving, setIsMoving] = useState(false);

  async function handleRemove(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsRemoving(true);
    setRemoveError(null);
    const form = event.currentTarget;

    try {
      const formData = new FormData(form);
      await postToApi(`/api/households/${householdExternalId}/stock-lots/${lotExternalId}/remove`, {
        quantity: String(formData.get("quantity") ?? "")
      });
      form.reset();
      router.refresh();
    } catch (error) {
      setRemoveError(error instanceof Error ? error.message : "Request failed.");
    } finally {
      setIsRemoving(false);
    }
  }

  async function handleMove(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsMoving(true);
    setMoveError(null);
    const form = event.currentTarget;

    try {
      const formData = new FormData(form);
      await postToApi(`/api/households/${householdExternalId}/stock-lots/${lotExternalId}/move`, {
        quantity: String(formData.get("quantity") ?? ""),
        destination_location_external_id: String(
          formData.get("destination_location_external_id") ?? ""
        )
      });
      form.reset();
      router.refresh();
    } catch (error) {
      setMoveError(error instanceof Error ? error.message : "Request failed.");
    } finally {
      setIsMoving(false);
    }
  }

  return (
    <div className="lot-actions" data-testid={`lot-actions-${lotExternalId}`}>
      <form className="inline-form" onSubmit={handleRemove} data-testid={`remove-lot-form-${lotExternalId}`}>
        <input
          name="quantity"
          type="number"
          min="0.001"
          step="0.001"
          required
          placeholder="Qty"
        />
        <button type="submit" className="ghost-button" disabled={isRemoving}>
          {isRemoving ? "Removing..." : "Remove"}
        </button>
      </form>
      {removeError ? <p className="error-text compact-error">{removeError}</p> : null}

      <form className="inline-form" onSubmit={handleMove} data-testid={`move-lot-form-${lotExternalId}`}>
        <input
          name="quantity"
          type="number"
          min="0.001"
          step="0.001"
          required
          placeholder="Qty"
        />
        <select name="destination_location_external_id" required defaultValue="">
          <option value="" disabled>
            Move to
          </option>
          {locations
            .filter((location) => location.external_id !== currentLocationExternalId)
            .map((location) => (
              <option key={location.external_id} value={location.external_id}>
                {location.location_group_name} / {location.name}
              </option>
            ))}
        </select>
        <button type="submit" className="ghost-button" disabled={isMoving}>
          {isMoving ? "Moving..." : "Move"}
        </button>
      </form>
      {moveError ? <p className="error-text compact-error">{moveError}</p> : null}
    </div>
  );
}
