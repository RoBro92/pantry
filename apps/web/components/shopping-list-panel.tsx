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
import { postToApi, putToApi, readApiErrorMessage } from "../lib/client-api";
import { PantryAddEntryDialog } from "./pantry-add-entry-dialog";

type ShoppingListPanelProps = {
  householdExternalId: string;
  shoppingList: ShoppingListSummary;
  locations: PantryLocationSummary[];
  canAdminister: boolean;
};

function formatDateTime(value: string | null) {
  if (!value) {
    return "Not set";
  }
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatQuantity(item: ShoppingListItemSummary) {
  if (item.quantity && item.unit) {
    return `${item.quantity} ${item.unit}`;
  }
  return item.quantity ?? "No quantity set";
}

function isUnresolvedPendingItem(item: ShoppingListItemSummary) {
  return item.status === "awaiting_purchase";
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
  const [productCreationItem, setProductCreationItem] = useState<ShoppingListItemSummary | null>(null);

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
  const unresolvedManualItems = useMemo(
    () =>
      selectedPendingList?.items.filter(
        (item) => isUnresolvedPendingItem(item) && item.product_external_id === null,
      ) ?? [],
    [selectedPendingList],
  );

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

  async function savePendingItem(event: FormEvent<HTMLFormElement>, itemExternalId: string) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setPending(true);
    setError(null);

    try {
      await putToApi(`/api/households/${householdExternalId}/shopping-list/items/${itemExternalId}`, {
        status: String(formData.get("status") ?? "awaiting_purchase"),
        quantity: String(formData.get("quantity") ?? "").trim() || null,
        unit: String(formData.get("unit") ?? "").trim() || null,
        note: String(formData.get("note") ?? "").trim() || null,
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
      const filename =
        disposition.match(/filename="([^"]+)"/)?.[1] ?? "shopping-list.txt";
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

  async function finalizePendingList(listExternalId: string) {
    setPending(true);
    setError(null);
    try {
      await postToApi(
        `/api/households/${householdExternalId}/shopping-list/pending/${listExternalId}/finalize`,
        {},
      );
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not finish reconciling this list.",
      );
    } finally {
      setPending(false);
    }
  }

  async function handleProductCreationCompleted(
    responseProductExternalId: string,
    item: ShoppingListItemSummary,
  ) {
    await postToApi(
      `/api/households/${householdExternalId}/shopping-list/items/${item.external_id}/attach-product`,
      {
        product_external_id: responseProductExternalId,
      },
    );
    await putToApi(`/api/households/${householdExternalId}/shopping-list/items/${item.external_id}`, {
      status: "purchased",
      quantity: item.quantity,
      unit: item.unit,
      note: item.note,
    });

    const nextItem = unresolvedManualItems.find((candidate) => candidate.external_id !== item.external_id);
    if (nextItem) {
      window.setTimeout(() => {
        setProductCreationItem(nextItem);
      }, 400);
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
                Build the active list, export a printable checklist when you are ready to shop, then reconcile the trip line by line.
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

          <form className="shopping-add-form" onSubmit={handleAddItem}>
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
                Items stay here until you export the checklist for an actual shopping trip.
              </p>
            </div>
            {activeItems.length === 0 ? (
              <div className="empty-state">
                <p>No active shopping items right now.</p>
              </div>
            ) : (
              <div className="shopping-item-list">
                {activeItems.map((item) => (
                  <article key={item.external_id} className="shopping-item-card">
                    <div className="setup-card-toolbar">
                      <div className="stack compact-stack">
                        <strong>{item.product_name ?? item.label}</strong>
                        <p className="helper-text">
                          {formatQuantity(item)}
                          {item.note ? ` · ${item.note}` : ""}
                        </p>
                        <p className="helper-text">Added {formatDateTime(item.created_at)}</p>
                      </div>
                      <span className="pill">{item.source_type.replaceAll("_", " ")}</span>
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
              <div className="shopping-item-list">
                {shoppingList.pending_lists.map((list) => (
                  <article
                    key={list.external_id}
                    className={`shopping-item-card${selectedPendingList?.external_id === list.external_id ? " is-selected" : ""}`}
                  >
                    <div className="setup-card-toolbar">
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
                  Update quantities, mark each line as purchased or not purchased, and move cancelled trips back into the active list if needed.
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
                  onClick={() => void finalizePendingList(selectedPendingList.external_id)}
                >
                  Finish reconciliation
                </button>
              </div>
            </div>

            <div className="shopping-reconcile-list">
              {selectedPendingList.items.map((item) => (
                <form
                  key={item.external_id}
                  className="shopping-reconcile-row"
                  onSubmit={(event) => void savePendingItem(event, item.external_id)}
                >
                  <div className="stack compact-stack">
                    <strong>{item.product_name ?? item.label}</strong>
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
                    <span>Qty</span>
                    <input
                      name="quantity"
                      type="number"
                      min="0.001"
                      step="0.001"
                      defaultValue={item.quantity ?? ""}
                    />
                  </label>
                  <label className="field compact">
                    <span>Unit</span>
                    <input name="unit" defaultValue={item.unit ?? ""} />
                  </label>
                  <label className="field compact shopping-reconcile-note">
                    <span>Note</span>
                    <input name="note" defaultValue={item.note ?? ""} />
                  </label>
                  <div className="shopping-reconcile-actions">
                    <button type="submit" className="ghost-button compact-button" disabled={pending}>
                      Save
                    </button>
                    {canAdminister && item.product_external_id === null ? (
                      <button
                        type="button"
                        className="ghost-button compact-button"
                        disabled={locations.length === 0}
                        onClick={() => setProductCreationItem(item)}
                      >
                        Create Pantry product
                      </button>
                    ) : null}
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
            <div className="shopping-item-list">
              {shoppingList.history_lists.map((list) => (
                <article key={list.external_id} className="shopping-item-card is-muted">
                  <div className="setup-card-toolbar">
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

      {productCreationItem ? (
        <PantryAddEntryDialog
          householdExternalId={householdExternalId}
          canAdminister={canAdminister}
          locations={locations}
          title="Create Pantry product"
          description="Create a Pantry product directly from this shopping item, then keep reconciling the trip."
          submitLabel="Create Pantry product"
          initialValues={{
            name: productCreationItem.label,
            quantity: productCreationItem.quantity ?? "1.000",
            unit: productCreationItem.unit ?? "count",
            note: productCreationItem.note ?? "",
            locationExternalId: locations[0]?.external_id ?? "",
          }}
          onCompleted={async (response) => {
            if (!response.product) {
              return;
            }
            await handleProductCreationCompleted(response.product.external_id, productCreationItem);
          }}
          onClose={() => setProductCreationItem(null)}
        />
      ) : null}
    </>
  );
}
