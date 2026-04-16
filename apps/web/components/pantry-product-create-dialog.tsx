"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type {
  PantryCatalogProductSummary,
  PantryEnrichmentPreviewResponse,
} from "../lib/api-types";
import { postToApi, putToApi } from "../lib/client-api";
import { BarcodeScannerDialog } from "./barcode-scanner-dialog";
import { ModalShell } from "./modal-shell";
import { PantryBarcodeField } from "./pantry-barcode-field";
import { ProductEnrichmentPreview } from "./product-enrichment-preview";
import { TextTagInput } from "./text-tag-input";

type PantryProductDialogProps = {
  householdExternalId: string;
  mode: "create" | "edit";
  initialValues: {
    externalId?: string;
    name: string;
    defaultUnit: string;
    aliases: string[];
    barcodes: string[];
    notes: string | null;
    manualIngredientTags: string[];
  };
  onCompleted?: (product: PantryCatalogProductSummary) => Promise<void> | void;
  onClose: () => void;
  title?: string;
  description?: string;
  submitLabel?: string;
  contextSummary?: {
    quantitySummary?: string | null;
    pantryLocationSummary?: string | null;
    note?: string | null;
  };
};

type FormState = {
  name: string;
  defaultUnit: string;
  aliasesInput: string;
  barcodesInput: string;
  notes: string;
  manualIngredientInput: string;
  manualIngredientTags: string[];
};

function createInitialState(
  initialValues: PantryProductDialogProps["initialValues"],
): FormState {
  return {
    name: initialValues.name,
    defaultUnit: initialValues.defaultUnit,
    aliasesInput: initialValues.aliases.join(", "),
    barcodesInput: initialValues.barcodes.join(", "),
    notes: initialValues.notes ?? "",
    manualIngredientInput: "",
    manualIngredientTags: initialValues.manualIngredientTags,
  };
}

