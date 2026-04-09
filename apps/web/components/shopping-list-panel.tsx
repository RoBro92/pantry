"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  PantryLocationSummary,
  ShoppingListDetailSummary,
  ShoppingListItemSummary,
  ShoppingListSummary,
} from "../lib/api-types";
import { appConfig } from "../lib/app-config";
import { deleteToApi, postToApi, putToApi, readApiErrorMessage } from "../lib/client-api";
import { formatQuantityValue, formatQuantityWithUnit } from "../lib/quantity-format";
import { ModalShell } from "./modal-shell";
import { PantryProductCreateDialog } from "./pantry-product-create-dialog";

type ShoppingListPanelProps = {
  householdExternalId: string;
  shoppingList: ShoppingListSummary;
  locations: PantryLocationSummary[];
  canAdminister: boolean;
};

type ActiveItemEditorState = {
  externalId: string;
  label: string;
  quantity: string;
  unit: string;
  note: string;
} | null;

function formatDateTime(value: string | null) {
  if (!value) {
    return "Not set";
  }
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function compareQuantities(left: string | null, right: string | null) {
  if (!left || !right) {
    return null;
  }
  const normalizedLeft = Number(formatQuantityValue(left));
  const normalizedRight = Number(formatQuantityValue(right));
  if (Number.isNaN(normalizedLeft) || Number.isNaN(normalizedRight)) {
    return null;
  }
  if (normalizedLeft === normalizedRight) {
    return 0;
  }
  return normalizedLeft < normalizedRight ? -1 : 1;
}

function isShortfall(item: ShoppingListItemSummary) {
  return (
    item.status === "purchased" &&
    item.quantity &&
    item.requested_quantity &&
    item.unit &&
    item.requested_unit &&
    item.unit === item.requested_unit &&
    compareQuantities(item.quantity, item.requested_quantity) === -1
  );
}

function isOverfill(item: ShoppingListItemSummary) {
  return (
    item.status === "purchased" &&
    item.quantity &&
    item.requested_quantity &&
    item.unit &&
    item.requested_unit &&
    item.unit === item.requested_unit &&
    compareQuantities(item.quantity, item.requested_quantity) === 1
  );
}

function isPurchasedNewProduct(item: ShoppingListItemSummary) {
  return item.status === "purchased" && item.product_external_id === null;
}

function buildRequestedSummary(item: ShoppingListItemSummary) {
  return formatQuantityWithUnit(item.requested_quantity, item.requested_unit, "No requested quantity");
}

function buildPurchasedSummary(item: ShoppingListItemSummary) {
  return formatQuantityWithUnit(item.quantity, item.unit, "No purchased quantity");
}

function buildNextStatus(item: ShoppingListItemSummary, nextQuantity: string, nextUnit: string, fallbackStatus: string) {
  if (
    item.requested_quantity &&
    item.requested_unit &&
    nextQuantity &&
    nextUnit &&
    item.requested_unit === nextUnit &&
    compareQuantities(nextQuantity, item.requested_quantity) === 0
  ) {
    return "purchased";
  }
  return fallbackStatus;
}

export function ShoppingListPanel({
  householdExternalId,
  shoppingList,
  locations,
  canAdminister,
}: ShoppingListPanelProps) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPendingListId, setSelectedPendingListId] = useState<string | null>(
    shoppingList.pending_lists[0]?.external_id ?? null,
  );
  const [activeItemEditor, setActiveItemEditor] = useState<ActiveItemEditorState>(null);
  const [finalizeListExternalId, setFinalizeListExternalId] = useState<string | null>(null);
  const [shortfallPromptOpen, setShortfallPromptOpen] = useState(false);
  const [productCreationQueue, setProductCreationQueue] = useState<ShoppingListItemSummary[]>([]);

  useEffect(() => {
    if (
      selectedPendingListId &&
      shoppingList.pending_lists.some((list) => list.external_id === selectedPendingListId)
    ) {
      return;
    }
    setSelectedPendingListId(shoppingList.pending_lists[0]?.external_id ?? null);
  }, [selectedPendingListId, shoppingList.pending_lists]);

  const activeItems = shoppingList.active_list.items.filter((item) => item.status === "open");
  const selectedPendingList =
    shoppingList.pending_lists.find((list) => list.external_id === selectedPendingListId) ??
    shoppingList.pending_lists[0] ??
    null;
  const shortfallItems = useMemo(
    () => selectedPendingList?.items.filter((item) => isShortfall(item)) ?? [],
    [selectedPendingList],
  );
  const newPurchasedItems = useMemo(
    () => selectedPendingList?.items.filter((item) => isPurchasedNewProduct(item)) ?? [],
    [selectedPendingList],
  );
  const productCreationItem = productCreationQueue[0] ?? null;

  async function handleAddItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    setPending(true);
    setError(null);

    try {
      await postToApi(`/api/households/${householdExternalId}/shopping-list/items`, {
        label: String(formData.get("label") ?? ""),
        quantity: String(formData.get("quantity") ?? "").trim() || null,
        unit: String(formData.get("unit") ?? "").trim() || null,
        note: String(formData.get("note") ?? "").trim() || null,
        source_type: "manual",
      });
      form.reset();
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not add shopping list item.",
      );
    } finally {
      setPending(false);
    }
  }

  async function saveActiveItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeItemEditor) {
      return;
    }
    const formData = new FormData(event.currentTarget);
    setPending(true);
    setError(null);

    try {
      await putToApi(`/api/households/${householdExternalId}/shopping-list/items/${activeItemEditor.externalId}`, {
        quantity: String(formData.get("quantity") ?? "").trim() || null,
        unit: String(formData.get("unit") ?? "").trim() || null,
        note: String(formData.get("note") ?? "").trim() || null,
      });
      setActiveItemEditor(null);
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not update this shopping item.",
      );
    } finally {
      setPending(false);
    }
  }

  async function removeActiveItem(itemExternalId: string) {
    setPending(true);
    setError(null);
    try {
      await deleteToApi(`/api/households/${householdExternalId}/shopping-list/items/${itemExternalId}`);
      setActiveItemEditor(null);
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not remove this shopping item.",
      );
    } finally {
      setPending(false);
    }
  }

  async function savePendingItem(event: FormEvent<HTMLFormElement>, item: ShoppingListItemSummary) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const nextQuantity = String(formData.get("quantity") ?? "").trim();
    const nextUnit = String(formData.get("unit") ?? "").trim();
    const nextStatus = buildNextStatus(
      item,
      nextQuantity,
      nextUnit,
      String(formData.get("status") ?? item.status),
    );
    setPending(true);
    setError(null);

    try {
      await putToApi(`/api/households/${householdExternalId}/shopping-list/items/${item.external_id}`, {
        status: nextStatus,
        quantity: nextQuantity || null,
        unit: nextUnit || null,
        note: String(formData.get("note") ?? "").trim() || null,
        pantry_location_external_id: String(formData.get("pantry_location_external_id") ?? "").trim() || null,
      });
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not update this shopping item.",
      );
    } finally {
      setPending(false);
    }
  }

  async function handleExport() {
    setPending(true);
    setError(null);
    try {
      const response = await fetch(
        `${appConfig.apiBaseUrl}/api/households/${householdExternalId}/shopping-list/export`,
        {
          method: "POST",
          credentials: "include",
        },
      );
      if (!response.ok) {
        throw new Error(await readApiErrorMessage(response, "Could not export the shopping list."));
      }

      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") ?? "";
      const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? "shopping-list.txt";
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not export the shopping list.",
      );
    } finally {
      setPending(false);
    }
  }

  async function mergePendingLists() {
    setPending(true);
    setError(null);
    try {
      await postToApi(`/api/households/${householdExternalId}/shopping-list/pending/merge`, {});
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not merge pending lists.",
      );
    } finally {
      setPending(false);
    }
  }

  async function returnPendingListToActive(listExternalId: string) {
    setPending(true);
    setError(null);
    try {
      await postToApi(
        `/api/households/${householdExternalId}/shopping-list/pending/${listExternalId}/return-to-active`,
        {},
      );
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not move this list back into the active list.",
      );
    } finally {
      setPending(false);
    }
  }

  async function finalizePendingList(listExternalId: string, returnShortfallsToActive: boolean) {
    setPending(true);
    setError(null);
    try {
      await postToApi(
        `/api/households/${householdExternalId}/shopping-list/pending/${listExternalId}/finalize`,
        { return_shortfalls_to_active: returnShortfallsToActive },
      );
      setFinalizeListExternalId(null);
      setShortfallPromptOpen(false);
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not finish reconciling this list.",
      );
    } finally {
      setPending(false);
    }
  }

  function queueFinalize(list: ShoppingListDetailSummary) {
    setFinalizeListExternalId(list.external_id);
    setError(null);

    if (newPurchasedItems.length > 0) {
      if (!canAdminister) {
        setError("A household admin needs to create Pantry products for new purchased items before finishing.");
        setFinalizeListExternalId(null);
        return;
      }
      setProductCreationQueue(newPurchasedItems);
      return;
    }

    if (shortfallItems.length > 0) {
      setShortfallPromptOpen(true);
      return;
    }

    void finalizePendingList(list.external_id, false);
  }

  async function attachCreatedProduct(productExternalId: string, item: ShoppingListItemSummary) {
    await postToApi(
      `/api/households/${householdExternalId}/shopping-list/items/${item.external_id}/attach-product`,
      {
        product_external_id: productExternalId,
      },
    );
    await putToApi(`/api/households/${householdExternalId}/shopping-list/items/${item.external_id}`, {
      status: "purchased",
      quantity: item.quantity ?? item.requested_quantity ?? "1",
      unit: item.unit ?? item.requested_unit ?? "count",
      note: item.note,
      pantry_location_external_id: item.pantry_location_external_id,
    });
  }

  async function handleProductCreationCompleted(productExternalId: string, item: ShoppingListItemSummary) {
    await attachCreatedProduct(productExternalId, item);
    const remainingItems = productCreationQueue.filter((candidate) => candidate.external_id !== item.external_id);
    setProductCreationQueue(remainingItems);

    if (remainingItems.length > 0) {
      return;
    }

    if (finalizeListExternalId && shortfallItems.length > 0) {
      setShortfallPromptOpen(true);
      return;
    }

    if (finalizeListExternalId) {
      await finalizePendingList(finalizeListExternalId, false);
    }
  }

  return (
    <>
      <div className="stack">
        <section className="panel">
          <div className="inventory-header">
            <div className="stack compact-stack">
              <p className="eyebrow">Shopping List</p>
              <h1>Household shopping</h1>
              <p className="section-copy">
                Keep the active list dense and editable, then reconcile each trip back into Pantry stock.
              </p>
            </div>
            <div className="tag-row">
              <span className="pill">{shoppingList.active_list.unresolved_item_count} active</span>
              <span className="pill">{shoppingList.pending_lists.length} awaiting purchase</span>
              <span className="pill">{shoppingList.history_lists.length} recent trips</span>
            </div>
          </div>

          <div className="page-actions">
            <button
              type="button"
              className="primary-button"
              disabled={pending || activeItems.length === 0}
              onClick={() => void handleExport()}
            >
              {pending ? "Working..." : "Export checklist (.txt)"}
            </button>
            <button
              type="button"
              className="ghost-button"
              disabled={pending || shoppingList.pending_lists.length < 2}
              onClick={() => void mergePendingLists()}
            >
              Merge pending lists
            </button>
          </div>

          <form className="shopping-add-form shopping-add-form-compact" onSubmit={handleAddItem}>
            <label className="field shopping-item-name">
              <span>Add item</span>
              <input name="label" placeholder="Milk" required />
            </label>
            <label className="field">
              <span>Qty</span>
              <input name="quantity" type="number" min="0.001" step="0.001" placeholder="1" />
            </label>
            <label className="field">
              <span>Unit</span>
              <input name="unit" placeholder="bottle" />
            </label>
            <label className="field shopping-item-note">
              <span>Note</span>
              <input name="note" placeholder="Semi-skimmed" />
            </label>
            <button type="submit" className="primary-button" disabled={pending}>
              {pending ? "Saving..." : "Add item"}
            </button>
          </form>

          {error ? <p className="error-text">{error}</p> : null}
        </section>

        <section className="content-grid shopping-columns">
          <article className="panel">
            <div className="stack compact-stack">
              <p className="eyebrow">Active</p>
              <h2 className="section-heading">{shoppingList.active_list.name}</h2>
              <p className="helper-text">
                Edit quantities and notes here before you export the next trip.
              </p>
            </div>
            {activeItems.length === 0 ? (
              <div className="empty-state">
                <p>No active shopping items right now.</p>
              </div>
            ) : (
              <div className="shopping-item-list shopping-item-list-dense">
                {activeItems.map((item) => (
                  <article key={item.external_id} className="shopping-item-card shopping-item-row">
                    <div className="shopping-item-row-main">
                      <div className="stack compact-stack">
                        <strong>{item.product_name ?? item.label}</strong>
                        <p className="helper-text">
                          {formatQuantityWithUnit(item.quantity, item.unit)}
                          {item.note ? ` · ${item.note}` : ""}
                        </p>
                      </div>
                      <div className="tag-row">
                        <span className="pill">{item.source_type.replaceAll("_", " ")}</span>
                        <button
                          type="button"
                          className="ghost-button compact-button"
                          onClick={() =>
                            setActiveItemEditor({
                              externalId: item.external_id,
                              label: item.product_name ?? item.label,
                              quantity: item.quantity ?? "",
                              unit: item.unit ?? "",
                              note: item.note ?? "",
                            })
                          }
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="ghost-button compact-button"
                          onClick={() => void removeActiveItem(item.external_id)}
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </article>

          <article className="panel">
            <div className="stack compact-stack">
              <p className="eyebrow">Awaiting Purchase</p>
              <h2 className="section-heading">Pending trips</h2>
              <p className="helper-text">
                Exported lists stay here until you cancel, merge, or reconcile them.
              </p>
            </div>

            {shoppingList.pending_lists.length === 0 ? (
              <div className="empty-state">
                <p>Export a checklist to start an awaiting-purchase list.</p>
              </div>
            ) : (
              <div className="shopping-item-list shopping-item-list-dense">
                {shoppingList.pending_lists.map((list) => (
                  <article
                    key={list.external_id}
                    className={`shopping-item-card${selectedPendingList?.external_id === list.external_id ? " is-selected" : ""}`}
                  >
                    <div className="shopping-item-row-main">
                      <div className="stack compact-stack">
                        <strong>{list.name}</strong>
                        <p className="helper-text">
                          {list.unresolved_item_count} unresolved · {list.purchased_item_count} purchased
                        </p>
                        <p className="helper-text">Exported {formatDateTime(list.generated_at)}</p>
                      </div>
                      <button
                        type="button"
                        className="ghost-button compact-button"
                        onClick={() => setSelectedPendingListId(list.external_id)}
                      >
                        {selectedPendingList?.external_id === list.external_id ? "Open" : "Review"}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </article>
        </section>

        {selectedPendingList ? (
          <section className="panel">
            <div className="inventory-header">
              <div className="stack compact-stack">
                <p className="eyebrow">Reconcile</p>
                <h2>{selectedPendingList.name}</h2>
                <p className="helper-text">
                  Save purchased quantities, reuse the last known pantry location where possible, and return any shortfall if needed when you finish.
                </p>
              </div>
              <div className="page-actions">
                <button
                  type="button"
                  className="ghost-button"
                  disabled={pending}
                  onClick={() => void returnPendingListToActive(selectedPendingList.external_id)}
                >
                  Move back to active list
                </button>
                <button
                  type="button"
                  className="primary-button"
                  disabled={pending}
                  onClick={() => queueFinalize(selectedPendingList)}
                >
                  Finish reconciliation
                </button>
              </div>
            </div>

            <div className="shopping-reconcile-list shopping-reconcile-list-compact">
              {selectedPendingList.items.map((item) => (
                <form
                  key={item.external_id}
                  className="shopping-reconcile-row shopping-reconcile-row-compact"
                  onSubmit={(event) => void savePendingItem(event, item)}
                >
                  <div className="stack compact-stack">
                    <div className="shopping-row-heading">
                      <strong>{item.product_name ?? item.label}</strong>
                      <div className="tag-row">
                        <span className="pill">{item.status.replaceAll("_", " ")}</span>
                        {item.product_external_id === null ? <span className="pill is-warning">New product</span> : null}
                        {isShortfall(item) ? <span className="pill is-warning">Shortfall</span> : null}
                        {isOverfill(item) ? <span className="pill is-success">Extra bought</span> : null}
                      </div>
                    </div>
                    <p className="helper-text">
                      Requested: {buildRequestedSummary(item)} · Purchased: {buildPurchasedSummary(item)}
                    </p>
                    <p className="helper-text">
                      Added {formatDateTime(item.created_at)}
                      {item.purchased_at ? ` · Purchased ${formatDateTime(item.purchased_at)}` : ""}
                      {item.not_purchased_at ? ` · Not purchased ${formatDateTime(item.not_purchased_at)}` : ""}
                    </p>
                  </div>

                  <label className="field compact">
                    <span>Status</span>
                    <select name="status" defaultValue={item.status}>
                      <option value="awaiting_purchase">Awaiting purchase</option>
                      <option value="purchased">Purchased</option>
                      <option value="not_purchased">Not purchased</option>
                    </select>
                  </label>
                  <label className="field compact">
                    <span>Purchased qty</span>
                    <input
                      name="quantity"
                      type="number"
                      min="0.001"
                      step="0.001"
                      defaultValue={item.quantity ?? item.requested_quantity ?? ""}
                    />
                  </label>
                  <label className="field compact">
                    <span>Unit</span>
                    <input name="unit" defaultValue={item.unit ?? item.requested_unit ?? ""} />
                  </label>
                  <label className="field compact">
                    <span>Pantry location</span>
                    <select name="pantry_location_external_id" defaultValue={item.pantry_location_external_id ?? ""}>
                      <option value="">Choose later</option>
                      {locations.map((location) => (
                        <option key={location.external_id} value={location.external_id}>
                          {location.location_group_name} / {location.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field compact shopping-reconcile-note">
                    <span>Note</span>
                    <input name="note" defaultValue={item.note ?? ""} />
                  </label>
                  <div className="shopping-reconcile-actions">
                    <button type="submit" className="ghost-button compact-button" disabled={pending}>
                      Save
                    </button>
                  </div>
                </form>
              ))}
            </div>
          </section>
        ) : null}

        <section className="panel">
          <div className="stack compact-stack">
            <p className="eyebrow">Recent trips</p>
            <h2 className="section-heading">History</h2>
          </div>
          {shoppingList.history_lists.length === 0 ? (
            <div className="empty-state">
              <p>Reconciled, returned, and merged lists will appear here.</p>
            </div>
          ) : (
            <div className="shopping-item-list shopping-item-list-dense">
              {shoppingList.history_lists.map((list) => (
                <article key={list.external_id} className="shopping-item-card is-muted">
                  <div className="shopping-item-row-main">
                    <div className="stack compact-stack">
                      <strong>{list.name}</strong>
                      <p className="helper-text">
                        {list.lifecycle_state.replaceAll("_", " ")} · {list.item_count} items
                      </p>
                      <p className="helper-text">
                        {list.reconciled_at ? `Finished ${formatDateTime(list.reconciled_at)}` : "Recently updated"}
                      </p>
                    </div>
                    <div className="tag-row">
                      {list.purchased_item_count > 0 ? <span className="pill">{list.purchased_item_count} purchased</span> : null}
                      {list.not_purchased_item_count > 0 ? <span className="pill">{list.not_purchased_item_count} returned</span> : null}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>

      {activeItemEditor ? (
        <ModalShell
          title={`Edit ${activeItemEditor.label}`}
          description="Adjust the quantity, unit, or note for this active shopping item."
          onClose={() => setActiveItemEditor(null)}
        >
          <form className="stack" onSubmit={saveActiveItem}>
            <div className="content-grid">
              <label className="field">
                <span>Quantity</span>
                <input
                  name="quantity"
                  type="number"
                  min="0.001"
                  step="0.001"
                  defaultValue={activeItemEditor.quantity}
                />
              </label>
              <label className="field">
                <span>Unit</span>
                <input name="unit" defaultValue={activeItemEditor.unit} />
              </label>
            </div>
            <label className="field">
              <span>Note</span>
              <input name="note" defaultValue={activeItemEditor.note} />
            </label>
            <div className="page-actions">
              <button type="submit" className="primary-button" disabled={pending}>
                {pending ? "Saving..." : "Save item"}
              </button>
              <button
                type="button"
                className="ghost-button"
                disabled={pending}
                onClick={() => void removeActiveItem(activeItemEditor.externalId)}
              >
                Remove
              </button>
            </div>
          </form>
        </ModalShell>
      ) : null}

      {shortfallPromptOpen && finalizeListExternalId ? (
        <ModalShell
          title="Return shortfall to active list?"
          description={`${shortfallItems.length} purchased item${shortfallItems.length === 1 ? "" : "s"} came back short. Decide whether the missing amount should go back onto the active shopping list.`}
          onClose={() => {
            setShortfallPromptOpen(false);
            setFinalizeListExternalId(null);
          }}
        >
          <div className="stack">
            <div className="page-actions">
              <button
                type="button"
                className="primary-button"
                disabled={pending}
                onClick={() => void finalizePendingList(finalizeListExternalId, true)}
              >
                Return shortfall
              </button>
              <button
                type="button"
                className="ghost-button"
                disabled={pending}
                onClick={() => void finalizePendingList(finalizeListExternalId, false)}
              >
                Keep closed
              </button>
            </div>
          </div>
        </ModalShell>
      ) : null}

      {productCreationItem ? (
        <PantryProductCreateDialog
          householdExternalId={householdExternalId}
          initialName={productCreationItem.label}
          initialUnit={productCreationItem.unit ?? productCreationItem.requested_unit ?? "count"}
          quantitySummary={buildPurchasedSummary(productCreationItem)}
          note={productCreationItem.note}
          onCompleted={async (product) => {
            await handleProductCreationCompleted(product.external_id, productCreationItem);
          }}
          onClose={() => {
            setProductCreationQueue([]);
            setFinalizeListExternalId(null);
          }}
        />
      ) : null}
    </>
  );
}
