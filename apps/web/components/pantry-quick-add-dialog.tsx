"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
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

type PantryQuickAddDialogProps = {
  householdExternalId: string;
  locations: PantryLocationSummary[];
  canAdminister: boolean;
  onClose: () => void;
};

type DuplicateDecision = "existing" | "separate" | null;

type QuickAddItem = {
  id: string;
  barcode: string;
  scanCount: number;
  name: string;
  quantity: string;
  unit: string;
  locationExternalId: string;
  purchasedOn: string;
  expiresOn: string;
  note: string;
  lookupPreview: PantryEnrichmentPreviewResponse | null;
  selectedEnrichmentSourceProductId: string | null;
  lookupStatus: string | null;
  lookupPending: boolean;
  duplicateMatch: PantryProductMatchSummary | null;
  duplicateDecision: DuplicateDecision;
  submitPending: boolean;
  error: string | null;
};

const DEFAULT_UNIT = "count";

function createQuickAddItemId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `quick-add-${Math.random().toString(36).slice(2, 10)}`;
}

function normalizeBarcodeValue(value: string) {
  return value.trim().replace(/[\s,]+/g, "");
}

function splitQueuedBarcodes(value: string) {
  return value
    .split(/[\s,]+/)
    .map((item) => normalizeBarcodeValue(item))
    .filter(Boolean);
}

function createQuickAddItem(
  barcode: string,
  defaults: {
    locationExternalId: string;
    purchasedOn: string;
  },
): QuickAddItem {
  return {
    id: createQuickAddItemId(),
    barcode,
    scanCount: 1,
    name: "",
    quantity: "1",
    unit: DEFAULT_UNIT,
    locationExternalId: defaults.locationExternalId,
    purchasedOn: defaults.purchasedOn,
    expiresOn: "",
    note: "",
    lookupPreview: null,
    selectedEnrichmentSourceProductId: null,
    lookupStatus: null,
    lookupPending: false,
    duplicateMatch: null,
    duplicateDecision: null,
    submitPending: false,
    error: null,
  };
}

function describeDuplicateMatch(matchedProduct: PantryProductMatchSummary) {
  if (matchedProduct.match_reason === "barcode_exact") {
    return "This barcode already belongs to that Pantry product, so quick add will route the lot there unless you clear the barcode.";
  }
  if (matchedProduct.match_reason === "name_similarity") {
    return "Pantry found a likely existing product. Use it by default, or keep this scan separate if that is intentional.";
  }
  return "Pantry found an existing product that already matches this item.";
}

function buildLookupStatus(preview: PantryEnrichmentPreviewResponse, barcode: string) {
  if (preview.candidates.length > 0) {
    return preview.message;
  }
  if (preview.status === "no_match" && barcode) {
    return "No Open Food Facts result found.";
  }
  return preview.message;
}

function validateQuickAddItem(item: QuickAddItem) {
  if (!item.name.trim()) {
    return "Add a product name before saving this scan.";
  }
  const normalizedQuantity = Number(item.quantity);
  if (!item.quantity.trim() || Number.isNaN(normalizedQuantity) || normalizedQuantity <= 0) {
    return "Quantity must be greater than zero.";
  }
  if (!item.unit.trim()) {
    return "Add a unit before saving this scan.";
  }
  if (!item.locationExternalId) {
    return "Choose a storage location before saving this scan.";
  }
  if (item.purchasedOn && item.expiresOn && item.expiresOn < item.purchasedOn) {
    return "Expiry date cannot be earlier than purchase date.";
  }
  return null;
}