function splitCommaSeparatedValues(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function primaryBarcode(value: string) {
  return splitCommaSeparatedValues(value)[0] ?? "";
}

function normalizeTagValue(value: string) {
  return value.trim();
}

export function PantryProductDialog({
  householdExternalId,
  mode,
  initialValues,
  onCompleted,
  onClose,
  title = mode === "create" ? "Create Pantro product" : "Edit Pantro product",
  description = mode === "create"
    ? "Create a Pantro product record with the full product fields before stock is reconciled."
    : "Update the saved product record without mixing in stock-lot fields.",
  submitLabel = mode === "create" ? "Create product" : "Save product",
  contextSummary,
}: PantryProductDialogProps) {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(createInitialState(initialValues));
  const [pending, setPending] = useState(false);
  const [lookupPending, setLookupPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lookupStatus, setLookupStatus] = useState<string | null>(null);
  const [lookupPreview, setLookupPreview] = useState<PantryEnrichmentPreviewResponse | null>(null);
  const [selectedEnrichmentSourceProductId, setSelectedEnrichmentSourceProductId] = useState<string | null>(null);
  const [isScannerOpen, setIsScannerOpen] = useState(false);
  const [lastBarcodeLookupValue, setLastBarcodeLookupValue] = useState(primaryBarcode(initialValues.barcodes.join(", ")));

  const selectedCandidate =
    lookupPreview?.candidates.find(
      (candidate) => candidate.source_product_id === selectedEnrichmentSourceProductId,
    ) ?? null;

  function resetEnrichmentPreview() {
    setLookupPreview(null);
    setLookupStatus(null);
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

  async function findProductDetails(source: "manual" | "blur" = "manual") {
    const candidateName = form.name.trim();
    const candidateBarcode = primaryBarcode(form.barcodesInput);
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

  async function handleSubmit() {
    setPending(true);
    setError(null);

    try {
      if (mode === "edit" && !initialValues.externalId) {
        throw new Error("This Pantro product is missing its identifier.");
      }
      const payload = {
        name: form.name,
        default_unit: form.defaultUnit,
        aliases: splitCommaSeparatedValues(form.aliasesInput),
        barcodes: splitCommaSeparatedValues(form.barcodesInput),
        notes: form.notes.trim() || null,
        manual_ingredient_tags: form.manualIngredientTags,
        confirmed_enrichment: selectedCandidate
          ? {
              source_name: selectedCandidate.source_name,
              source_product_id: selectedCandidate.source_product_id,
              match_status: selectedCandidate.match_status,
            }
          : null,
      };
      const product =
        mode === "create"
          ? await postToApi<PantryCatalogProductSummary>(
              `/api/households/${householdExternalId}/products`,
              payload,
            )
          : await putToApi<PantryCatalogProductSummary>(
              `/api/households/${householdExternalId}/products/${initialValues.externalId}`,
              payload,
            );
      router.refresh();
      await onCompleted?.(product);
      onClose();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not save this Pantro product.",
      );
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
          data-testid="pantry-product-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleSubmit();
          }}
        >
          {contextSummary ? (
            <section className="modal-form-section">
              <div className="inline-status-card">
                <strong>{form.name}</strong>
                {contextSummary.quantitySummary ? (
                  <p className="helper-text">Purchased: {contextSummary.quantitySummary}</p>
                ) : null}
                {contextSummary.pantryLocationSummary ? (
                  <p className="helper-text">Pantro location: {contextSummary.pantryLocationSummary}</p>
                ) : null}
                {contextSummary.note ? <p className="helper-text">Shopping note: {contextSummary.note}</p> : null}
              </div>
            </section>
          ) : null}

          <section className="modal-form-section">
            <div className="setup-card-toolbar">
              <div className="stack compact-stack">
                <h3 className="modal-section-title">Product details</h3>
                <p className="helper-text">
                  Product identity stays separate from stock-lot quantity, location, and expiry.
                </p>
              </div>
              {mode === "create" ? <span className="pill">New product</span> : null}
            </div>

            <div className="content-grid pantry-add-grid">
              <label className="field">
                <span>Product name</span>
                <input
                  name="name"
                  value={form.name}
                  onChange={(event) => {
                    resetEnrichmentPreview();
                    setForm((current) => ({ ...current, name: event.target.value }));
                  }}
                  placeholder="Beef mince"
                  required
                />
              </label>

              <label className="field">
                <span>Default unit</span>
                <input
                  name="default_unit"
                  value={form.defaultUnit}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, defaultUnit: event.target.value }))
                  }
                  placeholder="count"
                  required
                />
              </label>

              <PantryBarcodeField
                inputName="barcodes"
                value={form.barcodesInput}
                onChange={(value) => {
                  resetEnrichmentPreview();
                  setForm((current) => ({ ...current, barcodesInput: value }));
                }}
                onBlur={() => {
                  const primaryBarcodeValue = primaryBarcode(form.barcodesInput);
                  if (primaryBarcodeValue && primaryBarcodeValue !== lastBarcodeLookupValue) {
                    void findProductDetails("blur");
                  }
                }}
                onSubmitValue={() => {
                  if (primaryBarcode(form.barcodesInput)) {
                    void findProductDetails("manual");
                  }
                }}
                onLookup={() => void findProductDetails("manual")}
                onScan={() => setIsScannerOpen(true)}
                lookupPending={lookupPending}
                lookupDisabled={!form.name.trim() && !primaryBarcode(form.barcodesInput)}
                helperText="Use the first barcode for Open Food Facts lookup. Camera scanning works only when the browser supports it over HTTPS or localhost. Extra barcodes can be added as comma-separated values."
              />

              <label className="field">
                <span>Aliases</span>
                <input
                  name="aliases"
                  value={form.aliasesInput}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, aliasesInput: event.target.value }))
                  }
                  placeholder="Ground beef, minced beef"
                />
              </label>
            </div>

            <p className="helper-text">
              Aliases and extra barcodes accept either <code>value,value</code> or <code>value, value</code>.
            </p>

            <label className="field">
              <span>Product notes</span>
              <textarea
                name="notes"
                rows={4}
                value={form.notes}
                onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                placeholder="Storage guidance, substitutions, or family-specific notes"
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
              helperText="Manual ingredient tags stay alongside any imported enrichment."
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

          {error ? <p className="error-text">{error}</p> : null}

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
            resetEnrichmentPreview();
            setForm((current) => ({
              ...current,
              barcodesInput: current.barcodesInput.trim()
                ? `${barcode}, ${current.barcodesInput}`
                : barcode,
            }));
            setLastBarcodeLookupValue("");
            setIsScannerOpen(false);
          }}
        />
      ) : null}
    </>
  );
}
