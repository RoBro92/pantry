"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
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
import { PantryBarcodeField } from "./pantry-barcode-field";
import { ProductEnrichmentPreview } from "./product-enrichment-preview";
import { TextTagInput } from "./text-tag-input";

type PantryAddEntryDialogProps = {
  householdExternalId: string;
  canAdminister: boolean;
  locations: PantryLocationSummary[];
  onClose: () => void;
  entryMode?: "manual" | "scan";
  title?: string;
  description?: string;
  submitLabel?: string;
  initialValues?: Partial<FormState>;
  onCompleted?: (response: PantryEntryMutationResponse) => Promise<void> | void;
};

type FormState = {
  name: string;
  barcodesInput: string;
  quantity: string;
  unit: string;
  locationExternalId: string;
  aliases: string;
  purchasedOn: string;
  expiresOn: string;
  productNotes: string;
  lotNote: string;
  manualIngredientInput: string;
  manualIngredientTags: string[];
};

type DuplicateDecision = "existing" | "separate" | null;

const UNIT_OPTIONS = ["g", "kg", "oz", "lb", "ml", "l", "count", "pack", "bottle", "jar", "can"];

const EMPTY_FORM: FormState = {
  name: "",
  barcodesInput: "",
  quantity: "",
  unit: "count",
  locationExternalId: "",
  aliases: "",
  purchasedOn: "",
  expiresOn: "",
  productNotes: "",
  lotNote: "",
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

function splitBarcodes(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function getPrimaryBarcode(value: string) {
  return splitBarcodes(value)[0] ?? "";
}

function normalizeTagValue(value: string) {
  return value.trim();
}

export function PantryAddEntryDialog({
  householdExternalId,
  canAdminister: _canAdminister,
  locations,
  onClose,
  entryMode = "manual",
  title = entryMode === "scan" ? "Scan to add" : "Add manually",
  description =
    entryMode === "scan"
      ? "Capture the barcode first, save the essentials, and keep optional detail behind secondary sections."
      : "Create a pantry item with only the fields the household needs up front. Optional notes and enrichment stay secondary.",
  submitLabel = "Add to inventory",
  initialValues,
  onCompleted,
}: PantryAddEntryDialogProps) {
  const router = useRouter();
  const initialForm = createInitialForm(initialValues);
  const [form, setForm] = useState<FormState>(initialForm);
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
  const [isInlineScannerOpen, setIsInlineScannerOpen] = useState(
    entryMode === "scan" && !getPrimaryBarcode(initialForm.barcodesInput),
  );
  const [showOptionalDetails, setShowOptionalDetails] = useState(entryMode === "manual");
  const duplicateCheckRequestIdRef = useRef(0);
  const lastBarcodeLookupValueRef = useRef("");

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

  async function runDuplicateCheck(overrides?: {
    name?: string;
    barcodesInput?: string;
  }) {
    const candidateName = (overrides?.name ?? form.name).trim();
    const candidateBarcode = getPrimaryBarcode(overrides?.barcodesInput ?? form.barcodesInput);
    const requestId = duplicateCheckRequestIdRef.current + 1;
    duplicateCheckRequestIdRef.current = requestId;

    if (!candidateName && !candidateBarcode) {
      clearDuplicateState();
      setDuplicateCheckPending(false);
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
      if (duplicateCheckRequestIdRef.current !== requestId) {
        return;
      }
      applyDuplicateResult(response);
    } catch (requestError) {
      if (duplicateCheckRequestIdRef.current !== requestId) {
        return;
      }
      setError(
        requestError instanceof Error ? requestError.message : "Could not check for duplicates.",
      );
    } finally {
      if (duplicateCheckRequestIdRef.current === requestId) {
        setDuplicateCheckPending(false);
      }
    }
  }

  async function findProductDetails(
    source: "manual" | "blur" = "manual",
    overrides?: {
      name?: string;
      barcodesInput?: string;
    },
  ) {
    const candidateName = (overrides?.name ?? form.name).trim();
    const candidateBarcode = getPrimaryBarcode(overrides?.barcodesInput ?? form.barcodesInput);
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

      if (!candidateName) {
        const suggestedName = response.candidates[0]?.source_product_name?.trim() ?? "";
        if (suggestedName) {
          setForm((current) => ({ ...current, name: current.name.trim() ? current.name : suggestedName }));
        }
      }

      if (response.candidates.length > 0) {
        setLookupStatus(response.message);
      } else if (response.status === "no_match" && candidateBarcode) {
        setLookupStatus("No Open Food Facts result found.");
      } else {
        setLookupStatus(response.message);
      }

      if (source === "blur") {
        lastBarcodeLookupValueRef.current = candidateBarcode;
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
    setIsInlineScannerOpen(entryMode === "scan");
    setShowOptionalDetails(entryMode === "manual");
    lastBarcodeLookupValueRef.current = "";
    router.refresh();
    await onCompleted?.(response);
    window.setTimeout(() => onClose(), 250);
  }

  async function submit() {
    duplicateCheckRequestIdRef.current += 1;
    setDuplicateCheckPending(false);
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
          barcode: getPrimaryBarcode(form.barcodesInput) || null,
          aliases: splitAliases(form.aliases),
          product_notes: form.productNotes.trim() || null,
          manual_ingredient_tags: form.manualIngredientTags,
          purchased_on: form.purchasedOn || null,
          expires_on: form.expiresOn || null,
          note: form.lotNote.trim() || null,
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
        setDuplicateDecision(response.can_keep_separate_product ? "existing" : "existing");
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

  function handleDetectedBarcode(barcode: string, mode: "inline" | "dialog") {
    clearDuplicateState();
    resetEnrichmentPreview();
    setStatusMessage(null);

    const nextBarcodeInput =
      mode === "dialog" && form.barcodesInput.trim()
        ? `${barcode}, ${form.barcodesInput}`
        : barcode;

    setForm((current) => ({
      ...current,
      barcodesInput: nextBarcodeInput,
    }));
    lastBarcodeLookupValueRef.current = "";
    void runDuplicateCheck({ name: form.name, barcodesInput: nextBarcodeInput });
    void findProductDetails("manual", { name: form.name, barcodesInput: nextBarcodeInput });
  }

  return (
    <>
      <ModalShell
        title={title}
        description={description}
        onClose={onClose}
        closeOnBackdropClick={false}
        panelClassName="modal-panel modal-panel-wide modal-panel-mobile-shell"
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
                <h3 className="modal-section-title">
                  {entryMode === "scan" ? "Scan-first household add" : "Manual household add"}
                </h3>
                <p className="helper-text">
                  {entryMode === "scan"
                    ? "Keep the first step to barcode, name, quantity, and storage. Optional enrichment and notes stay secondary."
                    : "Start with the essentials. Dates, aliases, enrichment, and notes only need attention when they help."}
                </p>
              </div>
              <span className="pill">
                {duplicateCheckPending ? "Checking duplicates..." : entryMode === "scan" ? "Scan first" : "Manual add"}
              </span>
            </div>

            {entryMode === "scan" ? (
              <div className="scan-first-panel">
                <div className="scan-first-header">
                  <div className="stack compact-stack">
                    <strong>Barcode capture</strong>
                    <p className="helper-text">
                      Start with the barcode and Pantro will try to fill in product context before you save.
                    </p>
                  </div>
                  <div className="pantry-inline-action-row">
                    <button
                      type="button"
                      className="ghost-button compact-button"
                      onClick={() => setIsInlineScannerOpen((current) => !current)}
                    >
                      {isInlineScannerOpen ? "Hide scanner" : getPrimaryBarcode(form.barcodesInput) ? "Scan again" : "Open scanner"}
                    </button>
                    {getPrimaryBarcode(form.barcodesInput) ? (
                      <span className="pill is-success">Barcode ready</span>
                    ) : (
                      <span className="pill">Waiting for barcode</span>
                    )}
                  </div>
                </div>

                {isInlineScannerOpen ? (
                  <BarcodeScannerDialog
                    variant="inline"
                    onClose={() => setIsInlineScannerOpen(false)}
                    onDetected={(barcode) => {
                      handleDetectedBarcode(barcode, "inline");
                    }}
                  />
                ) : (
                  <label className="field">
                    <span>Barcode</span>
                    <input
                      name="barcode"
                      value={form.barcodesInput}
                      onChange={(event) => {
                        clearDuplicateState();
                        resetEnrichmentPreview();
                        setForm((current) => ({ ...current, barcodesInput: event.target.value }));
                      }}
                      onBlur={() => {
                        const trimmedBarcode = getPrimaryBarcode(form.barcodesInput);
                        void runDuplicateCheck();
                        if (trimmedBarcode && trimmedBarcode !== lastBarcodeLookupValueRef.current) {
                          void findProductDetails("blur");
                        }
                      }}
                      placeholder="5000111046244"
                      autoComplete="off"
                      autoCorrect="off"
                      spellCheck={false}
                      inputMode="numeric"
                    />
                  </label>
                )}
              </div>
            ) : (
              <PantryBarcodeField
                inputName="barcode"
                value={form.barcodesInput}
                onChange={(value) => {
                  clearDuplicateState();
                  resetEnrichmentPreview();
                  setForm((current) => ({ ...current, barcodesInput: value }));
                }}
                onBlur={() => {
                  const trimmedBarcode = getPrimaryBarcode(form.barcodesInput);
                  void runDuplicateCheck();
                  if (trimmedBarcode && trimmedBarcode !== lastBarcodeLookupValueRef.current) {
                    void findProductDetails("blur");
                  }
                }}
                onSubmitValue={() => {
                  void runDuplicateCheck();
                  if (getPrimaryBarcode(form.barcodesInput)) {
                    void findProductDetails("manual");
                  }
                }}
                onLookup={() => void findProductDetails("manual")}
                onScan={() => setIsScannerOpen(true)}
                lookupPending={lookupPending}
                lookupDisabled={!form.name.trim() && !getPrimaryBarcode(form.barcodesInput)}
                helperText="USB scanners can type directly into this field. Camera scanning stays available when the browser and device allow it."
              />
            )}

            <div className="content-grid pantry-add-grid pantry-add-grid-core">
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
                  placeholder={entryMode === "scan" ? "Filled automatically when possible" : "Beef mince"}
                  required
                />
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
            </div>

            <div className="pantry-inline-action-row">
              <button
                type="button"
                className="ghost-button compact-button"
                onClick={() => setShowOptionalDetails((current) => !current)}
              >
                {showOptionalDetails ? "Hide optional details" : "Show optional details"}
              </button>
              {entryMode === "scan" && !isInlineScannerOpen ? (
                <button
                  type="button"
                  className="ghost-button compact-button"
                  onClick={() => setIsInlineScannerOpen(true)}
                >
                  Scan another barcode
                </button>
              ) : null}
            </div>

            {showOptionalDetails ? (
              <details className="compact-disclosure" open>
                <summary>Optional details</summary>
                <div className="compact-disclosure-body stack">
                  {entryMode === "scan" ? (
                    <PantryBarcodeField
                      inputName="barcode"
                      value={form.barcodesInput}
                      onChange={(value) => {
                        clearDuplicateState();
                        resetEnrichmentPreview();
                        setForm((current) => ({ ...current, barcodesInput: value }));
                      }}
                      onBlur={() => {
                        const trimmedBarcode = getPrimaryBarcode(form.barcodesInput);
                        void runDuplicateCheck();
                        if (
                          trimmedBarcode &&
                          trimmedBarcode !== lastBarcodeLookupValueRef.current
                        ) {
                          void findProductDetails("blur");
                        }
                      }}
                      onSubmitValue={() => {
                        void runDuplicateCheck();
                        if (getPrimaryBarcode(form.barcodesInput)) {
                          void findProductDetails("manual");
                        }
                      }}
                      onLookup={() => void findProductDetails("manual")}
                      onScan={() => setIsScannerOpen(true)}
                      lookupPending={lookupPending}
                      lookupDisabled={!form.name.trim() && !getPrimaryBarcode(form.barcodesInput)}
                      helperText="Use this section to edit the saved barcode or add an extra one before you save."
                    />
                  ) : null}

                  <div className="content-grid pantry-add-grid pantry-add-grid-optional">
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
                      <span>Purchase date</span>
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
                      <span>Expiry date</span>
                      <input
                        type="date"
                        name="expires_on"
                        value={form.expiresOn}
                        onChange={(event) =>
                          setForm((current) => ({ ...current, expiresOn: event.target.value }))
                        }
                      />
                    </label>

                    <label className="field">
                      <span>Lot note</span>
                      <input
                        name="note"
                        value={form.lotNote}
                        onChange={(event) =>
                          setForm((current) => ({ ...current, lotNote: event.target.value }))
                        }
                        placeholder="Family pack"
                      />
                    </label>
                  </div>

                  <label className="field">
                    <span>Product notes</span>
                    <textarea
                      name="product_notes"
                      rows={3}
                      value={form.productNotes}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, productNotes: event.target.value }))
                      }
                      placeholder="Storage guidance, substitutions, or household-specific notes"
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

                  <p className="helper-text">
                    Aliases and extra barcodes accept either <code>value,value</code> or{" "}
                    <code>value, value</code>.
                  </p>
                </div>
              </details>
            ) : null}
          </section>

          {lookupStatus || lookupPreview || selectedCandidate ? (
            <section className="modal-form-section">
              <details className="compact-disclosure" open={entryMode === "manual"}>
                <summary>Open Food Facts details</summary>
                <div className="compact-disclosure-body">
                  <div className="inline-status-card">
                    <div className="stack compact-stack">
                      <strong>Optional product enrichment</strong>
                      <p className="helper-text">
                        {selectedCandidate
                          ? `${selectedCandidate.source_product_name ?? "Selected match"} will be linked on save.`
                          : lookupStatus ?? "Optional enrichment is ready if you want it."}
                      </p>
                    </div>
                    <div className="page-actions">
                      {lookupPreview?.candidates.length ? (
                        <ProductEnrichmentPreview
                          preview={lookupPreview}
                          selectedSourceProductId={selectedEnrichmentSourceProductId}
                          onSelect={setSelectedEnrichmentSourceProductId}
                          onClearSelection={() => setSelectedEnrichmentSourceProductId(null)}
                        />
                      ) : null}
                      {(lookupPreview || lookupStatus || selectedCandidate) && !lookupPending ? (
                        <button
                          type="button"
                          className="ghost-button compact-button"
                          onClick={resetEnrichmentPreview}
                        >
                          Clear
                        </button>
                      ) : null}
                    </div>
                  </div>
                </div>
              </details>
            </section>
          ) : null}

          {matchedProduct ? (
            <section className="modal-form-section">
              <div className="inline-status-card is-warning">
                <div className="stack compact-stack">
                  <strong>{matchedProduct.name} already looks like the right product</strong>
                  <p className="helper-text">
                    {matchedProduct.match_reason === "barcode_exact"
                      ? "This barcode already belongs to that product, so Pantro will route this lot there."
                      : matchedProduct.match_reason === "name_similarity"
                        ? "Pantro found a likely existing product before you add this lot."
                        : "Pantro found an existing product with the same identity."}
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

          <div className="page-actions pantry-submit-actions">
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
            handleDetectedBarcode(barcode, "dialog");
            setIsScannerOpen(false);
          }}
        />
      ) : null}
    </>
  );
}
