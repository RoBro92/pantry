"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import type { ShoppingListSummary } from "../lib/api-types";
import { postToApi } from "../lib/client-api";

type ShoppingListPanelProps = {
  householdExternalId: string;
  shoppingList: ShoppingListSummary;
};

export function ShoppingListPanel({
  householdExternalId,
  shoppingList,
}: ShoppingListPanelProps) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openItems = shoppingList.items.filter((item) => item.status === "open");
  const completedItems = shoppingList.items.filter((item) => item.status === "completed");

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

  async function updateItemStatus(itemExternalId: string, status: "open" | "completed") {
    setPending(true);
    setError(null);
    try {
      await postToApi(
        `/api/households/${householdExternalId}/shopping-list/items/${itemExternalId}/complete`,
        { status },
      );
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not update shopping item.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="inventory-header">
          <div className="stack compact-stack">
            <p className="eyebrow">Shopping List</p>
            <h1>{shoppingList.name}</h1>
            <p className="section-copy">
              Keep depleted pantry products, manual reminders, and future replenishment work in one
              lightweight household list.
            </p>
          </div>
          <div className="tag-row">
            <span className="pill">{shoppingList.open_item_count} open</span>
            <span className="pill">{shoppingList.completed_item_count} completed</span>
          </div>
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
            <p className="eyebrow">Open</p>
            <h2 className="section-heading">Need to buy</h2>
          </div>
          {openItems.length === 0 ? (
            <div className="empty-state">
              <p>No open shopping items right now.</p>
            </div>
          ) : (
            <div className="shopping-item-list">
              {openItems.map((item) => (
                <article key={item.external_id} className="shopping-item-card">
                  <div className="setup-card-toolbar">
                    <div className="stack compact-stack">
                      <strong>{item.product_name ?? item.label}</strong>
                      <p className="helper-text">
                        {item.quantity && item.unit
                          ? `${item.quantity} ${item.unit}`
                          : item.quantity
                            ? item.quantity
                            : "No quantity set"}
                        {item.note ? ` · ${item.note}` : ""}
                      </p>
                    </div>
                    <span className="pill">{item.source_type.replaceAll("_", " ")}</span>
                  </div>
                  <button
                    type="button"
                    className="ghost-button compact-button"
                    disabled={pending}
                    onClick={() => void updateItemStatus(item.external_id, "completed")}
                  >
                    Mark complete
                  </button>
                </article>
              ))}
            </div>
          )}
        </article>

        <article className="panel">
          <div className="stack compact-stack">
            <p className="eyebrow">Completed</p>
            <h2 className="section-heading">Recently handled</h2>
          </div>
          {completedItems.length === 0 ? (
            <div className="empty-state">
              <p>Completed items will accumulate here until the shopping workflow expands.</p>
            </div>
          ) : (
            <div className="shopping-item-list">
              {completedItems.map((item) => (
                <article key={item.external_id} className="shopping-item-card is-muted">
                  <div className="setup-card-toolbar">
                    <div className="stack compact-stack">
                      <strong>{item.product_name ?? item.label}</strong>
                      <p className="helper-text">
                        Completed{" "}
                        {item.completed_at
                          ? new Date(item.completed_at).toLocaleString("en-GB", {
                              dateStyle: "medium",
                              timeStyle: "short",
                            })
                          : "recently"}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="ghost-button compact-button"
                      disabled={pending}
                      onClick={() => void updateItemStatus(item.external_id, "open")}
                    >
                      Reopen
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </article>
      </section>
    </div>
  );
}
