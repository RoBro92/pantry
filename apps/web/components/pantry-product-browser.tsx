"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  PantryLocationSummary,
  PantryProductSummary,
} from "../lib/api-types";
import { postToApi } from "../lib/client-api";
import { PantryLotActions } from "./pantry-lot-actions";
import { ProductEnrichmentDetails } from "./product-enrichment-details";

type PantryProductBrowserProps = {
  householdExternalId: string;
  products: PantryProductSummary[];
  locations: PantryLocationSummary[];
};

function formatDateLabel(value: string | null) {
  if (!value) {
    return "Not set";
  }
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-GB", {
    dateStyle: "medium",
  });
}

function formatExpirySummary(product: PantryProductSummary) {
  if (product.near_expiry_lot_count > 0 && product.nearest_expiry_on) {
    return `Near expiry · ${formatDateLabel(product.nearest_expiry_on)}`;
  }
  if (product.nearest_expiry_on) {
    return `Next expiry · ${formatDateLabel(product.nearest_expiry_on)}`;
  }
  return product.stock_status === "out_of_stock" ? "Out of stock" : "No dated lots";
}

export function PantryProductBrowser({
  householdExternalId,
  products,
  locations,
}: PantryProductBrowserProps) {
  const router = useRouter();
  const [view, setView] = useState<"table" | "list">("table");
  const [expandedProductId, setExpandedProductId] = useState<string | null>(
    products[0]?.product_external_id ?? null,
  );
  const [shoppingPendingProductId, setShoppingPendingProductId] = useState<string | null>(null);

  useEffect(() => {
    if (products.some((product) => product.product_external_id === expandedProductId)) {
      return;
    }
    setExpandedProductId(products[0]?.product_external_id ?? null);
  }, [expandedProductId, products]);

  async function addToShoppingList(product: PantryProductSummary) {
    setShoppingPendingProductId(product.product_external_id);
    try {
      await postToApi(`/api/households/${householdExternalId}/shopping-list/items`, {
        product_external_id: product.product_external_id,
        source_type: product.stock_status === "out_of_stock" ? "pantry_depleted" : "pantry_product",
      });
      router.refresh();
    } finally {
      setShoppingPendingProductId(null);
    }
  }

  function renderProductDetail(product: PantryProductSummary) {
    return (
      <div className="inventory-detail-grid">
        <div className="inventory-context-card">
          <div className="inventory-context-header">
            <div className="stack compact-stack">
              <strong>{product.product_name}</strong>
              <p className="helper-text">
                {product.stock_status === "out_of_stock"
                  ? "This product record is still available even though no active stock lots remain."
                  : `${product.total_quantity} ${product.unit} across ${product.lot_count} active lot${product.lot_count === 1 ? "" : "s"}.`}
              </p>
            </div>
            <div className="tag-row">
              <span className={`pill${product.stock_status === "out_of_stock" ? " is-warning" : ""}`}>
                {product.stock_status === "out_of_stock" ? "Out of stock" : "In stock"}
              </span>
              {product.enrichment ? <span className="pill">Open Food Facts</span> : null}
              {product.is_in_shopping_list ? <span className="pill">On shopping list</span> : null}
            </div>
          </div>

          <div className="inventory-meta-grid">
            <div>
              <dt>Rooms</dt>
              <dd>{product.room_summary}</dd>
            </div>
            <div>
              <dt>Storage</dt>
              <dd>{product.storage_summary}</dd>
            </div>
            <div>
              <dt>Aliases</dt>
              <dd>{product.aliases.length > 0 ? product.aliases.join(", ") : "None"}</dd>
            </div>
            <div>
              <dt>Barcodes</dt>
              <dd>{product.barcodes.length > 0 ? product.barcodes.join(", ") : "None"}</dd>
            </div>
            <div>
              <dt>Manual ingredients</dt>
              <dd>
                {product.manual_ingredient_tags.length > 0
                  ? product.manual_ingredient_tags.join(", ")
                  : "None"}
              </dd>
            </div>
            <div>
              <dt>Expiry</dt>
              <dd>{formatExpirySummary(product)}</dd>
            </div>
          </div>

          {product.locations.length > 0 ? (
            <div className="inventory-location-breakdown">
              <strong>Location breakdown</strong>
              <ul className="detail-list">
                {product.locations.map((location) => (
                  <li key={location.location_external_id}>
                    <strong>
                      {location.location_group_name} / {location.location_name}
                    </strong>
                    <span>
                      {location.total_quantity} {product.unit} across {location.lot_count} lot
                      {location.lot_count === 1 ? "" : "s"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="page-actions inventory-actions">
            <button
              type="button"
              className="ghost-button"
              disabled={product.is_in_shopping_list || shoppingPendingProductId === product.product_external_id}
              onClick={() => void addToShoppingList(product)}
            >
              {product.is_in_shopping_list
                ? "Already on shopping list"
                : shoppingPendingProductId === product.product_external_id
                  ? "Adding..."
                  : "Add to shopping list"}
            </button>
          </div>

          {product.enrichment ? (
            <ProductEnrichmentDetails
              enrichment={product.enrichment}
              title="Linked enrichment"
              subtitle="Open Food Facts stays attached as enrichment context. Pantry keeps product identity, aliases, and stock ownership."
            />
          ) : null}
        </div>

        <div className="inventory-lot-stack">
          <div className="inventory-context-header">
            <div className="stack compact-stack">
              <strong>Stock lots</strong>
              <p className="helper-text">
                {product.stock_lots.length > 0
                  ? "Each stock lot stays editable without duplicating the product row."
                  : "No active stock lots remain for this product."}
              </p>
            </div>
          </div>

          {product.stock_lots.length === 0 ? (
            <div className="empty-state">
              <p>Add a new lot when this product comes back into stock.</p>
            </div>
          ) : (
            <div className="pantry-lot-list">
              {product.stock_lots.map((lot) => (
                <article
                  key={lot.external_id}
                  className="pantry-lot-card"
                  data-testid={`stock-lot-card-${lot.external_id}`}
                >
                  <div className="pantry-lot-card-summary">
                    <div className="stack compact-stack">
                      <strong>
                        {lot.quantity} {lot.unit}
                      </strong>
                      <p className="helper-text">
                        {lot.location_group_name} / {lot.location_name}
                      </p>
                    </div>
                    <div className="tag-row">
                      {lot.is_near_expiry ? <span className="pill is-warning">Near expiry</span> : null}
                      {lot.is_depleted ? <span className="pill is-warning">Depleted</span> : null}
                    </div>
                  </div>
                  <dl className="lot-meta-grid">
                    <div>
                      <dt>Purchased</dt>
                      <dd>{formatDateLabel(lot.purchased_on)}</dd>
                    </div>
                    <div>
                      <dt>Expiry</dt>
                      <dd>{formatDateLabel(lot.expires_on)}</dd>
                    </div>
                    <div>
                      <dt>Notes</dt>
                      <dd>{lot.note ?? "None"}</dd>
                    </div>
                  </dl>
                  <PantryLotActions
                    householdExternalId={householdExternalId}
                    lotExternalId={lot.external_id}
                    quantity={lot.quantity}
                    currentLocationExternalId={lot.location_external_id}
                    locations={locations}
                  />
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <section className="panel">
        <div className="inventory-header">
          <div className="stack compact-stack">
            <p className="eyebrow">Inventory</p>
            <h2>No matching products</h2>
          </div>
        </div>
        <div className="empty-state">
          <p>Try a different search, clear a filter, or add a new product and stock lot.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="inventory-header">
        <div className="stack compact-stack">
          <p className="eyebrow">Inventory</p>
          <h2>Products</h2>
          <p className="section-copy">
            One row per product, with stock-lot detail available on demand.
          </p>
        </div>
        <div className="view-toggle" role="tablist" aria-label="Inventory view">
          <button
            type="button"
            className={view === "table" ? "primary-button compact-button" : "ghost-button compact-button"}
            onClick={() => setView("table")}
          >
            Table
          </button>
          <button
            type="button"
            className={view === "list" ? "primary-button compact-button" : "ghost-button compact-button"}
            onClick={() => setView("list")}
          >
            List
          </button>
        </div>
      </div>

      {view === "table" ? (
        <div className="table-wrap pantry-table-wrap">
          <table className="data-table pantry-inventory-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Total</th>
                <th>Stored in</th>
                <th>Expiry</th>
                <th>Status</th>
                <th>Detail</th>
              </tr>
            </thead>
            {products.map((product) => {
              const isExpanded = expandedProductId === product.product_external_id;
              return (
                <tbody
                  key={product.product_external_id}
                  data-testid={`product-card-${product.product_external_id}`}
                >
                  <tr>
                    <td>
                      <div className="inventory-product-cell">
                        <strong>{product.product_name}</strong>
                        <span>
                          {product.enrichment ? "Open Food Facts linked" : "User-owned product record"}
                        </span>
                      </div>
                    </td>
                    <td>
                      {product.stock_status === "out_of_stock"
                        ? "Out of stock"
                        : `${product.total_quantity} ${product.unit} · ${product.lot_count} lot${product.lot_count === 1 ? "" : "s"}`}
                    </td>
                    <td>
                      <div className="inventory-product-cell">
                        <strong>{product.room_summary}</strong>
                        <span>{product.storage_summary}</span>
                      </div>
                    </td>
                    <td>{formatExpirySummary(product)}</td>
                    <td>
                      <div className="tag-row">
                        {product.near_expiry_lot_count > 0 ? (
                          <span className="pill is-warning">Near expiry</span>
                        ) : null}
                        {product.enrichment ? <span className="pill">Enriched</span> : null}
                        <span className={`pill${product.stock_status === "out_of_stock" ? " is-warning" : ""}`}>
                          {product.stock_status === "out_of_stock" ? "Out of stock" : "In stock"}
                        </span>
                        {product.is_in_shopping_list ? <span className="pill">Shopping</span> : null}
                      </div>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="ghost-button compact-button"
                        onClick={() =>
                          setExpandedProductId(isExpanded ? null : product.product_external_id)
                        }
                      >
                        {isExpanded ? "Hide" : "Show"}
                      </button>
                    </td>
                  </tr>
                  {isExpanded ? (
                    <tr className="inventory-expanded-row">
                      <td colSpan={6}>{renderProductDetail(product)}</td>
                    </tr>
                  ) : null}
                </tbody>
              );
            })}
          </table>
        </div>
      ) : (
        <div className="inventory-list">
          {products.map((product) => {
            const isExpanded = expandedProductId === product.product_external_id;
            return (
              <article
                key={product.product_external_id}
                className="inventory-list-card"
                data-testid={`product-card-${product.product_external_id}`}
              >
                <div className="inventory-list-summary">
                  <div className="stack compact-stack">
                    <h3>{product.product_name}</h3>
                    <p className="helper-text">
                      {product.stock_status === "out_of_stock"
                        ? "Out of stock"
                        : `${product.total_quantity} ${product.unit} · ${product.lot_count} lot${product.lot_count === 1 ? "" : "s"}`}
                    </p>
                  </div>
                  <div className="tag-row">
                    {product.near_expiry_lot_count > 0 ? <span className="pill is-warning">Near expiry</span> : null}
                    {product.enrichment ? <span className="pill">Enriched</span> : null}
                  </div>
                </div>
                <p className="helper-text">{product.storage_summary}</p>
                <button
                  type="button"
                  className="ghost-button compact-button"
                  onClick={() => setExpandedProductId(isExpanded ? null : product.product_external_id)}
                >
                  {isExpanded ? "Hide detail" : "Show detail"}
                </button>
                {isExpanded ? renderProductDetail(product) : null}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
