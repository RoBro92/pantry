"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  BulkPantryEntryMutationResponse,
  PantryDuplicateCheckResponse,
  PantryEnrichmentPreviewResponse,
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
    error: null,
  };
}

function getSelectedCandidate(item: QuickAddItem) {
  return (
    item.lookupPreview?.candidates.find(
      (candidate) => candidate.source_product_id === item.selectedEnrichmentSourceProductId,
    ) ?? null
  );
}

function describeDuplicateMatch(matchedProduct: PantryProductMatchSummary) {
  if (matchedProduct.match_reason === "barcode_exact") {
    return "This barcode already belongs to that product record, so Pantro will add another lot there unless you clear or correct the barcode.";
  }
  if (matchedProduct.match_reason === "canonical_verified") {
    return "Pantro matched this item to a verified local canonical record and will reuse the existing household product on save.";
  }
  if (matchedProduct.match_reason === "name_similarity") {
    return "Pantro found a likely existing product record. Use it by default, or keep this scan separate if that is intentional.";
  }
  return "Pantro found an existing product record that already matches this item.";
}

function buildLookupStatus(preview: PantryEnrichmentPreviewResponse, barcode: string) {
  if (preview.candidates.length > 0) {
    return preview.message;
  }
  if (preview.status === "no_match" && barcode) {
    return "No Open Food Facts result found for this barcode.";
  }
  return preview.message;
}

function validateQuickAddItem(item: QuickAddItem) {
  if (!item.name.trim()) {
    return "Add a product name before moving on.";
  }

  const normalizedQuantity = Number(item.quantity);
  if (!item.quantity.trim() || Number.isNaN(normalizedQuantity) || normalizedQuantity <= 0) {
    return "Quantity must be greater than zero.";
  }

  if (!item.unit.trim()) {
    return "Add a unit before moving on.";
  }

  if (!item.locationExternalId) {
    return "Choose a storage location before moving on.";
  }

  if (item.purchasedOn && item.expiresOn && item.expiresOn < item.purchasedOn) {
    return "Expiry date cannot be earlier than purchase date.";
  }

  return null;
}

function getQueueItemState(item: QuickAddItem) {
  if (item.lookupPending) {
    return "loading";
  }
  if (validateQuickAddItem(item)) {
    return "needs_attention";
  }
  return "ready";
}

function buildSaveSummary(response: BulkPantryEntryMutationResponse) {
  if (response.added_count === 0) {
    return "No queued items were added. Review the highlighted items and try again.";
  }

  if (response.failed_count === 0) {
    return `Added ${response.added_count} item${response.added_count === 1 ? "" : "s"} to inventory.`;
  }

  return `Added ${response.added_count} item${response.added_count === 1 ? "" : "s"}. ${response.failed_count} still need review.`;
}

