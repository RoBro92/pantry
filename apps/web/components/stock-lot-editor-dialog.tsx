"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { PantryLocationSummary } from "../lib/api-types";
import { postToApi, putToApi } from "../lib/client-api";
import { ModalShell } from "./modal-shell";

type StockLotEditorDialogProps = {
  householdExternalId: string;
  locations: PantryLocationSummary[];
  productExternalId: string;
  mode: "create" | "edit";
  onClose: () => void;
  initialValues: {
    lotExternalId?: string;
    productName: string;
    quantity: string;
    unit: string;
    locationExternalId: string;
    purchasedOn: string | null;
    expiresOn: string | null;
    note: string | null;
  };
};

export function StockLotEditorDialog({
  householdExternalId,
  locations,
  productExternalId,
  mode,
  onClose,
  initialValues,
}: StockLotEditorDialogProps) {
  const router = useRouter();
  const [quantity, setQuantity] = useState(initialValues.quantity);
  const [locationExternalId, setLocationExternalId] = useState(initialValues.locationExternalId);
  const [purchasedOn, setPurchasedOn] = useState(initialValues.purchasedOn ?? "");
  const [expiresOn, setExpiresOn] = useState(initialValues.expiresOn ?? "");
  const [note, setNote] = useState(initialValues.note ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);

    try {
      if (mode === "create") {
        await postToApi(`/api/households/${householdExternalId}/stock-lots`, {
          product_external_id: productExternalId,
          location_external_id: locationExternalId,
          quantity,
          note: note.trim() || null,
          purchased_on: purchasedOn || null,
          expires_on: expiresOn || null,
        });
      } else {
        await putToApi(
          `/api/households/${householdExternalId}/stock-lots/${initialValues.lotExternalId}`,
          {
            location_external_id: locationExternalId,
            quantity,
            note: note.trim() || null,
            purchased_on: purchasedOn || null,
            expires_on: expiresOn || null,
          },
        );
      }
      router.refresh();
      onClose();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not save this stock lot.");
    } finally {
      setPending(false);
    }
  }

  return (
    <ModalShell
      title={mode === "create" ? "Add another lot" : "Edit stock lot"}
      description={
        mode === "create"
          ? `Add another lot for ${initialValues.productName}.`
          : `Update this ${initialValues.productName} lot.`
      }
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
            <span>Storage location</span>
            <select
              value={locationExternalId}
              onChange={(event) => setLocationExternalId(event.target.value)}
              required
            >
              <option value="">Select a storage location</option>
              {locations.map((location) => (
                <option key={location.external_id} value={location.external_id}>
                  {location.location_group_name} / {location.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Purchased</span>
            <input
              type="date"
              value={purchasedOn}
              onChange={(event) => setPurchasedOn(event.target.value)}
            />
          </label>
          <label className="field">
            <span>Expires</span>
            <input
              type="date"
              value={expiresOn}
              onChange={(event) => setExpiresOn(event.target.value)}
            />
          </label>
        </div>
        <label className="field">
          <span>Note</span>
          <input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Optional note" />
        </label>
        {error ? <p className="error-text">{error}</p> : null}
        <div className="page-actions">
          <button type="submit" className="primary-button" disabled={pending}>
            {pending ? "Saving..." : mode === "create" ? "Add lot" : "Save changes"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}
