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
import { BarcodeScannerDialog } from "./barcode-scanner-dialog";
import { ModalShell } from "./modal-shell";
import { ProductEnrichmentPreview } from "./product-enrichment-preview";
import { TextTagInput } from "./text-tag-input";

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
  manualIngredientInput: string;
  manualIngredientTags: string[];
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
  manualIngredientInput: "",
  manualIngredientTags: [],
};

function splitAliases(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeTagValue(value: string) {
  return value.trim();
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
  const [isScannerOpen, setIsScannerOpen] = useState(false);

  const selectedCandidate =
    lookupPreview?.candidates.find(
      (candidate) => candidate.source_product_id === selectedEnrichmentSourceProductId,
    ) ?? null;

  function resetEnrichmentPreview() {
    setLookupPreview(null);
    setSelectedEnrichmentSourceProductId(null);
  }

  function addManualIngredient(value: string) {
    const nextTag = normalizeTagValue(value);
    if (!nextTag) {
      return;
    }
    setForm((current) => ({
      ...current,
      manualIngredientInput: "",
      manualIngredientTags: Array.from(new Set([...current.manualIngredientTags, nextTag])),
    }));
  }

  function removeManualIngredient(value: string) {
    setForm((current) => ({
      ...current,
      manualIngredientTags: current.manualIngredientTags.filter((item) => item !== value),
    }));
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
          manual_ingredient_tags: form.manualIngredientTags,
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
    <>
      <ModalShell
        title="Add to pantry"
        description="Create a product and its first stock lot in one pass, or route straight into adding another lot when the product already exists."
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
          <section className="modal-form-section">
            <div className="stack compact-stack">
              <h3 className="modal-section-title">Product identity</h3>
              <p className="helper-text">
                Pantry keeps the product name, aliases, and manual ingredient tags user-owned even
                if you attach Open Food Facts enrichment.
              </p>
            </div>
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
                <div className="inline-action-field">
                  <input
                    name="barcode"
                    value={form.barcode}
                    onChange={(event) => {
                      resetEnrichmentPreview();
                      setMatchedProduct(null);
                      setForm((current) => ({ ...current, barcode: event.target.value }));
                    }}
                    placeholder="5000111046244"
                  />
                  <button
                    type="button"
                    className="ghost-button compact-button"
                    onClick={() => setIsScannerOpen(true)}
                  >
                    Scan
                  </button>
                </div>
                <p className="helper-text">
                  USB barcode scanners can type directly into this field. Camera scanning opens only
                  when the browser supports it.
                </p>
              </label>

              <label className="field">
                <span>Aliases</span>
                <input
                  name="aliases"
                  value={form.aliases}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, aliases: event.target.value }))
                  }
                  placeholder="Ground beef, minced beef"
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

            <TextTagInput
              label="Manual ingredients"
              tags={form.manualIngredientTags}
              newValue={form.manualIngredientInput}
              onNewValueChange={(value) =>
                setForm((current) => ({ ...current, manualIngredientInput: value }))
              }
              onAddTag={addManualIngredient}
              onRemoveTag={removeManualIngredient}
              placeholder="Add an ingredient such as Beef"
              inputName="manual_ingredient"
              helperText="Manual ingredient tags stay alongside Open Food Facts ingredient enrichment so Pantry can keep both user-entered context and imported detail."
            />
          </section>

          <section className="modal-form-section">
            <div className="setup-card-toolbar">
              <div className="stack compact-stack">
                <h3 className="modal-section-title">Open Food Facts enrichment</h3>
                <p className="helper-text">
                  Optional enrichment adds ingredients, allergens, dietary tags, nutrition, and an
                  image URL without replacing Pantry’s product identity.
                </p>
              </div>
              <div className="page-actions">
                <button
                  type="button"
                  className="ghost-button"
                  disabled={lookupPending || (!form.name.trim() && !form.barcode.trim())}
                  onClick={() => void findProductDetails()}
                >
                  {lookupPending ? "Looking up..." : "Look up OFF details"}
                </button>
                {lookupPreview ? (
                  <button type="button" className="ghost-button" onClick={resetEnrichmentPreview}>
                    Clear preview
                  </button>
                ) : null}
              </div>
            </div>

            {lookupPreview ? (
              <ProductEnrichmentPreview
                preview={lookupPreview}
                selectedSourceProductId={selectedEnrichmentSourceProductId}
                onSelect={setSelectedEnrichmentSourceProductId}
                onClearSelection={() => setSelectedEnrichmentSourceProductId(null)}
              />
            ) : (
              <div className="info-callout">
                <strong>Lookup stays optional</strong>
                <p>
                  You can save the product and stock lot without any external enrichment if the
                  product is homemade, local, or not present in Open Food Facts.
                </p>
              </div>
            )}
          </section>

          <section className="modal-form-section">
            <div className="stack compact-stack">
              <h3 className="modal-section-title">Stock lot details</h3>
              <p className="helper-text">
                Add the first quantity now, or let Pantry route this straight into another lot on
                an existing product.
              </p>
            </div>
            <div className="split-fields">
              <label className="field">
                <span>Quantity</span>
                <input
                  name="quantity"
                  type="number"
                  min="0.001"
                  step="0.001"
                  value={form.quantity}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, quantity: event.target.value }))
                  }
                  required
                />
              </label>
              <label className="field">
                <span>Unit</span>
                <input
                  name="unit"
                  list="pantry-unit-options"
                  value={form.unit}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, unit: event.target.value }))
                  }
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
                  onChange={(event) =>
                    setForm((current) => ({ ...current, expiresOn: event.target.value }))
                  }
                />
              </label>
            </div>

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
          </section>

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
                Pantry matched this product already. Saving now will add another stock lot to the
                existing record and preserve its current product identity.
              </p>
              <p>Saved unit: {matchedProduct.default_unit}.</p>
              {matchedProduct.aliases.length > 0 ? (
                <p>Known aliases: {matchedProduct.aliases.join(", ")}.</p>
              ) : null}
            </div>
          ) : null}

          {selectedCandidate ? (
            <div className="info-callout">
              <strong>Enrichment will be linked on save</strong>
              <p>
                Pantry will keep its own product name, aliases, and manual ingredients while
                storing the selected Open Food Facts record as optional advisory enrichment.
              </p>
            </div>
          ) : null}

          {error ? <p className="error-text">{error}</p> : null}
          {statusMessage ? <p className="status-note">{statusMessage}</p> : null}

          <div className="page-actions">
            <button
              type="submit"
              className="primary-button"
              disabled={pending || locations.length === 0}
            >
              {pending
                ? "Saving..."
                : matchedProduct
                  ? "Add stock lot to existing product"
                  : "Create product and stock lot"}
            </button>
          </div>
        </form>

        <datalist id="pantry-unit-options">
          {UNIT_OPTIONS.map((unit) => (
            <option key={unit} value={unit} />
          ))}
        </datalist>
      </ModalShell>

      {isScannerOpen ? (
        <BarcodeScannerDialog
          onDetected={(value) => {
            resetEnrichmentPreview();
            setMatchedProduct(null);
            setForm((current) => ({ ...current, barcode: value }));
          }}
          onClose={() => setIsScannerOpen(false)}
        />
      ) : null}
    </>
  );
}
