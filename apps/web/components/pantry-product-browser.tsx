"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { PantryLocationSummary, PantryProductSummary } from "../lib/api-types";
import { formatQuantityWithUnit } from "../lib/quantity-format";
import { PantryLotActions } from "./pantry-lot-actions";
import { ProductEnrichmentDetails } from "./product-enrichment-details";
import { ShoppingListAddDialog } from "./shopping-list-add-dialog";
import { StockLotEditorDialog } from "./stock-lot-editor-dialog";

type PantryProductBrowserProps = {
  householdExternalId: string;
  products: PantryProductSummary[];
  locations: PantryLocationSummary[];
  page: number;
  pageSize: number;
  pageCount: number;
  matchedProductCount: number;
  hasActiveFilters: boolean;
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
  page,
  pageSize,
  pageCount,
  matchedProductCount,
  hasActiveFilters,
}: PantryProductBrowserProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [view, setView] = useState<"table" | "list">("table");
  const [expandedProductId, setExpandedProductId] = useState<string | null>(null);
  const [shoppingDialogProduct, setShoppingDialogProduct] = useState<PantryProductSummary | null>(null);
  const [stockLotEditorProduct, setStockLotEditorProduct] = useState<PantryProductSummary | null>(null);

  useEffect(() => {
    if (expandedProductId === null || products.some((product) => product.product_external_id === expandedProductId)) {
      return;
    }
    setExpandedProductId(null);
  }, [expandedProductId, products]);

  function updatePagination(nextPage: number, nextPageSize = pageSize) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", String(nextPage));
    params.set("page_size", String(nextPageSize));
    router.push(`${pathname}?${params.toString()}`, { scroll: false });
  }

  function updatePageSize(nextPageSize: number) {
    updatePagination(1, nextPageSize);
  }

  function renderPagination() {
    if (matchedProductCount <= pageSize) {
      return null;
    }

    const start = matchedProductCount === 0 ? 0 : (page - 1) * pageSize + 1;
    const end = Math.min(page * pageSize, matchedProductCount);
    return (
      <div className="inventory-pagination">
        <p className="helper-text">
          Showing {start}-{end} of {matchedProductCount}
        </p>
        <div className="page-actions">
          <label className="field compact inventory-page-size">
            <span>Page size</span>
            <select value={pageSize} onChange={(event) => updatePageSize(Number(event.target.value))}>
              <option value="10">10</option>
              <option value="25">25</option>
              <option value="50">50</option>
            </select>
          </label>
          <button
            type="button"
            className="ghost-button compact-button"
            disabled={page <= 1}
            onClick={() => updatePagination(page - 1)}
          >
            Previous
          </button>
          <span className="pill">
            Page {page} of {pageCount}
          </span>
          <button
            type="button"
            className="ghost-button compact-button"
            disabled={page >= pageCount}
            onClick={() => updatePagination(page + 1)}
          >
            Next
          </button>
        </div>
      </div>
    );
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
                  ? "This product record still exists even though no active stock lots remain."
                  : `${formatQuantityWithUnit(product.total_quantity, product.unit)} across ${product.lot_count} active lot${product.lot_count === 1 ? "" : "s"}.`}
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
                      {formatQuantityWithUnit(location.total_quantity, product.unit)} across {location.lot_count} lot
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
              disabled={product.is_in_shopping_list}
              onClick={() => setShoppingDialogProduct(product)}
            >
              {product.is_in_shopping_list
                ? "Already on shopping list"
                : "Add to shopping list"}
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={() => setStockLotEditorProduct(product)}
            >
              Add another lot
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
                  ? "Each lot stays editable without fragmenting the product row."
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
                  className="pantry-lot-row"
                  data-testid={`stock-lot-card-${lot.external_id}`}
                >
                  <div className="pantry-lot-row-main">
                    <div className="pantry-lot-row-summary">
                      <div className="stack compact-stack">
                        <div className="pantry-lot-row-heading">
                          <strong>{formatQuantityWithUnit(lot.quantity, lot.unit)}</strong>
                          <span className="helper-text">
                            {lot.location_group_name} / {lot.location_name}
                          </span>
                        </div>
                        {lot.note ? <p className="helper-text">{lot.note}</p> : null}
                      </div>
                      <div className="lot-meta-grid pantry-lot-inline-grid">
                        <div>
                          <dt>Purchased</dt>
                          <dd>{formatDateLabel(lot.purchased_on)}</dd>
                        </div>
                        <div>
                          <dt>Expiry</dt>
                          <dd>{formatDateLabel(lot.expires_on)}</dd>
                        </div>
                      </div>
                    </div>
                    <div className="tag-row">
                      {lot.is_near_expiry ? <span className="pill is-warning">Near expiry</span> : null}
                      {lot.is_depleted ? <span className="pill is-warning">Depleted</span> : null}
                    </div>
                  </div>
                  <PantryLotActions
                    householdExternalId={householdExternalId}
                    lot={lot}
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
    <>
      <section className="panel">
        <div className="inventory-header">
          <div className="stack compact-stack">
            <p className="eyebrow">Inventory</p>
            <h2>Products</h2>
            <p className="section-copy">
              One row per product, with stock-lot detail available on demand.
            </p>
            <p className="helper-text">
              {hasActiveFilters
                ? `${matchedProductCount} matching product${matchedProductCount === 1 ? "" : "s"}`
                : `${matchedProductCount} product${matchedProductCount === 1 ? "" : "s"} in this pantry`}
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
        {renderPagination()}

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
                          <h3 className="inventory-product-name">{product.product_name}</h3>
                          {product.manual_ingredient_tags.length > 0 ? (
                            <span>Manual ingredients: {product.manual_ingredient_tags.join(", ")}</span>
                          ) : null}
                          <span>
                            {product.enrichment ? "Open Food Facts linked" : "User-owned product record"}
                          </span>
                        </div>
                      </td>
                      <td>
                        {product.stock_status === "out_of_stock"
                          ? "Out of stock"
                          : `${formatQuantityWithUnit(product.total_quantity, product.unit)} across ${product.lot_count} lot${product.lot_count === 1 ? "" : "s"}`}
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
                          : `${formatQuantityWithUnit(product.total_quantity, product.unit)} across ${product.lot_count} lot${product.lot_count === 1 ? "" : "s"}`}
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
        {renderPagination()}
      </section>

      {shoppingDialogProduct ? (
        <ShoppingListAddDialog
          householdExternalId={householdExternalId}
          productExternalId={shoppingDialogProduct.product_external_id}
          productName={shoppingDialogProduct.product_name}
          sourceType={
            shoppingDialogProduct.stock_status === "out_of_stock" ? "pantry_depleted" : "pantry_product"
          }
          defaultQuantity="1"
          defaultUnit={shoppingDialogProduct.unit}
          defaultLocationExternalId={shoppingDialogProduct.locations[0]?.location_external_id ?? null}
          onClose={() => setShoppingDialogProduct(null)}
        />
      ) : null}

      {stockLotEditorProduct ? (
        <StockLotEditorDialog
          householdExternalId={householdExternalId}
          locations={locations}
          productExternalId={stockLotEditorProduct.product_external_id}
          mode="create"
          initialValues={{
            productName: stockLotEditorProduct.product_name,
            quantity: "1",
            unit: stockLotEditorProduct.unit,
            locationExternalId: stockLotEditorProduct.locations[0]?.location_external_id ?? "",
            purchasedOn: null,
            expiresOn: null,
            note: null,
          }}
          onClose={() => setStockLotEditorProduct(null)}
        />
      ) : null}
    </>
  );
}