export function PantryQuickAddDialog({
  householdExternalId,
  locations,
  canAdminister,
  onClose,
}: PantryQuickAddDialogProps) {
  const router = useRouter();
  const captureInputRef = useRef<HTMLInputElement | null>(null);
  const itemsRef = useRef<QuickAddItem[]>([]);
  const [captureValue, setCaptureValue] = useState("");
  const [captureError, setCaptureError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [sessionLocationExternalId, setSessionLocationExternalId] = useState("");
  const [sessionPurchasedOn, setSessionPurchasedOn] = useState("");
  const [items, setItems] = useState<QuickAddItem[]>([]);
  const [isScannerOpen, setIsScannerOpen] = useState(false);
  const [bulkPending, setBulkPending] = useState(false);

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  useEffect(() => {
    captureInputRef.current?.focus();
  }, []);

  function replaceItems(nextItems: QuickAddItem[]) {
    itemsRef.current = nextItems;
    setItems(nextItems);
  }

  function mutateItems(updater: (current: QuickAddItem[]) => QuickAddItem[]) {
    const nextItems = updater(itemsRef.current);
    replaceItems(nextItems);
    return nextItems;
  }

  function focusCaptureField() {
    window.setTimeout(() => {
      captureInputRef.current?.focus();
    }, 0);
  }

  async function hydrateQuickAddItem(
    itemId: string,
    {
      barcode,
      productName,
    }: {
      barcode: string;
      productName: string;
    },
  ) {
    mutateItems((current) =>
      current.map((item) =>
        item.id === itemId
          ? {
              ...item,
              lookupPending: true,
              error: null,
            }
          : item,
      ),
    );

    let lookupPreview: PantryEnrichmentPreviewResponse | null = null;
    let lookupStatus: string | null = null;
    let suggestedName = productName.trim();
    let selectedEnrichmentSourceProductId: string | null = null;
    let duplicateResponse: PantryDuplicateCheckResponse | null = null;
    let nextError: string | null = null;

    try {
      lookupPreview = await postToApi<PantryEnrichmentPreviewResponse>(
        `/api/households/${householdExternalId}/pantry/enrichment/preview`,
        {
          product_name: suggestedName,
          barcode,
        },
      );
      lookupStatus = buildLookupStatus(lookupPreview, barcode);
      if (!suggestedName) {
        suggestedName = lookupPreview.candidates[0]?.source_product_name?.trim() ?? "";
      }
      if (lookupPreview.candidates.length === 1 || lookupPreview.lookup_strategy === "barcode") {
        selectedEnrichmentSourceProductId = lookupPreview.candidates[0]?.source_product_id ?? null;
      }
    } catch (requestError) {
      nextError =
        requestError instanceof Error ? requestError.message : "Could not look up product details.";
    }

    try {
      duplicateResponse = await postToApi<PantryDuplicateCheckResponse>(
        `/api/households/${householdExternalId}/pantry/entries/duplicate-check`,
        {
          name: suggestedName || null,
          barcode,
        },
      );
    } catch (requestError) {
      if (!nextError) {
        nextError =
          requestError instanceof Error
            ? requestError.message
            : "Could not check for existing Pantry products.";
      }
    }

    mutateItems((current) =>
      current.map((item) => {
        if (item.id !== itemId) {
          return item;
        }
        const matchedProduct = duplicateResponse?.matched_product ?? null;
        return {
          ...item,
          name: item.name.trim() ? item.name : suggestedName || matchedProduct?.name || "",
          lookupPreview,
          selectedEnrichmentSourceProductId,
          lookupStatus,
          lookupPending: false,
          duplicateMatch: matchedProduct,
          duplicateDecision: matchedProduct ? "existing" : null,
          unit:
            item.unit.trim() && item.unit !== DEFAULT_UNIT
              ? item.unit
              : matchedProduct?.default_unit ?? item.unit,
          error: nextError,
        };
      }),
    );
  }

  function queueBarcodes(rawValue: string) {
    const nextBarcodes = splitQueuedBarcodes(rawValue);
    if (nextBarcodes.length === 0) {
      setCaptureError("Scan or type at least one barcode first.");
      focusCaptureField();
      return;
    }

    const newItems: QuickAddItem[] = [];
    let nextItems = [...itemsRef.current];
    nextBarcodes.forEach((barcode) => {
      const existingItem = nextItems.find((item) => item.barcode === barcode) ?? null;
      if (existingItem) {
        const nextScanCount = existingItem.scanCount + 1;
        nextItems = nextItems.map((item) =>
          item.id === existingItem.id
            ? {
                ...item,
                scanCount: nextScanCount,
                quantity:
                  item.quantity.trim() === String(existingItem.scanCount)
                    ? String(nextScanCount)
                    : item.quantity,
              }
            : item,
        );
        return;
      }

      const created = createQuickAddItem(barcode, {
        locationExternalId: sessionLocationExternalId,
        purchasedOn: sessionPurchasedOn,
      });
      nextItems = [created, ...nextItems];
      newItems.push(created);
    });

    replaceItems(nextItems);

    setCaptureValue("");
    setCaptureError(null);
    setStatusMessage(
      nextBarcodes.length === 1
        ? `Queued ${nextBarcodes[0]} for review.`
        : `Queued ${nextBarcodes.length} barcodes for review.`,
    );
    focusCaptureField();
    newItems.forEach((item) => {
      void hydrateQuickAddItem(item.id, {
        barcode: item.barcode,
        productName: item.name,
      });
    });
  }

  function removeItem(itemId: string) {
    mutateItems((current) => current.filter((item) => item.id !== itemId));
    focusCaptureField();
  }

  function updateItem(itemId: string, patch: Partial<QuickAddItem>) {
    mutateItems((current) =>
      current.map((item) => (item.id === itemId ? { ...item, ...patch } : item)),
    );
  }

  function applySessionDefaultsToQueuedItems() {
    mutateItems((current) =>
      current.map((item) => ({
        ...item,
        locationExternalId: sessionLocationExternalId || item.locationExternalId,
        purchasedOn: sessionPurchasedOn || item.purchasedOn,
      })),
    );
    setStatusMessage("Applied the common quick-add defaults to the queued items.");
  }

  async function submitItem(
    itemId: string,
    { refreshAfter = true }: { refreshAfter?: boolean } = {},
  ) {
    const item = itemsRef.current.find((candidate) => candidate.id === itemId);
    if (!item) {
      return false;
    }

    const validationError = validateQuickAddItem(item);
    if (validationError) {
      updateItem(itemId, { error: validationError });
      return false;
    }

    updateItem(itemId, { submitPending: true, error: null });

    const selectedCandidate =
      item.lookupPreview?.candidates.find(
        (candidate) => candidate.source_product_id === item.selectedEnrichmentSourceProductId,
      ) ?? null;

    try {
      const response = await postToApi<PantryEntryMutationResponse>(
        `/api/households/${householdExternalId}/pantry/entries`,
        {
          name: item.name.trim(),
          quantity: item.quantity,
          unit: item.unit.trim(),
          location_external_id: item.locationExternalId,
          barcode: item.barcode,
          aliases: [],
          product_notes: null,
          manual_ingredient_tags: [],
          purchased_on: item.purchasedOn || null,
          expires_on: item.expiresOn || null,
          note: item.note.trim() || null,
          existing_product_external_id:
            item.duplicateMatch && item.duplicateDecision !== "separate"
              ? item.duplicateMatch.external_id
              : null,
          allow_separate_product:
            Boolean(item.duplicateMatch?.can_keep_separate_product) &&
            item.duplicateDecision === "separate",
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
        updateItem(itemId, {
          submitPending: false,
          duplicateMatch: response.matched_product,
          duplicateDecision: "existing",
          error: response.message,
        });
        return false;
      }

      if (response.status === "creation_not_allowed" || response.status === "alias_conflict") {
        updateItem(itemId, {
          submitPending: false,
          error: response.message,
        });
        return false;
      }

      mutateItems((current) => current.filter((candidate) => candidate.id !== itemId));
      setStatusMessage(response.message);
      if (refreshAfter) {
        router.refresh();
      }
      return true;
    } catch (requestError) {
      updateItem(itemId, {
        submitPending: false,
        error: requestError instanceof Error ? requestError.message : "Could not save this scan.",
      });
      return false;
    } finally {
      updateItem(itemId, { submitPending: false });
    }
  }

  async function submitAllItems() {
    const itemIds = itemsRef.current.map((item) => item.id);
    if (itemIds.length === 0) {
      return;
    }

    setBulkPending(true);
    setStatusMessage(null);

    let addedCount = 0;
    for (const itemId of itemIds) {
      const added = await submitItem(itemId, { refreshAfter: false });
      if (added) {
        addedCount += 1;
      }
    }

    if (addedCount > 0) {
      router.refresh();
    }
    const remainingCount = itemsRef.current.length;
    setStatusMessage(
      addedCount === 0
        ? "No queued items were added. Review the highlighted rows and try again."
        : remainingCount === 0
          ? `Added ${addedCount} item${addedCount === 1 ? "" : "s"} to Pantry.`
          : `Added ${addedCount} item${addedCount === 1 ? "" : "s"}. ${remainingCount} still need review.`,
    );
    setBulkPending(false);
    focusCaptureField();
  }

  return (
    <>
      <ModalShell
        title="Quick add pantry items"
        description="Queue multiple barcodes first, let Pantry look up Open Food Facts data in the background, then review the compact lot details before saving."
        onClose={onClose}
        closeOnBackdropClick={false}
        panelClassName="modal-panel modal-panel-wide"
      >
        <div className="stack pantry-quick-add-shell" data-testid="pantry-quick-add-dialog">
          <section className="modal-form-section">
            <div className="setup-card-toolbar">
              <div className="stack compact-stack">
                <h3 className="modal-section-title">Scan queue</h3>
                <p className="helper-text">
                  Keep the cursor in this field for USB scanners. You can also paste multiple
                  barcodes separated by spaces, commas, or new lines.
                </p>
              </div>
              <span className="pill">
                {items.length} queued item{items.length === 1 ? "" : "s"}
              </span>
            </div>

            <div className="content-grid pantry-quick-add-session-grid">
              <label className="field">
                <span>Common storage location</span>
                <select
                  value={sessionLocationExternalId}
                  onChange={(event) => setSessionLocationExternalId(event.target.value)}
                >
                  <option value="">Choose later per item</option>
                  {locations.map((location) => (
                    <option key={location.external_id} value={location.external_id}>
                      {location.location_group_name} / {location.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Common purchase date</span>
                <input
                  type="date"
                  value={sessionPurchasedOn}
                  onChange={(event) => setSessionPurchasedOn(event.target.value)}
                />
              </label>
            </div>

            <div className="pantry-quick-add-capture">
              <label className="field pantry-quick-add-capture-field">
                <span>Barcode capture</span>
                <input
                  ref={captureInputRef}
                  value={captureValue}
                  onChange={(event) => setCaptureValue(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key !== "Enter") {
                      return;
                    }
                    event.preventDefault();
                    queueBarcodes(captureValue);
                  }}
                  placeholder="Scan a barcode and wait for Enter"
                  autoComplete="off"
                  autoCorrect="off"
                  spellCheck={false}
                />
              </label>

              <div className="pantry-quick-add-capture-actions">
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => queueBarcodes(captureValue)}
                >
                  Add barcode
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => setIsScannerOpen(true)}
                >
                  Scan with camera
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={items.length === 0}
                  onClick={applySessionDefaultsToQueuedItems}
                >
                  Apply defaults to queued items
                </button>
              </div>
            </div>

            {captureError ? <p className="error-text">{captureError}</p> : null}
            {statusMessage ? <p className="status-note">{statusMessage}</p> : null}
            {!canAdminister ? (
              <p className="helper-text">
                Household admins can create new Pantry products during quick add. Non-admin users
                can still add to existing products when a match is found.
              </p>
            ) : null}
          </section>

          <section className="modal-form-section">
            <div className="setup-card-toolbar">
              <div className="stack compact-stack">
                <h3 className="modal-section-title">Review queued items</h3>
                <p className="helper-text">
                  Each row keeps the barcode, suggested product name, quantity, and lot details
                  together so repeated post-shop entry stays dense.
                </p>
              </div>
            </div>

            {items.length === 0 ? (
              <div className="empty-state">
                <p>Scan at least one barcode to start a quick-add session.</p>
              </div>
            ) : (
              <div className="quick-add-item-list">
                {items.map((item) => {
                  const selectedCandidate =
                    item.lookupPreview?.candidates.find(
                      (candidate) =>
                        candidate.source_product_id === item.selectedEnrichmentSourceProductId,
                    ) ?? null;

                  return (
                    <article
                      key={item.id}
                      className="quick-add-item-card"
                      data-testid={`quick-add-item-${item.id}`}
                    >
                      <div className="inventory-context-header">
                        <div className="stack compact-stack">
                          <strong>{item.name.trim() || `Barcode ${item.barcode}`}</strong>
                          <p className="helper-text">Barcode {item.barcode}</p>
                        </div>
                        <div className="tag-row">
                          <span className="pill">
                            {item.scanCount} scan{item.scanCount === 1 ? "" : "s"}
                          </span>
                          {item.lookupPending ? <span className="pill">Looking up…</span> : null}
                          {selectedCandidate ? <span className="pill is-success">OFF ready</span> : null}
                          <button
                            type="button"
                            className="ghost-button compact-button"
                            onClick={() => removeItem(item.id)}
                          >
                            Remove
                          </button>
                        </div>
                      </div>

                      {item.duplicateMatch ? (
                        <div className="inline-status-card is-warning">
                          <div className="stack compact-stack">
                            <strong>{item.duplicateMatch.name} already looks right</strong>
                            <p className="helper-text">
                              {describeDuplicateMatch(item.duplicateMatch)}
                            </p>
                          </div>
                          <div className="duplicate-choice-row">
                            <button
                              type="button"
                              className={
                                item.duplicateDecision === "existing"
                                  ? "primary-button compact-button"
                                  : "ghost-button compact-button"
                              }
                              onClick={() =>
                                updateItem(item.id, { duplicateDecision: "existing" })
                              }
                            >
                              Add lot to existing product
                            </button>
                            {item.duplicateMatch.can_keep_separate_product ? (
                              <button
                                type="button"
                                className={
                                  item.duplicateDecision === "separate"
                                    ? "primary-button compact-button"
                                    : "ghost-button compact-button"
                                }
                                onClick={() =>
                                  updateItem(item.id, { duplicateDecision: "separate" })
                                }
                              >
                                Keep separate
                              </button>
                            ) : null}
                          </div>
                        </div>
                      ) : null}

                      <div className="content-grid pantry-quick-add-grid">
                        <label className="field">
                          <span>Product name</span>
                          <input
                            value={item.name}
                            onChange={(event) =>
                              updateItem(item.id, {
                                name: event.target.value,
                                error: null,
                              })
                            }
                            placeholder="Open Food Facts will try to fill this"
                            required
                          />
                        </label>

                        <label className="field">
                          <span>Quantity</span>
                          <input
                            type="number"
                            min="0.001"
                            step="0.001"
                            value={item.quantity}
                            onChange={(event) =>
                              updateItem(item.id, {
                                quantity: event.target.value,
                                error: null,
                              })
                            }
                            required
                          />
                        </label>

                        <label className="field">
                          <span>Unit</span>
                          <input
                            value={item.unit}
                            onChange={(event) =>
                              updateItem(item.id, {
                                unit: event.target.value,
                                error: null,
                              })
                            }
                            required
                          />
                        </label>

                        <label className="field">
                          <span>Storage location</span>
                          <select
                            value={item.locationExternalId}
                            onChange={(event) =>
                              updateItem(item.id, {
                                locationExternalId: event.target.value,
                                error: null,
                              })
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
                          <span>Purchase date</span>
                          <input
                            type="date"
                            value={item.purchasedOn}
                            onChange={(event) =>
                              updateItem(item.id, { purchasedOn: event.target.value, error: null })
                            }
                          />
                        </label>

                        <label className="field">
                          <span>Expiry date</span>
                          <input
                            type="date"
                            value={item.expiresOn}
                            onChange={(event) =>
                              updateItem(item.id, { expiresOn: event.target.value, error: null })
                            }
                          />
                        </label>
                      </div>

                      <label className="field">
                        <span>Lot note</span>
                        <input
                          value={item.note}
                          onChange={(event) =>
                            updateItem(item.id, { note: event.target.value, error: null })
                          }
                          placeholder="Optional pack or lot note"
                        />
                      </label>

                      {item.lookupStatus ? <p className="helper-text">{item.lookupStatus}</p> : null}

                      {item.lookupPreview?.candidates.length ? (
                        <details className="compact-disclosure">
                          <summary>
                            Review {item.lookupPreview.candidates.length} Open Food Facts match
                            {item.lookupPreview.candidates.length === 1 ? "" : "es"}
                          </summary>
                          <div className="compact-disclosure-body">
                            <ProductEnrichmentPreview
                              preview={item.lookupPreview}
                              selectedSourceProductId={item.selectedEnrichmentSourceProductId}
                              onSelect={(sourceProductId) =>
                                updateItem(item.id, {
                                  selectedEnrichmentSourceProductId: sourceProductId,
                                })
                              }
                              onClearSelection={() =>
                                updateItem(item.id, {
                                  selectedEnrichmentSourceProductId: null,
                                })
                              }
                            />
                          </div>
                        </details>
                      ) : null}

                      {item.error ? <p className="error-text">{item.error}</p> : null}

                      <div className="page-actions">
                        <button
                          type="button"
                          className="ghost-button compact-button"
                          disabled={item.lookupPending || item.submitPending}
                          onClick={() =>
                            void hydrateQuickAddItem(item.id, {
                              barcode: item.barcode,
                              productName: item.name,
                            })
                          }
                        >
                          {item.lookupPending ? "Checking..." : "Refresh lookup"}
                        </button>
                        <button
                          type="button"
                          className="primary-button compact-button"
                          disabled={item.submitPending || bulkPending}
                          onClick={() => void submitItem(item.id)}
                        >
                          {item.submitPending ? "Adding..." : "Add this item"}
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>

          <div className="page-actions">
            <button
              type="button"
              className="primary-button"
              disabled={items.length === 0 || bulkPending}
              onClick={() => void submitAllItems()}
            >
              {bulkPending
                ? "Adding queued items..."
                : `Add ${items.length} queued item${items.length === 1 ? "" : "s"}`}
            </button>
          </div>
        </div>
      </ModalShell>

      {isScannerOpen ? (
        <BarcodeScannerDialog
          onClose={() => setIsScannerOpen(false)}
          onDetected={(barcode) => {
            queueBarcodes(barcode);
            setIsScannerOpen(false);
          }}
        />
      ) : null}
    </>
  );
}
