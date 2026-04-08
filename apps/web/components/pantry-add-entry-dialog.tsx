"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type {
  PantryDuplicateCheckResponse,
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
  title?: string;
  description?: string;
  submitLabel?: string;
  initialValues?: Partial<FormState>;
  onCompleted?: (response: PantryEntryMutationResponse) => Promise<void> | void;
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

type DuplicateDecision = "existing" | "separate" | null;

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

function createInitialForm(initialValues?: Partial<FormState>): FormState {
  return {
    ...EMPTY_FORM,
    ...initialValues,
    manualIngredientTags: initialValues?.manualIngredientTags ?? [],
  };
}

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
  title = "Add to pantry",
  description = "Create a product and its first stock lot in one compact flow, with duplicate detection before you commit.",
  submitLabel = "Add to pantry",
  initialValues,
  onCompleted,
}: PantryAddEntryDialogProps) {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(createInitialForm(initialValues));
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [matchedProduct, setMatchedProduct] = useState<PantryProductMatchSummary | null>(null);
  const [duplicateDecision, setDuplicateDecision] = useState<DuplicateDecision>(null);
  const [lookupPending, setLookupPending] = useState(false);
  const [duplicateCheckPending, setDuplicateCheckPending] = useState(false);
  const [lookupPreview, setLookupPreview] = useState<PantryEnrichmentPreviewResponse | null>(null);
  const [lookupStatus, setLookupStatus] = useState<string | null>(null);
  const [selectedEnrichmentSourceProductId, setSelectedEnrichmentSourceProductId] = useState<string | null>(null);
  const [isScannerOpen, setIsScannerOpen] = useState(false);
  const [lastBarcodeLookupValue, setLastBarcodeLookupValue] = useState("");

  const selectedCandidate =
    lookupPreview?.candidates.find(
      (candidate) => candidate.source_product_id === selectedEnrichmentSourceProductId,
    ) ?? null;

  function resetEnrichmentPreview() {
    setLookupPreview(null);
    setLookupStatus(null);
    setSelectedEnrichmentSourceProductId(null);
  }

  function clearDuplicateState() {
    setMatchedProduct(null);
    setDuplicateDecision(null);
  }

  function applyDuplicateResult(response: PantryDuplicateCheckResponse) {
    setMatchedProduct(response.matched_product);
    setDuplicateDecision(
      response.matched_product
        ? response.can_keep_separate_product
          ? "existing"
          : "existing"
        : null,
    );
    setStatusMessage(response.matched_product ? response.message : null);
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

  async function runDuplicateCheck() {
    const candidateName = form.name.trim();
    const candidateBarcode = form.barcode.trim();
    if (!candidateName && !candidateBarcode) {
      clearDuplicateState();
      return;
    }

    setDuplicateCheckPending(true);
    try {
      const response = await postToApi<PantryDuplicateCheckResponse>(
        `/api/households/${householdExternalId}/pantry/entries/duplicate-check`,
        {
          name: candidateName || null,
          barcode: candidateBarcode || null,
        },
      );
      applyDuplicateResult(response);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not check for duplicates.",
      );
    } finally {
      setDuplicateCheckPending(false);
    }
  }

  async function findProductDetails(source: "manual" | "blur" = "manual") {
    const candidateName = form.name.trim();
    const candidateBarcode = form.barcode.trim();
    if (!candidateName && !candidateBarcode) {
      return;
    }

    setLookupPending(true);
    setError(null);

    try {
      const response = await postToApi<PantryEnrichmentPreviewResponse>(
        `/api/households/${householdExternalId}/pantry/enrichment/preview`,
        {
          product_name: candidateName,
          barcode: candidateBarcode || null,
        },
      );
      setLookupPreview(response);
      setSelectedEnrichmentSourceProductId(null);
      if (response.candidates.length > 0) {
        setLookupStatus(response.message);
      } else if (response.status === "no_match" && candidateBarcode) {
        setLookupStatus("No Open Food Facts result found.");
      } else {
        setLookupStatus(response.message);
      }
      if (source === "blur") {
        setLastBarcodeLookupValue(candidateBarcode);
      }
    } catch (requestError) {
      setLookupPreview(null);
      setSelectedEnrichmentSourceProductId(null);
      setLookupStatus(null);
      setError(
        requestError instanceof Error ? requestError.message : "Could not look up product details.",
      );
    } finally {
      setLookupPending(false);
    }
  }

  async function handleSuccessfulMutation(response: PantryEntryMutationResponse) {
    clearDuplicateState();
    setStatusMessage(response.message);
    setForm(createInitialForm(initialValues));
    resetEnrichmentPreview();
    router.refresh();
    await onCompleted?.(response);
    window.setTimeout(() => onClose(), 250);
  }

  async function submit() {
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
          existing_product_external_id:
            matchedProduct && duplicateDecision !== "separate"
              ? matchedProduct.external_id
              : null,
          allow_separate_product:
            Boolean(matchedProduct?.can_keep_separate_product) &&
            duplicateDecision === "separate",
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
        setDuplicateDecision(
          response.can_keep_separate_product ? "existing" : "existing",
        );
        setStatusMessage(response.message);
        if (response.matched_product.default_unit !== form.unit) {
          setForm((current) => ({ ...current, unit: response.matched_product!.default_unit }));
        }
        return;
      }

      if (response.status === "alias_conflict") {
        clearDuplicateState();
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
        clearDuplicateState();
        setError(response.message);
        return;
      }

      await handleSuccessfulMutation(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not save pantry item.");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <ModalShell
        title={title}
        description={description}
        onClose={onClose}
        closeOnBackdropClick={false}
        panelClassName="modal-panel modal-panel-wide"
      >
        <form
          className="stack pantry-add-form"
          data-testid="pantry-add-entry-form"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <section className="modal-form-section">
            <div className="setup-card-toolbar">
              <div className="stack compact-stack">
                <h3 className="modal-section-title">Product and lot</h3>
                <p className="helper-text">
                  Keep the product identity user-owned, then attach optional enrichment only if it
                  helps.
                </p>
              </div>
              <span className="pill">
                {duplicateCheckPending ? "Checking duplicates..." : "Duplicate-aware"}
              </span>
            </div>

            <div className="content-grid pantry-add-grid">
              <label className="field">
                <span>Product name</span>
                <input
                  name="name"
                  value={form.name}
                  onChange={(event) => {
                    clearDuplicateState();
                    resetEnrichmentPreview();
                    setForm((current) => ({ ...current, name: event.target.value }));
                  }}
                  onBlur={() => void runDuplicateCheck()}
                  placeholder="Beef mince"
                  required
                />
              </label>

              <label className="field">
                <span>Barcode</span>
                <div className="inline-action-field is-multi-action">
                  <input
                    name="barcode"
                    value={form.barcode}
                    onChange={(event) => {
                      clearDuplicateState();
                      resetEnrichmentPreview();
                      setForm((current) => ({ ...current, barcode: event.target.value }));
                    }}
                    onBlur={() => {
                      const trimmedBarcode = form.barcode.trim();
                      void runDuplicateCheck();
                      if (trimmedBarcode && trimmedBarcode !== lastBarcodeLookupValue) {
                        void findProductDetails("blur");
                      }
                    }}
                    placeholder="5000111046244"
                  />
                  <button
                    type="button"
                    className="ghost-button compact-button"
                    disabled={lookupPending || (!form.name.trim() && !form.barcode.trim())}
                    onClick={() => void findProductDetails("manual")}
                  >
                    {lookupPending ? "Looking up..." : "Look up"}
                  </button>
                  <button
                    type="button"
                    className="ghost-button compact-button"
                    onClick={() => setIsScannerOpen(true)}
                  >
                    Scan
                  </button>
                  <details className="inline-help-details">
                    <summary>?</summary>
                    <p className="helper-text">
                      USB scanners can type directly into this field. Pantry also tries an Open Food
                      Facts lookup when you leave the field.
                    </p>
                  </details>
                </div>
              </label>

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
                  placeholder="1"
                  required
                />
              </label>

              <label className="field">
                <span>Unit</span>
                <select
                  name="unit"
                  value={form.unit}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, unit: event.target.value }))
                  }
                >
                  {UNIT_OPTIONS.map((unitOption) => (
                    <option key={unitOption} value={unitOption}>
                      {unitOption}
                    </option>
                  ))}
                </select>
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
                <span>Purchased</span>
                <input
                  type="date"
                  name="purchased_on"
                  value={form.purchasedOn}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, purchasedOn: event.target.value }))
                  }
                />
              </label>

              <label className="field">
                <span>Expires</span>
                <input
                  type="date"
                  name="expires_on"
                  value={form.expiresOn}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, expiresOn: event.target.value }))
                  }
                />
              </label>
            </div>

            <p className="helper-text">
              Aliases accept either <code>ingredient,ingredient</code> or <code>ingredient, ingredient</code>.
            </p>

            <label className="field">
              <span>Note</span>
              <input
                name="note"
                value={form.note}
                onChange={(event) =>
                  setForm((current) => ({ ...current, note: event.target.value }))
                }
                placeholder="Family pack"
              />
            </label>

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
              helperText="Use commas or spaced commas for aliases. Manual ingredient tags stay alongside any imported enrichment."
            />
          </section>

          {lookupStatus || lookupPreview || selectedCandidate ? (
            <section className="modal-form-section">
              <div className="inline-status-card">
                <div className="stack compact-stack">
                  <strong>Open Food Facts</strong>
                  <p className="helper-text">
                    {selectedCandidate
                      ? `${selectedCandidate.source_product_name ?? "Selected match"} will be linked on save.`
                      : lookupStatus ?? "Optional enrichment is ready if you want it."}
                  </p>
                </div>
                <div className="page-actions">
                  {lookupPreview?.candidates.length ? (
                    <details className="compact-disclosure">
                      <summary>
                        Review {lookupPreview.candidates.length} match
                        {lookupPreview.candidates.length === 1 ? "" : "es"}
                      </summary>
                      <div className="compact-disclosure-body">
                        <ProductEnrichmentPreview
                          preview={lookupPreview}
                          selectedSourceProductId={selectedEnrichmentSourceProductId}
                          onSelect={setSelectedEnrichmentSourceProductId}
                          onClearSelection={() => setSelectedEnrichmentSourceProductId(null)}
                        />
                      </div>
                    </details>
                  ) : null}
                  {(lookupPreview || lookupStatus || selectedCandidate) && !lookupPending ? (
                    <button type="button" className="ghost-button compact-button" onClick={resetEnrichmentPreview}>
                      Clear
                    </button>
                  ) : null}
                </div>
              </div>
            </section>
          ) : null}

          {matchedProduct ? (
            <section className="modal-form-section">
              <div className="inline-status-card is-warning">
                <div className="stack compact-stack">
                  <strong>{matchedProduct.name} already looks like the right product</strong>
                  <p className="helper-text">
                    {matchedProduct.match_reason === "barcode_exact"
                      ? "This barcode already belongs to that product, so Pantry will route this lot there."
                      : matchedProduct.match_reason === "name_similarity"
                        ? "Pantry found a likely existing product before you add this lot."
                        : "Pantry found an existing product with the same identity."}
                  </p>
                </div>
                <div className="duplicate-choice-row">
                  <button
                    type="button"
                    className={
                      duplicateDecision === "existing"
                        ? "primary-button compact-button"
                        : "ghost-button compact-button"
                    }
                    onClick={() => setDuplicateDecision("existing")}
                  >
                    Add lot to existing product
                  </button>
                  {matchedProduct.can_keep_separate_product ? (
                    <button
                      type="button"
                      className={
                        duplicateDecision === "separate"
                          ? "primary-button compact-button"
                          : "ghost-button compact-button"
                      }
                      onClick={() => setDuplicateDecision("separate")}
                    >
                      Keep as separate product
                    </button>
                  ) : null}
                </div>
              </div>
            </section>
          ) : null}

          {error ? <p className="error-text">{error}</p> : null}
          {statusMessage ? <p className="status-note">{statusMessage}</p> : null}

          <div className="page-actions">
            <button type="submit" className="primary-button" disabled={pending}>
              {pending ? "Saving..." : submitLabel}
            </button>
          </div>
        </form>
      </ModalShell>

      {isScannerOpen ? (
        <BarcodeScannerDialog
          onClose={() => setIsScannerOpen(false)}
          onDetected={(barcode) => {
            clearDuplicateState();
            resetEnrichmentPreview();
            setForm((current) => ({ ...current, barcode }));
            setLastBarcodeLookupValue("");
            setIsScannerOpen(false);
          }}
        />
      ) : null}
    </>
  );
}
