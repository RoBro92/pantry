"use client";

import Link from "next/link";
import { FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
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
import { PantryProductDialog } from "./pantry-product-create-dialog";
import { ShoppingTripFinishDialog } from "./shopping-trip-finish-dialog";

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

type PendingItemDraft = {
  quantity: string;
  unit: string;
  note: string;
  pantryLocationExternalId: string;
};

type QueuedBulkAction = {
  action: "reconcile_selected";
  itemIds: string[];
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

function buildRequestedSummary(item: ShoppingListItemSummary) {
  return formatQuantityWithUnit(item.requested_quantity, item.requested_unit, "No requested quantity");
}

function buildPurchasedSummary(item: ShoppingListItemSummary, draft?: PendingItemDraft) {
  return formatQuantityWithUnit(
    draft?.quantity ?? item.quantity,
    draft?.unit ?? item.unit,
    "No purchased quantity",
  );
}

function createPendingItemDraft(item: ShoppingListItemSummary): PendingItemDraft {
  return {
    quantity: item.quantity ?? item.requested_quantity ?? "",
    unit: item.unit ?? item.requested_unit ?? "",
    note: item.note ?? "",
    pantryLocationExternalId: item.pantry_location_external_id ?? "",
  };
}

function sortPendingItems(items: ShoppingListItemSummary[]) {
  return [...items].sort((left, right) => {
    const leftGroup = `${left.pantry_location_group_name ?? ""}|${left.pantry_location_name ?? ""}`;
    const rightGroup = `${right.pantry_location_group_name ?? ""}|${right.pantry_location_name ?? ""}`;
    return leftGroup.localeCompare(rightGroup) || (left.product_name ?? left.label).localeCompare(right.product_name ?? right.label);
  });
}

function getPendingItemBadge(item: ShoppingListItemSummary) {
  if (item.product_external_id === null) {
    return { label: "New product", className: "pill is-warning" };
  }
  return { label: "Pantry product", className: "pill is-success" };
}

function buildLocationSummary(item: ShoppingListItemSummary, locations: PantryLocationSummary[], draft: PendingItemDraft) {
  const selectedLocation =
    locations.find((location) => location.external_id === draft.pantryLocationExternalId) ?? null;
  if (selectedLocation) {
    return `${selectedLocation.location_group_name} / ${selectedLocation.name}`;
  }
  if (item.pantry_location_name) {
    return `${item.pantry_location_group_name} / ${item.pantry_location_name}`;
  }
  return "Choose later";
}

type ShoppingIconButtonProps = {
  label: string;
  intent?: "default" | "danger" | "success";
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
};

function ShoppingIconButton({
  label,
  intent = "default",
  onClick,
  disabled = false,
  children,
}: ShoppingIconButtonProps) {
  const className =
    intent === "danger"
      ? "shopping-icon-button is-danger"
      : intent === "success"
        ? "shopping-icon-button is-success"
        : "shopping-icon-button";

  return (
    <button
      type="button"
      className={className}
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
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
  const [selectedItemIds, setSelectedItemIds] = useState<string[]>([]);
  const [expandedItemIds, setExpandedItemIds] = useState<string[]>([]);
  const [pendingItemDrafts, setPendingItemDrafts] = useState<Record<string, PendingItemDraft>>({});
  const [productCreationQueue, setProductCreationQueue] = useState<ShoppingListItemSummary[]>([]);
  const [queuedBulkAction, setQueuedBulkAction] = useState<QueuedBulkAction>(null);
  const [isFinishTripDialogOpen, setIsFinishTripDialogOpen] = useState(false);

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
  const unresolvedPendingItems = useMemo(
    () =>
      sortPendingItems(
        selectedPendingList?.items.filter((item) => item.status === "awaiting_purchase") ?? [],
      ),
    [selectedPendingList],
  );
  const handledPendingItemCount = (selectedPendingList?.items.length ?? 0) - unresolvedPendingItems.length;
  const selectedCount = selectedItemIds.length;
  const allSelected = unresolvedPendingItems.length > 0 && selectedCount === unresolvedPendingItems.length;
  const productCreationItem = productCreationQueue[0] ?? null;

  useEffect(() => {
    setPendingItemDrafts((current) => {
      const nextDrafts = { ...current };
      const unresolvedIds = new Set(unresolvedPendingItems.map((item) => item.external_id));
      unresolvedPendingItems.forEach((item) => {
        if (!nextDrafts[item.external_id]) {
          nextDrafts[item.external_id] = createPendingItemDraft(item);
        }
      });
      Object.keys(nextDrafts).forEach((itemId) => {
        if (!unresolvedIds.has(itemId)) {
          delete nextDrafts[itemId];
        }
      });
      return nextDrafts;
    });
  }, [unresolvedPendingItems]);

  useEffect(() => {
    const unresolvedIds = new Set(unresolvedPendingItems.map((item) => item.external_id));
    setSelectedItemIds((current) => current.filter((itemId) => unresolvedIds.has(itemId)));
  }, [unresolvedPendingItems]);

  useEffect(() => {
    const unresolvedIds = new Set(unresolvedPendingItems.map((item) => item.external_id));
    setExpandedItemIds((current) => current.filter((itemId) => unresolvedIds.has(itemId)));
  }, [unresolvedPendingItems]);

  useEffect(() => {
    if (selectedPendingList) {
      return;
    }
    setIsFinishTripDialogOpen(false);
  }, [selectedPendingList]);

  function updatePendingDraft(itemExternalId: string, patch: Partial<PendingItemDraft>) {
    setPendingItemDrafts((current) => ({
      ...current,
      [itemExternalId]: {
        ...(current[itemExternalId] ?? createPendingItemDraft(
          unresolvedPendingItems.find((item) => item.external_id === itemExternalId)!,
        )),
        ...patch,
      },
    }));
  }

  function toggleItemSelection(itemExternalId: string) {
    setSelectedItemIds((current) =>
      current.includes(itemExternalId)
        ? current.filter((candidate) => candidate !== itemExternalId)
        : [...current, itemExternalId],
    );
  }

  function setAllSelected(nextSelected: boolean) {
    setSelectedItemIds(nextSelected ? unresolvedPendingItems.map((item) => item.external_id) : []);
  }

  function toggleExpanded(itemExternalId: string) {
    setExpandedItemIds((current) =>
      current.includes(itemExternalId)
        ? current.filter((candidate) => candidate !== itemExternalId)
        : [...current, itemExternalId],
    );
  }

  function getDraftForItem(item: ShoppingListItemSummary) {
    return pendingItemDrafts[item.external_id] ?? createPendingItemDraft(item);
  }

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

  async function movePendingListBackToActive(listExternalId: string) {
    setPending(true);
    setError(null);
    try {
      await postToApi(
        `/api/households/${householdExternalId}/shopping-list/pending/${listExternalId}/return-to-active`,
        {},
      );
      setSelectedItemIds([]);
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not move this list back into the active list.",
      );
    } finally {
      setPending(false);
    }
  }

  function validateReconcileSelection(selectedItems: ShoppingListItemSummary[]) {
    for (const item of selectedItems) {
      const draft = getDraftForItem(item);
      const normalizedQuantity = Number(formatQuantityValue(draft.quantity));
      if (!draft.quantity.trim() || Number.isNaN(normalizedQuantity) || normalizedQuantity <= 0) {
        throw new Error("Purchased quantity must be greater than zero. Return or delete items that were not bought.");
      }
      if (!draft.unit.trim()) {
        throw new Error(`Choose a purchased unit for ${item.product_name ?? item.label}.`);
      }
    }
  }

  function buildBulkPayloadItems(itemIds: string[]) {
    return itemIds.map((itemId) => {
      const item = unresolvedPendingItems.find((candidate) => candidate.external_id === itemId);
      if (!item) {
        throw new Error("One or more selected shopping items are no longer available.");
      }
      const draft = getDraftForItem(item);
      return {
        item_external_id: item.external_id,
        quantity: draft.quantity.trim() || null,
        unit: draft.unit.trim() || null,
        note: draft.note,
        pantry_location_external_id: draft.pantryLocationExternalId || null,
      };
    });
  }

  async function postBulkAction(action: "reconcile_selected" | "return_selected" | "delete_selected", itemIds: string[]) {
    if (!selectedPendingList) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      await postToApi(
        `/api/households/${householdExternalId}/shopping-list/pending/${selectedPendingList.external_id}/bulk`,
        {
          action,
          items: buildBulkPayloadItems(itemIds),
        },
      );
      setSelectedItemIds((current) => current.filter((itemId) => !itemIds.includes(itemId)));
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not update the selected shopping items.",
      );
    } finally {
      setPending(false);
    }
  }

  async function runBulkAction(action: "reconcile_selected" | "return_selected" | "delete_selected", itemIds?: string[]) {
    const targetItemIds = itemIds ?? selectedItemIds;
    if (!selectedPendingList || targetItemIds.length === 0) {
      setError("Select at least one unresolved shopping item first.");
      return;
    }

    const selectedItems = targetItemIds
      .map((itemId) => unresolvedPendingItems.find((item) => item.external_id === itemId))
      .filter((item): item is ShoppingListItemSummary => Boolean(item));

    try {
      if (action === "reconcile_selected") {
        validateReconcileSelection(selectedItems);
        const newProducts = selectedItems.filter((item) => item.product_external_id === null);
        if (newProducts.length > 0) {
          if (!canAdminister) {
            throw new Error("A household admin must create Pantry products for new purchased items before they can be reconciled.");
          }
          setQueuedBulkAction({ action, itemIds: targetItemIds });
          setProductCreationQueue(newProducts);
          return;
        }
      }

      await postBulkAction(action, targetItemIds);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not process the selected shopping items.");
    }
  }

  async function finalizeSelectedPendingList(unresolvedAction?: "return_to_active" | "delete") {
    if (!selectedPendingList) {
      return;
    }

    setPending(true);
    setError(null);
    try {
      await postToApi(
        `/api/households/${householdExternalId}/shopping-list/pending/${selectedPendingList.external_id}/finalize`,
        {
          return_shortfalls_to_active: false,
          unresolved_action: unresolvedAction ?? null,
        },
      );
      setSelectedItemIds([]);
      setIsFinishTripDialogOpen(false);
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not finish this shopping trip.",
      );
    } finally {
      setPending(false);
    }
  }

  async function finishSelectedPendingList() {
    if (!selectedPendingList) {
      return;
    }
    if (unresolvedPendingItems.length > 0) {
      setIsFinishTripDialogOpen(true);
      return;
    }
    await finalizeSelectedPendingList();
  }

  async function attachCreatedProduct(productExternalId: string, itemExternalId: string) {
    await postToApi(
      `/api/households/${householdExternalId}/shopping-list/items/${itemExternalId}/attach-product`,
      {
        product_external_id: productExternalId,
      },
    );
  }

  async function handleProductCreationCompleted(productExternalId: string, item: ShoppingListItemSummary) {
    await attachCreatedProduct(productExternalId, item.external_id);
    const remainingItems = productCreationQueue.filter((candidate) => candidate.external_id !== item.external_id);
    setProductCreationQueue(remainingItems);

    if (remainingItems.length === 0 && queuedBulkAction) {
      const queuedItemIds = queuedBulkAction.itemIds;
      setQueuedBulkAction(null);
      await postBulkAction(queuedBulkAction.action, queuedItemIds);
      return;
    }

    router.refresh();
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
                Add items manually or via Pantry to your shopping list, generate a printable list, and reconcile on purchase.
              </p>
            </div>
            <div className="tag-row">
              <span className="pill">{shoppingList.active_list.unresolved_item_count} active</span>
              <span className="pill">{shoppingList.pending_lists.length} awaiting purchase</span>
              <Link
                href={`/app/households/${householdExternalId}/shopping-list/history`}
                className="secondary-link compact-link"
              >
                Shopping history
              </Link>
            </div>
          </div>

          <div className="page-actions">
            <button
              type="button"
              className="primary-button"
              disabled={pending || activeItems.length === 0}
              onClick={() => void handleExport()}
            >
              {pending ? "Working..." : "Export List (.txt)"}
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
                Review one trip at a time, then bulk reconcile what was bought as planned.
              </p>
            </div>

            {shoppingList.pending_lists.length === 0 ? (
              <div className="empty-state">
                <p>Export a checklist to start an awaiting-purchase trip.</p>
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
                          {list.unresolved_item_count} unresolved · {list.purchased_item_count} purchased · {list.not_purchased_item_count} returned
                        </p>
                        <p className="helper-text">Exported {formatDateTime(list.generated_at)}</p>
                      </div>
                      <button
                        type="button"
                        className="ghost-button compact-button"
                        onClick={() => setSelectedPendingListId(list.external_id)}
                      >
                        {selectedPendingList?.external_id === list.external_id ? "Selected" : "Review"}
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
                  Tick rows bought as planned, edit exceptions inline, and reconcile the selection in one pass.
                </p>
              </div>
              <div className="page-actions">
                <button
                  type="button"
                  className="ghost-button"
                  disabled={pending}
                  onClick={() => void movePendingListBackToActive(selectedPendingList.external_id)}
                >
                  Move whole trip back to active list
                </button>
                <button
                  type="button"
                  className="primary-button"
                  disabled={pending}
                  onClick={() => void finishSelectedPendingList()}
                >
                  Finish trip
                </button>
              </div>
            </div>

            <div className="shopping-bulk-toolbar">
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(event) => setAllSelected(event.target.checked)}
                />
                <span>
                  {selectedCount > 0 ? `${selectedCount} selected` : "Select all visible rows"}
                </span>
              </label>
              <div className="page-actions">
                <button
                  type="button"
                  className="primary-button compact-button"
                  disabled={pending || selectedCount === 0}
                  onClick={() => void runBulkAction("reconcile_selected")}
                >
                  Reconcile selected
                </button>
                <button
                  type="button"
                  className="ghost-button compact-button"
                  disabled={pending || selectedCount === 0}
                  onClick={() => void runBulkAction("return_selected")}
                >
                  Return selected to shopping list
                </button>
                <button
                  type="button"
                  className="ghost-button compact-button"
                  disabled={pending || selectedCount === 0}
                  onClick={() => void runBulkAction("delete_selected")}
                >
                  Delete selected
                </button>
              </div>
            </div>

            {handledPendingItemCount > 0 ? (
              <p className="helper-text">
                {handledPendingItemCount} handled item{handledPendingItemCount === 1 ? "" : "s"} are already tucked away from this view. Once the remaining items are dealt with, the trip will move into history automatically.
              </p>
            ) : null}

            {unresolvedPendingItems.length === 0 ? (
              <div className="empty-state">
                <p>This trip has no unresolved items left. It will move into shopping history automatically.</p>
              </div>
            ) : (
              <div className="shopping-reconcile-table">
                <div className="shopping-reconcile-table-heading" aria-hidden="true">
                  <span>Select</span>
                  <span>Product</span>
                  <span>Purchased qty</span>
                  <span>Unit</span>
                  <span>Pantry location</span>
                  <span>Actions</span>
                </div>

                {unresolvedPendingItems.map((item) => {
                  const draft = getDraftForItem(item);
                  const isSelected = selectedItemIds.includes(item.external_id);
                  const isExpanded = expandedItemIds.includes(item.external_id);
                  const badge = getPendingItemBadge(item);
                  const locationSummary = buildLocationSummary(item, locations, draft);
                  return (
                    <article
                      key={item.external_id}
                      className={`shopping-reconcile-row shopping-reconcile-row-dense${isSelected ? " is-selected" : ""}`}
                      data-testid={`shopping-reconcile-row-${item.external_id}`}
                    >
                      <div className="shopping-reconcile-row-mainline">
                        <label className="checkbox-row shopping-reconcile-checkbox">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleItemSelection(item.external_id)}
                          />
                          <span className="sr-only">Select {item.product_name ?? item.label}</span>
                        </label>
                        <div className="stack compact-stack shopping-reconcile-title">
                          <strong>{item.product_name ?? item.label}</strong>
                          <div className="tag-row">
                            <span className={badge.className}>{badge.label}</span>
                          </div>
                        </div>

                        <label className="field compact shopping-reconcile-inline-field">
                          <span className="sr-only">Purchased qty</span>
                          <input
                            type="number"
                            min="0.001"
                            step="0.001"
                            value={draft.quantity}
                            onChange={(event) =>
                              updatePendingDraft(item.external_id, { quantity: event.target.value })
                            }
                          />
                        </label>
                        <label className="field compact shopping-reconcile-inline-field">
                          <span className="sr-only">Unit</span>
                          <input
                            value={draft.unit}
                            onChange={(event) =>
                              updatePendingDraft(item.external_id, { unit: event.target.value })
                            }
                          />
                        </label>
                        <label className="field compact shopping-reconcile-inline-field shopping-reconcile-location-field">
                          <span className="sr-only">Pantry location</span>
                          <select
                            value={draft.pantryLocationExternalId}
                            onChange={(event) =>
                              updatePendingDraft(item.external_id, {
                                pantryLocationExternalId: event.target.value,
                              })
                            }
                          >
                            <option value="">Choose later</option>
                            {locations.map((location) => (
                              <option key={location.external_id} value={location.external_id}>
                                {location.location_group_name} / {location.name}
                              </option>
                            ))}
                          </select>
                        </label>

                        <div className="shopping-reconcile-actions">
                          <ShoppingIconButton
                            label="Delete item"
                            intent="danger"
                            disabled={pending}
                            onClick={() => void runBulkAction("delete_selected", [item.external_id])}
                          >
                            <svg viewBox="0 0 20 20" aria-hidden="true">
                              <path d="M6.5 3.5h7l.5 2H17v1.5H3V5.5h3zM7 8.5v6M10 8.5v6M13 8.5v6M5.5 7h9l-.6 9.2a1 1 0 0 1-1 .8H7.1a1 1 0 0 1-1-.8z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
                            </svg>
                          </ShoppingIconButton>
                          <ShoppingIconButton
                            label="Return item to shopping list"
                            disabled={pending}
                            onClick={() => void runBulkAction("return_selected", [item.external_id])}
                          >
                            <svg viewBox="0 0 20 20" aria-hidden="true">
                              <path d="M7 6 3.5 9.5 7 13M4 9.5h7a4.5 4.5 0 1 1 0 9" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" />
                            </svg>
                          </ShoppingIconButton>
                          <ShoppingIconButton
                            label="Reconcile item"
                            intent="success"
                            disabled={pending}
                            onClick={() => void runBulkAction("reconcile_selected", [item.external_id])}
                          >
                            <svg viewBox="0 0 20 20" aria-hidden="true">
                              <path d="M10 4v12M4 10h12" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
                              <path d="m6.5 10.5 2.2 2.2 4.8-5.4" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.4" />
                            </svg>
                          </ShoppingIconButton>
                          <ShoppingIconButton
                            label={isExpanded ? "Collapse details" : "Expand details"}
                            onClick={() => toggleExpanded(item.external_id)}
                          >
                            <svg
                              viewBox="0 0 20 20"
                              aria-hidden="true"
                              className={isExpanded ? "is-expanded" : ""}
                            >
                              <path d="m5.5 7.5 4.5 4.5 4.5-4.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
                            </svg>
                          </ShoppingIconButton>
                        </div>
                      </div>

                      {isExpanded ? (
                        <div className="shopping-reconcile-details">
                          <div className="shopping-reconcile-detail-grid">
                            <div className="stack compact-stack">
                              <span className="shopping-detail-label">Requested</span>
                              <span>{buildRequestedSummary(item)}</span>
                            </div>
                            <div className="stack compact-stack">
                              <span className="shopping-detail-label">Planned reconcile</span>
                              <span>{buildPurchasedSummary(item, draft)}</span>
                            </div>
                            <div className="stack compact-stack">
                              <span className="shopping-detail-label">Pantry location</span>
                              <span>{locationSummary}</span>
                            </div>
                            <div className="stack compact-stack">
                              <span className="shopping-detail-label">Source</span>
                              <span>{item.source_type.replaceAll("_", " ")}</span>
                            </div>
                          </div>

                          <label className="field compact shopping-reconcile-note-field">
                            <span>Notes</span>
                            <input
                              value={draft.note}
                              onChange={(event) =>
                                updatePendingDraft(item.external_id, { note: event.target.value })
                              }
                              placeholder="Optional purchased note"
                            />
                          </label>

                          <div className="page-actions shopping-reconcile-detail-actions">
                            <button
                              type="button"
                              className="ghost-button compact-button"
                              onClick={() =>
                                updatePendingDraft(item.external_id, {
                                  quantity: item.requested_quantity ?? item.quantity ?? "",
                                  unit: item.requested_unit ?? item.unit ?? draft.unit,
                                })
                              }
                            >
                              Use requested amount
                            </button>
                            {item.product_external_id === null ? (
                              canAdminister ? (
                                <button
                                  type="button"
                                  className="ghost-button compact-button"
                                  onClick={() => {
                                    setQueuedBulkAction(null);
                                    setProductCreationQueue([item]);
                                  }}
                                >
                                  Create Pantry product
                                </button>
                              ) : (
                                <span className="helper-text">
                                  A household admin must create the Pantry product before this item can be reconciled.
                                </span>
                              )
                            ) : null}
                          </div>
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        ) : null}

        <section className="panel">
          <div className="inventory-header">
            <div className="stack compact-stack">
              <p className="eyebrow">History</p>
              <h2 className="section-heading">Shopping history</h2>
              <p className="helper-text">
                Historic trips now live in a dedicated view so active reconciliation stays compact.
              </p>
            </div>
            <Link
              href={`/app/households/${householdExternalId}/shopping-list/history`}
              className="secondary-link compact-link"
            >
              Open history
            </Link>
          </div>
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

      {productCreationItem ? (
        <PantryProductDialog
          householdExternalId={householdExternalId}
          mode="create"
          title="Create Pantry product"
          description="Create the missing Pantry product with the full product fields, then return to reconciliation."
          submitLabel="Create product"
          initialValues={{
            name: productCreationItem.label,
            defaultUnit:
              getDraftForItem(productCreationItem).unit ||
              productCreationItem.unit ||
              productCreationItem.requested_unit ||
              "count",
            aliases: [],
            barcodes: [],
            notes: getDraftForItem(productCreationItem).note || productCreationItem.note,
            manualIngredientTags: [],
          }}
          contextSummary={{
            quantitySummary: buildPurchasedSummary(productCreationItem, getDraftForItem(productCreationItem)),
            pantryLocationSummary: buildLocationSummary(
              productCreationItem,
              locations,
              getDraftForItem(productCreationItem),
            ),
            note: getDraftForItem(productCreationItem).note || productCreationItem.note,
          }}
          onCompleted={async (product) => {
            await handleProductCreationCompleted(product.external_id, productCreationItem);
          }}
          onClose={() => {
            setProductCreationQueue([]);
            setQueuedBulkAction(null);
          }}
        />
      ) : null}

      {selectedPendingList && isFinishTripDialogOpen ? (
        <ShoppingTripFinishDialog
          tripName={selectedPendingList.name}
          unresolvedItemCount={unresolvedPendingItems.length}
          pending={pending}
          onConfirm={async (action) => {
            await finalizeSelectedPendingList(action);
          }}
          onClose={() => setIsFinishTripDialogOpen(false)}
        />
      ) : null}
    </>
  );
}
