"use client";

import Link from "next/link";
import { useState } from "react";
import type { ShoppingListSummary } from "../lib/api-types";
import { formatQuantityWithUnit } from "../lib/quantity-format";

type ShoppingHistoryPanelProps = {
  householdExternalId: string;
  shoppingList: ShoppingListSummary;
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

export function ShoppingHistoryPanel({
  householdExternalId,
  shoppingList,
}: ShoppingHistoryPanelProps) {
  const [expandedListId, setExpandedListId] = useState<string | null>(shoppingList.history_lists[0]?.external_id ?? null);

  return (
    <div className="stack">
      <section className="panel">
        <div className="inventory-header">
          <div className="stack compact-stack">
            <p className="eyebrow">History</p>
            <h1>Shopping history</h1>
            <p className="section-copy">
              Review completed, returned, and merged trips without crowding the active shopping workspace.
            </p>
          </div>
          <Link
            href={`/app/households/${householdExternalId}/shopping-list`}
            className="secondary-link compact-link"
          >
            Back to shopping list
          </Link>
        </div>
        <div className="tag-row">
          <span className="pill">{shoppingList.history_lists.length} trips shown</span>
          <span className="pill">{shoppingList.pending_lists.length} still awaiting purchase</span>
        </div>
      </section>

      {shoppingList.history_lists.length === 0 ? (
        <section className="panel">
          <div className="empty-state">
            <p>Finished, returned, and merged shopping trips will appear here.</p>
          </div>
        </section>
      ) : (
        <section className="stack">
          {shoppingList.history_lists.map((list) => {
            const isExpanded = expandedListId === list.external_id;
            return (
              <article key={list.external_id} className="panel shopping-history-card">
                <div className="shopping-item-row-main">
                  <div className="stack compact-stack">
                    <strong>{list.name}</strong>
                    <p className="helper-text">
                      {list.lifecycle_state.replaceAll("_", " ")} · {list.item_count} items
                    </p>
                    <p className="helper-text">
                      {list.reconciled_at ? `Finished ${formatDateTime(list.reconciled_at)}` : `Updated ${formatDateTime(list.generated_at)}`}
                    </p>
                  </div>
                  <div className="tag-row">
                    {list.purchased_item_count > 0 ? <span className="pill">{list.purchased_item_count} purchased</span> : null}
                    {list.not_purchased_item_count > 0 ? <span className="pill">{list.not_purchased_item_count} returned</span> : null}
                    <button
                      type="button"
                      className="ghost-button compact-button"
                      onClick={() => setExpandedListId(isExpanded ? null : list.external_id)}
                    >
                      {isExpanded ? "Hide items" : "Show items"}
                    </button>
                  </div>
                </div>

                {isExpanded ? (
                  <div className="shopping-history-item-list">
                    {list.items.map((item) => (
                      <article key={item.external_id} className="shopping-history-item-row">
                        <div className="stack compact-stack">
                          <strong>{item.product_name ?? item.label}</strong>
                          <p className="helper-text">
                            Requested {formatQuantityWithUnit(item.requested_quantity, item.requested_unit, "None")} · Final {formatQuantityWithUnit(item.quantity, item.unit, "None")}
                          </p>
                          {item.note ? <p className="helper-text">{item.note}</p> : null}
                        </div>
                        <div className="tag-row">
                          <span className="pill">{item.status.replaceAll("_", " ")}</span>
                          {item.product_external_id === null ? <span className="pill is-warning">New product</span> : null}
                        </div>
                      </article>
                    ))}
                  </div>
                ) : null}
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}
