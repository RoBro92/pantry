"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type {
  PantryEnrichmentPreviewResponse,
  PantryEntryMutationResponse,
  PantryLocationSummary,
  PantryProductMatchSummary,
} from "../lib/api-types";
import { postToApi } from "../lib/client-api";
import { ModalShell } from "./modal-shell";
import { ProductEnrichmentPreview } from "./product-enrichment-preview";

type PantryAddEntryDialogProps = {
  householdExternalId: string;
  canAdminister: boolean;
  locations: PantryLocationSummary[];
  onClose: () => void;
};

type FormState = {
  name: string;
  barcode: string;
  quantity: string;
  unit: string;
  locationExternalId: string;
  aliases: string;
  purchasedOn: string;
  expiresOn: string;
  note: string;
};

const UNIT_OPTIONS = ["g", "kg", "oz", "lb", "ml", "l", "count", "pack", "bottle", "jar", "can"];

const EMPTY_FORM: FormState = {
  name: "",
  barcode: "",
  quantity: "",
  unit: "count",
  locationExternalId: "",
  aliases: "",
  purchasedOn: "",
  expiresOn: "",
  note: "",
};

function splitAliases(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function PantryAddEntryDialog({
  householdExternalId,
  canAdminister,
  locations,
  onClose,
}: PantryAddEntryDialogProps) {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [matchedProduct, setMatchedProduct] = useState<PantryProductMatchSummary | null>(null);
  const [lookupPending, setLookupPending] = useState(false);
  const [lookupPreview, setLookupPreview] = useState<PantryEnrichmentPreviewResponse | null>(null);
  const [selectedEnrichmentSourceProductId, setSelectedEnrichmentSourceProductId] = useState<string | null>(null);

  const selectedCandidate =
    lookupPreview?.candidates.find(
      (candidate) => candidate.source_product_id === selectedEnrichmentSourceProductId,
    ) ?? null;

  function resetEnrichmentPreview() {
    setLookupPreview(null);
    setSelectedEnrichmentSourceProductId(null);
  }

  async function findProductDetails() {
    setLookupPending(true);
    setError(null);
    setStatusMessage(null);

    try {
      const response = await postToApi<PantryEnrichmentPreviewResponse>(
        `/api/households/${householdExternalId}/pantry/enrichment/preview`,
        {
          product_name: form.name,
          barcode: form.barcode.trim() || null,
        },
      );
      setLookupPreview(response);
      setSelectedEnrichmentSourceProductId(null);
    } catch (requestError) {
      setLookupPreview(null);
      setSelectedEnrichmentSourceProductId(null);
      setError(
        requestError instanceof Error ? requestError.message : "Could not look up product details.",
      );
    } finally {
      setLookupPending(false);
    }
  }

  async function submit(existingProductExternalId?: string) {
    setPending(true);
    setError(null);
    setStatusMessage(null);

    try {
      const response = await postToApi<PantryEntryMutationResponse>(
        `/api/households/${householdExternalId}/pantry/entries`,
        {
          name: form.name,
          quantity: form.quantity,
          unit: form.unit,
          location_external_id: form.locationExternalId,
          barcode: form.barcode.trim() || null,
          aliases: splitAliases(form.aliases),
          purchased_on: form.purchasedOn || null,
          expires_on: form.expiresOn || null,
          note: form.note.trim() || null,
          existing_product_external_id: existingProductExternalId ?? null,
          confirmed_enrichment: selectedCandidate
            ? {
                source_name: selectedCandidate.source_name,
                source_product_id: selectedCandidate.source_product_id,
                match_status: selectedCandidate.match_status,
              }
            : null,
        },
      );

      if (response.status === "existing_product" && response.matched_product) {
        setMatchedProduct(response.matched_product);
        setStatusMessage(response.message);
        if (response.matched_product.default_unit !== form.unit) {
          setForm((current) => ({ ...current, unit: response.matched_product!.default_unit }));
        }
        return;
      }

      if (response.status === "alias_conflict") {
        setMatchedProduct(null);
        setError(
          response.alias_conflicts.length > 0
            ? response.alias_conflicts
                .map((conflict) => `${conflict.alias} is already used by ${conflict.product_name}`)
                .join(". ")
            : response.message,
        );
        return;
      }

      if (response.status === "creation_not_allowed") {
        setMatchedProduct(null);
        setError(response.message);
        return;
      }

      setMatchedProduct(null);
      setStatusMessage(response.message);
      setForm(EMPTY_FORM);
      resetEnrichmentPreview();
      router.refresh();
      window.setTimeout(() => onClose(), 350);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not save pantry item.");
    } finally {
      setPending(false);
    }
  }

  return (
    <ModalShell
      title="Add to pantry"
      description="Create a product and its first stock lot in one flow, or add another lot to an existing product."
      onClose={onClose}
      closeOnBackdropClick={false}
    >
      <form
        className="stack"
        data-testid="pantry-add-entry-form"
        onSubmit={(event) => {
          event.preventDefault();
          void submit(matchedProduct?.external_id ?? undefined);
        }}
      >
        <div className="content-grid">
          <label className="field">
            <span>Product name</span>
            <input
              name="name"
              value={form.name}
              onChange={(event) => {
                setMatchedProduct(null);
                resetEnrichmentPreview();
                setForm((current) => ({ ...current, name: event.target.value }));
              }}
              placeholder="Beef mince"
              required
            />
          </label>
          <label className="field">
            <span>Barcode</span>
            <input
              name="barcode"
              value={form.barcode}
              onChange={(event) => {
                resetEnrichmentPreview();
                setForm((current) => ({ ...current, barcode: event.target.value }));
              }}
              placeholder="5000111046244"
            />
          </label>
          <label className="field">
            <span>Storage location</span>
            <select
              name="location_external_id"
              value={form.locationExternalId}
              onChange={(event) =>
                setForm((current) => ({ ...current, locationExternalId: event.target.value }))
              }
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
        </div>

        <div className="page-actions">
          <button
            type="button"
            className="ghost-button"
            disabled={lookupPending || (!form.name.trim() && !form.barcode.trim())}
            onClick={() => void findProductDetails()}
          >
            {lookupPending ? "Finding details..." : "Find product details"}
          </button>
          {lookupPreview ? (
            <button type="button" className="ghost-button" onClick={resetEnrichmentPreview}>
              Clear preview
            </button>
          ) : null}
        </div>

        {lookupPreview ? (
          <ProductEnrichmentPreview
            preview={lookupPreview}
            selectedSourceProductId={selectedEnrichmentSourceProductId}
            onSelect={setSelectedEnrichmentSourceProductId}
            onClearSelection={() => setSelectedEnrichmentSourceProductId(null)}
          />
        ) : null}

        <div className="split-fields">
          <label className="field">
            <span>Quantity</span>
            <input
              name="quantity"
              type="number"
              min="0.001"
              step="0.001"
              value={form.quantity}
              onChange={(event) => setForm((current) => ({ ...current, quantity: event.target.value }))}
              required
            />
          </label>
          <label className="field">
            <span>Unit</span>
            <input
              name="unit"
              list="pantry-unit-options"
              value={form.unit}
              onChange={(event) => setForm((current) => ({ ...current, unit: event.target.value }))}
              placeholder="g"
              required
            />
          </label>
          <label className="field">
            <span>Purchase date</span>
            <input
              name="purchased_on"
              type="date"
              value={form.purchasedOn}
              onChange={(event) =>
                setForm((current) => ({ ...current, purchasedOn: event.target.value }))
              }
            />
          </label>
          <label className="field">
            <span>Expiry date</span>
            <input
              name="expires_on"
              type="date"
              value={form.expiresOn}
              onChange={(event) => setForm((current) => ({ ...current, expiresOn: event.target.value }))}
            />
          </label>
        </div>

        <label className="field">
          <span>Aliases</span>
          <input
            name="aliases"
            value={form.aliases}
            onChange={(event) => setForm((current) => ({ ...current, aliases: event.target.value }))}
            placeholder="Ground beef, minced beef"
          />
        </label>

        <label className="field">
          <span>Notes</span>
          <textarea
            name="note"
            rows={3}
            value={form.note}
            onChange={(event) => setForm((current) => ({ ...current, note: event.target.value }))}
            placeholder="Family pack from the market"
          />
        </label>

        {!canAdminister ? (
          <div className="info-callout">
            <strong>Household-admin creation only</strong>
            <p>
              You can add stock to existing products, but creating a brand new product still
              requires the Household Admin role.
            </p>
          </div>
        ) : null}

        {matchedProduct ? (
          <div className="info-callout" data-testid="existing-product-warning">
            <strong>{matchedProduct.name} already exists</strong>
            <p>
              Pantry found an existing product and will add another stock lot to it. Saved unit:{" "}
              {matchedProduct.default_unit}.
            </p>
            {matchedProduct.aliases.length > 0 ? (
              <p>Known aliases: {matchedProduct.aliases.join(", ")}.</p>
            ) : null}
          </div>
        ) : null}

        {selectedCandidate ? (
          <div className="info-callout">
            <strong>Enrichment will be linked on save</strong>
            <p>
              Pantry will keep its own product name and unit, and store these Open Food Facts
              details as optional advisory metadata.
            </p>
          </div>
        ) : null}

        {error ? <p className="error-text">{error}</p> : null}
        {statusMessage ? <p className="status-note">{statusMessage}</p> : null}

        <div className="page-actions">
          <button type="submit" className="primary-button" disabled={pending || locations.length === 0}>
            {pending
              ? "Saving..."
              : matchedProduct
                ? "Add stock lot to existing product"
                : "Save pantry item"}
          </button>
        </div>
      </form>

      <datalist id="pantry-unit-options">
        {UNIT_OPTIONS.map((unit) => (
          <option key={unit} value={unit} />
        ))}
      </datalist>
    </ModalShell>
  );
}
