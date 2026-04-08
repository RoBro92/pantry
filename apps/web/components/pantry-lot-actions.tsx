"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { PantryLocationSummary } from "../lib/api-types";
import { postToApi } from "../lib/client-api";

type PantryLotActionsProps = {
  householdExternalId: string;
  lotExternalId: string;
  quantity: string;
  currentLocationExternalId: string;
  locations: PantryLocationSummary[];
};

export function PantryLotActions({
  householdExternalId,
  lotExternalId,
  quantity,
  currentLocationExternalId,
  locations
}: PantryLotActionsProps) {
  const router = useRouter();
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [moveError, setMoveError] = useState<string | null>(null);
  const [isRemoving, setIsRemoving] = useState(false);
  const [isDepleting, setIsDepleting] = useState(false);
  const [isMoving, setIsMoving] = useState(false);

  async function removeQuantity(value: string) {
    await postToApi(`/api/households/${householdExternalId}/stock-lots/${lotExternalId}/remove`, {
      quantity: value
    });
    router.refresh();
  }

  async function handleRemove(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsRemoving(true);
    setRemoveError(null);
    const form = event.currentTarget;

    try {
      const formData = new FormData(form);
      await removeQuantity(String(formData.get("quantity") ?? ""));
      form.reset();
    } catch (error) {
      setRemoveError(error instanceof Error ? error.message : "Request failed.");
    } finally {
      setIsRemoving(false);
    }
  }

  async function handleDeplete() {
    setIsDepleting(true);
    setRemoveError(null);
    try {
      await removeQuantity(quantity);
    } catch (error) {
      setRemoveError(error instanceof Error ? error.message : "Request failed.");
    } finally {
      setIsDepleting(false);
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
      <div className="lot-actions-row">
        <form
          className="inline-form"
          onSubmit={handleRemove}
          data-testid={`remove-lot-form-${lotExternalId}`}
        >
          <input
            name="quantity"
            type="number"
            min="0.001"
            step="0.001"
            required
            placeholder="Qty to remove"
          />
          <button type="submit" className="ghost-button" disabled={isRemoving}>
            {isRemoving ? "Removing..." : "Remove stock"}
          </button>
        </form>
        <button
          type="button"
          className="ghost-button"
          disabled={isDepleting}
          onClick={() => void handleDeplete()}
        >
          {isDepleting ? "Depleting..." : "Mark depleted"}
        </button>
      </div>
      {removeError ? <p className="error-text compact-error">{removeError}</p> : null}

      <form
        className="inline-form"
        onSubmit={handleMove}
        data-testid={`move-lot-form-${lotExternalId}`}
      >
        <input
          name="quantity"
          type="number"
          min="0.001"
          step="0.001"
          required
          placeholder="Qty to move"
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