function QueueStatusPill({ item }: { item: QuickAddItem }) {
  const state = getQueueItemState(item);

  if (state === "loading") {
    return <span className="pill">Looking up…</span>;
  }

  if (state === "ready") {
    return <span className="pill is-success">Ready</span>;
  }

  return <span className="pill">Needs details</span>;
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
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isScannerOpen, setIsScannerOpen] = useState(false);
  const [bulkPending, setBulkPending] = useState(false);

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  useEffect(() => {
    captureInputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (items.length === 0) {
      setCurrentIndex(0);
      return;
    }
    if (currentIndex >= items.length) {
      setCurrentIndex(items.length - 1);
    }
  }, [currentIndex, items.length]);

  const totalScans = useMemo(
    () => items.reduce((sum, item) => sum + item.scanCount, 0),
    [items],
  );
  const repeatedScanCount = totalScans - items.length;
  const readyCount = useMemo(
    () => items.filter((item) => getQueueItemState(item) === "ready").length,
    [items],
  );
  const currentItem = items[currentIndex] ?? null;
  const currentItemValidationError = currentItem ? validateQuickAddItem(currentItem) : null;
  const selectedCandidate = currentItem ? getSelectedCandidate(currentItem) : null;

  function focusCaptureField() {
    window.setTimeout(() => {
      captureInputRef.current?.focus();
    }, 0);
  }

  function replaceItems(nextItems: QuickAddItem[]) {
    itemsRef.current = nextItems;
    setItems(nextItems);
  }

  function mutateItems(updater: (current: QuickAddItem[]) => QuickAddItem[]) {
    const nextItems = updater(itemsRef.current);
    replaceItems(nextItems);
    return nextItems;
  }

  function updateItem(itemId: string, patch: Partial<QuickAddItem>) {
    mutateItems((current) =>
      current.map((item) => (item.id === itemId ? { ...item, ...patch } : item)),
    );
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
    const normalizedBarcode = normalizeBarcodeValue(barcode);
    const normalizedName = productName.trim();
    if (!normalizedBarcode && !normalizedName) {
      updateItem(itemId, {
        lookupPending: false,
        lookupPreview: null,
        lookupStatus: null,
        selectedEnrichmentSourceProductId: null,
        duplicateMatch: null,
        duplicateDecision: null,
        error: null,
      });
      return;
    }

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
          barcode: normalizedBarcode || null,
        },
      );
      lookupStatus = buildLookupStatus(lookupPreview, normalizedBarcode);
      if (!suggestedName) {
        suggestedName = lookupPreview.candidates[0]?.source_product_name?.trim() ?? "";
      }
      if (
        lookupPreview.candidates.length === 1 ||
        lookupPreview.lookup_strategy === "barcode"
      ) {
        selectedEnrichmentSourceProductId =
          lookupPreview.candidates[0]?.source_product_id ?? null;
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
          barcode: normalizedBarcode || null,
        },
      );
    } catch (requestError) {
      if (!nextError) {
        nextError =
          requestError instanceof Error
            ? requestError.message
            : "Could not check for existing product records.";
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
      nextItems = [...nextItems, created];
      newItems.push(created);
    });

    const hadItems = itemsRef.current.length > 0;
    replaceItems(nextItems);

    if (!hadItems && newItems.length > 0) {
      setCurrentIndex(0);
    }

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
    setStatusMessage("Removed that item from the scan queue.");
  }

  function applySessionDefaultsToQueuedItems() {
    mutateItems((current) =>
      current.map((item) => ({
        ...item,
        locationExternalId: sessionLocationExternalId || item.locationExternalId,
        purchasedOn: sessionPurchasedOn || item.purchasedOn,
      })),
    );
    setStatusMessage("Applied the common defaults to the queued items.");
  }

  function goToNextItem() {
    if (!currentItem) {
      return;
    }

    const validationError = validateQuickAddItem(currentItem);
    if (validationError) {
      updateItem(currentItem.id, { error: validationError });
      setStatusMessage("Complete the required details before moving to the next item.");
      return;
    }

    if (currentIndex < items.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setStatusMessage(null);
      return;
    }

    setStatusMessage("All queued items are reviewed. Save all when you are ready.");
  }

  async function refreshCurrentItem() {
    if (!currentItem) {
      return;
    }

    await hydrateQuickAddItem(currentItem.id, {
      barcode: currentItem.barcode,
      productName: currentItem.name,
    });
  }

  async function submitAllItems() {
    if (itemsRef.current.length === 0) {
      return;
    }

    const nextItems = itemsRef.current.map((item) => ({
      ...item,
      error: validateQuickAddItem(item),
    }));
    replaceItems(nextItems);

    const firstInvalidIndex = nextItems.findIndex((item) => item.error);
    if (firstInvalidIndex >= 0) {
      setCurrentIndex(firstInvalidIndex);
      setStatusMessage("Review the highlighted item before saving the queue.");
      return;
    }

    setBulkPending(true);
    setStatusMessage(null);

    try {
      const response = await postToApi<BulkPantryEntryMutationResponse>(
        `/api/households/${householdExternalId}/pantry/entries/bulk`,
        {
          entries: itemsRef.current.map((item) => {
            const candidate = getSelectedCandidate(item);
            return {
              name: item.name.trim(),
              quantity: item.quantity,
              unit: item.unit.trim(),
              location_external_id: item.locationExternalId,
              barcode: item.barcode || null,
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
              confirmed_enrichment: candidate
                ? {
                    source_name: candidate.source_name,
                    source_product_id: candidate.source_product_id,
                    match_status: candidate.match_status,
                  }
                : null,
            };
          }),
        },
      );

      const failedItems: QuickAddItem[] = [];
      response.items.forEach((result) => {
        const existingItem = itemsRef.current[result.request_index];
        if (!existingItem) {
          return;
        }
        if (result.ok) {
          return;
        }

        failedItems.push({
          ...existingItem,
          duplicateMatch: result.matched_product ?? existingItem.duplicateMatch,
          duplicateDecision: result.matched_product ? "existing" : existingItem.duplicateDecision,
          error: result.message,
          unit:
            result.matched_product?.default_unit && existingItem.unit !== result.matched_product.default_unit
              ? result.matched_product.default_unit
              : existingItem.unit,
        });
      });

      replaceItems(failedItems);
      if (failedItems.length > 0) {
        setCurrentIndex(0);
      }

      if (response.added_count > 0) {
        router.refresh();
      }

      setStatusMessage(buildSaveSummary(response));
      focusCaptureField();
    } catch (requestError) {
      setStatusMessage(null);
      setCaptureError(
        requestError instanceof Error ? requestError.message : "Could not save the queued items.",
      );
    } finally {
      setBulkPending(false);
    }
  }

  return (
    <>
      <ModalShell
        title="Bulk scan inventory items"
        description="Scan multiple barcodes first, let Pantro look up Open Food Facts data in the background, then review each queued item one at a time before saving the whole batch."
        onClose={onClose}
        closeOnBackdropClick={false}
        panelClassName="modal-panel modal-panel-wide"
      >
        <div className="stack pantry-quick-add-shell" data-testid="pantry-quick-add-dialog">
          <section className="modal-form-section">
            <div className="setup-card-toolbar">
              <div className="stack compact-stack">
                <h3 className="modal-section-title">Scan setup</h3>
                <p className="helper-text">
                  Keep the cursor in the capture field for USB scanners. You can also paste or scan
                  multiple barcodes separated by spaces, commas, or new lines.
                </p>
              </div>
              <div className="tag-row">
                <span className="pill">
                  {items.length} queued item{items.length === 1 ? "" : "s"}
                </span>
                <span className="pill">{totalScans} total scan{totalScans === 1 ? "" : "s"}</span>
                {repeatedScanCount > 0 ? (
                  <span className="pill">{repeatedScanCount} repeat{repeatedScanCount === 1 ? "" : "s"} merged</span>
                ) : null}
              </div>
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
                  onChange={(event) => {
                    setCaptureValue(event.target.value);
                    if (captureError) {
                      setCaptureError(null);
                    }
                  }}
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
                  inputMode="numeric"
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
                Household admins can create new product records during bulk scan. Non-admin users
                can still add to existing products when a match is found.
              </p>
            ) : null}
          </section>

          <section className="modal-form-section pantry-bulk-review-shell">
            <div className="pantry-bulk-queue-panel">
              <div className="setup-card-toolbar">
                <div className="stack compact-stack">
                  <h3 className="modal-section-title">Session queue</h3>
                  <p className="helper-text">
                    Review items one at a time. Repeated scans are already collapsed into quantity
                    where possible.
                  </p>
                </div>
                <span className="pill">
                  {readyCount} ready / {items.length}
                </span>
              </div>

              {items.length === 0 ? (
                <div className="empty-state">
                  <p>Scan at least one barcode to start a bulk scan session.</p>
                </div>
              ) : (
                <div className="pantry-bulk-queue-list">
                  {items.map((item, index) => (
                    <button
                      key={item.id}
                      type="button"
                      className={
                        index === currentIndex
                          ? "pantry-bulk-queue-item is-current"
                          : "pantry-bulk-queue-item"
                      }
                      data-testid={`quick-add-item-${item.id}`}
                      onClick={() => setCurrentIndex(index)}
                    >
                      <div className="stack compact-stack">
                        <strong>{item.name.trim() || `Barcode ${item.barcode}`}</strong>
                        <p className="helper-text">
                          {item.barcode ? `Barcode ${item.barcode}` : "Barcode can be added during review"}
                        </p>
                      </div>
                      <div className="tag-row">
                        <span className="pill">
                          {item.scanCount} scan{item.scanCount === 1 ? "" : "s"}
                        </span>
                        {item.duplicateMatch ? <span className="pill">Duplicate</span> : null}
                        {getSelectedCandidate(item) ? <span className="pill is-success">OFF ready</span> : null}
                        <QueueStatusPill item={item} />
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="pantry-bulk-review-panel">
              {currentItem ? (
                <div className="stack">
                  <div className="setup-card-toolbar">
                    <div className="stack compact-stack">
                      <h3 className="modal-section-title">
                        Review item {currentIndex + 1} of {items.length}
                      </h3>
                      <p className="helper-text">
                        Confirm the product match, lot details, and storage location before moving
                        on.
                      </p>
                    </div>
                    <div className="tag-row">
                      {currentItem.scanCount > 1 ? (
                        <span className="pill">
                          {currentItem.scanCount} scans collapsed into this entry
                        </span>
                      ) : null}
                      {currentItemValidationError ? (
                        <span className="pill">Needs attention</span>
                      ) : (
                        <span className="pill is-success">Ready to save</span>
                      )}
                    </div>
                  </div>

                  <div className="content-grid pantry-bulk-review-grid">
                    <label className="field">
                      <span>Barcode</span>
                      <input
                        value={currentItem.barcode}
                        onChange={(event) =>
                          updateItem(currentItem.id, {
                            barcode: normalizeBarcodeValue(event.target.value),
                            duplicateMatch: null,
                            duplicateDecision: null,
                            lookupPreview: null,
                            lookupStatus: null,
                            selectedEnrichmentSourceProductId: null,
                            error: null,
                          })
                        }
                        onKeyDown={(event) => {
                          if (event.key !== "Enter") {
                            return;
                          }
                          event.preventDefault();
                          void refreshCurrentItem();
                        }}
                        placeholder="Correct or clear the barcode if needed"
                        autoComplete="off"
                        autoCorrect="off"
                        spellCheck={false}
                        inputMode="numeric"
                      />
                    </label>

                    <label className="field">
                      <span>Product name</span>
                      <input
                        value={currentItem.name}
                        onChange={(event) =>
                          updateItem(currentItem.id, {
                            name: event.target.value,
                            duplicateMatch: null,
                            duplicateDecision: null,
                            lookupPreview: null,
                            lookupStatus: null,
                            selectedEnrichmentSourceProductId: null,
                            error: null,
                          })
                        }
                        placeholder="Open Food Facts will try to fill this"
                      />
                    </label>

                    <label className="field">
                      <span>Quantity</span>
                      <input
                        type="number"
                        min="0.001"
                        step="0.001"
                        value={currentItem.quantity}
                        onChange={(event) =>
                          updateItem(currentItem.id, {
                            quantity: event.target.value,
                            error: null,
                          })
                        }
                      />
                    </label>

                    <label className="field">
                      <span>Unit</span>
                      <input
                        value={currentItem.unit}
                        onChange={(event) =>
                          updateItem(currentItem.id, {
                            unit: event.target.value,
                            error: null,
                          })
                        }
                      />
                    </label>

                    <label className="field">
                      <span>Storage location</span>
                      <select
                        value={currentItem.locationExternalId}
                        onChange={(event) =>
                          updateItem(currentItem.id, {
                            locationExternalId: event.target.value,
                            error: null,
                          })
                        }
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
                        value={currentItem.purchasedOn}
                        onChange={(event) =>
                          updateItem(currentItem.id, {
                            purchasedOn: event.target.value,
                            error: null,
                          })
                        }
                      />
                    </label>

                    <label className="field">
                      <span>Expiry date</span>
                      <input
                        type="date"
                        value={currentItem.expiresOn}
                        onChange={(event) =>
                          updateItem(currentItem.id, {
                            expiresOn: event.target.value,
                            error: null,
                          })
                        }
                      />
                    </label>
                  </div>

                  <label className="field">
                    <span>Lot note</span>
                    <input
                      value={currentItem.note}
                      onChange={(event) =>
                        updateItem(currentItem.id, {
                          note: event.target.value,
                          error: null,
                        })
                      }
                      placeholder="Optional pack or lot note"
                    />
                  </label>

                  {currentItem.duplicateMatch ? (
                    <div className="inline-status-card is-warning">
                      <div className="stack compact-stack">
                        <strong>{currentItem.duplicateMatch.name} already looks right</strong>
                        <p className="helper-text">
                          {describeDuplicateMatch(currentItem.duplicateMatch)}
                        </p>
                      </div>
                      <p className="helper-text">Default action: save this scan as another lot on the existing product.</p>
                      {currentItem.duplicateMatch.can_keep_separate_product ? (
                        <details className="compact-disclosure">
                          <summary>
                            {currentItem.duplicateDecision === "separate"
                              ? "Separate product override selected"
                              : "Create a separate product anyway"}
                          </summary>
                          <div className="compact-disclosure-body stack">
                            <p className="helper-text">
                              Only use a separate product if this scan should stay distinct in your household inventory.
                            </p>
                            <div className="page-actions">
                              {currentItem.duplicateDecision === "separate" ? (
                                <button
                                  type="button"
                                  className="ghost-button compact-button"
                                  onClick={() =>
                                    updateItem(currentItem.id, { duplicateDecision: "existing" })
                                  }
                                >
                                  Use existing product instead
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  className="ghost-button compact-button"
                                  onClick={() =>
                                    updateItem(currentItem.id, { duplicateDecision: "separate" })
                                  }
                                >
                                  Create separate product
                                </button>
                              )}
                            </div>
                          </div>
                        </details>
                      ) : null}
                    </div>
                  ) : null}

                  <div className="inline-status-card">
                    <div className="stack compact-stack">
                      <strong>Product identification</strong>
                      <p className="helper-text">
                        {selectedCandidate
                          ? `${selectedCandidate.source_product_name ?? "Selected OFF match"} will be linked when you save this batch.`
                          : currentItem.lookupStatus ??
                            "Refresh the product match after correcting the barcode or name."}
                      </p>
                    </div>
                    <div className="page-actions">
                      <button
                        type="button"
                        className="ghost-button compact-button"
                        disabled={currentItem.lookupPending}
                        onClick={() => void refreshCurrentItem()}
                      >
                        {currentItem.lookupPending ? "Checking..." : "Refresh product match"}
                      </button>
                    </div>
                  </div>

                  {currentItem.lookupPreview?.candidates.length ? (
                    <details className="compact-disclosure" open={Boolean(selectedCandidate)}>
                      <summary>
                        Review {currentItem.lookupPreview.candidates.length} Open Food Facts match
                        {currentItem.lookupPreview.candidates.length === 1 ? "" : "es"}
                      </summary>
                      <div className="compact-disclosure-body">
                        <ProductEnrichmentPreview
                          preview={currentItem.lookupPreview}
                          selectedSourceProductId={currentItem.selectedEnrichmentSourceProductId}
                          onSelect={(sourceProductId) =>
                            updateItem(currentItem.id, {
                              selectedEnrichmentSourceProductId: sourceProductId,
                            })
                          }
                          onClearSelection={() =>
                            updateItem(currentItem.id, {
                              selectedEnrichmentSourceProductId: null,
                            })
                          }
                        />
                      </div>
                    </details>
                  ) : null}

                  {currentItem.error ? <p className="error-text">{currentItem.error}</p> : null}

                  <div className="page-actions pantry-bulk-review-actions">
                    <button
                      type="button"
                      className="ghost-button"
                      disabled={currentIndex === 0}
                      onClick={() => setCurrentIndex((index) => Math.max(index - 1, 0))}
                    >
                      Previous item
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => removeItem(currentItem.id)}
                    >
                      Remove from queue
                    </button>
                    <button
                      type="button"
                      className="primary-button"
                      onClick={goToNextItem}
                    >
                      {currentIndex < items.length - 1 ? "Next item" : "Review complete"}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="empty-state">
                  <p>Start scanning to review the queue here.</p>
                </div>
              )}
            </div>
          </section>

          <div className="page-actions">
            <button
              type="button"
              className="primary-button"
              disabled={items.length === 0 || bulkPending}
              onClick={() => void submitAllItems()}
            >
              {bulkPending
                ? "Saving queued items..."
                : `Save all ${items.length} item${items.length === 1 ? "" : "s"}`}
            </button>
          </div>
        </div>
      </ModalShell>

      {isScannerOpen ? (
        <BarcodeScannerDialog
          mode="continuous"
          onClose={() => setIsScannerOpen(false)}
          onDetected={(barcode) => {
            queueBarcodes(barcode);
          }}
        />
      ) : null}
    </>
  );
}
