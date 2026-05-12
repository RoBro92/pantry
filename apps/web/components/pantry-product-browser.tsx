"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { PantryLocationSummary, PantryProductSummary } from "../lib/api-types";
import { formatQuantityWithUnit } from "../lib/quantity-format";
import { PantryLotActions } from "./pantry-lot-actions";
import { PantryProductDeleteDialog } from "./pantry-product-delete-dialog";
import { PantryProductDialog } from "./pantry-product-create-dialog";
import { ProductEnrichmentDetails } from "./product-enrichment-details";
import { ProductEnrichmentLookupDialog } from "./product-enrichment-lookup-dialog";
import { ProductIntelligenceDetails } from "./product-intelligence-details";
import { ProductIntelligenceRunDialog } from "./product-intelligence-run-dialog";
import { ShoppingListAddDialog } from "./shopping-list-add-dialog";
import { StockLotEditorDialog } from "./stock-lot-editor-dialog";

type PantryProductBrowserProps = {
  householdExternalId: string;
  products: PantryProductSummary[];
  locations: PantryLocationSummary[];
  canAdminister: boolean;
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

function renderStatusPills(product: PantryProductSummary) {
  return (
    <div className="pantry-status-pill-pair">
      <span className={`pill${product.near_expiry_lot_count > 0 ? " is-warning" : ""}`}>
        {product.near_expiry_lot_count > 0 ? "Use soon" : "Stored"}
      </span>
      <span className={`pill${product.stock_status === "out_of_stock" ? " is-warning" : ""}`}>
        {product.stock_status === "out_of_stock" ? "Out of stock" : "In stock"}
      </span>
      {product.is_in_shopping_list ? <span className="pill">On shopping list</span> : null}
    </div>
  );
}

function WrappedValue({ children }: { children: string }) {
  return <span className="inventory-wrap-text">{children}</span>;
}

function describeCanonicalSummary(product: PantryProductSummary) {
  if (!product.canonical) {
    return null;
  }

  const matchMethod = product.canonical.match_method.replaceAll("_", " ");
  if (product.canonical.link_status === "verified") {
    return `Verified canonical link to ${product.canonical.canonical_item.name} via ${matchMethod}. Pantro uses this local household identity for deterministic matching and duplicate prevention.`;
  }
  return `Pending canonical proposal for ${product.canonical.canonical_item.name} via ${matchMethod}. This is a local suggestion captured from the product and is not verified canonical truth yet.`;
}

export function PantryProductBrowser({
  householdExternalId,
  products,
  locations,
  canAdminister,
  page,
  pageSize,
  pageCount,
  matchedProductCount,
  hasActiveFilters,
}: PantryProductBrowserProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [expandedProductId, setExpandedProductId] = useState<string | null>(null);
  const [shoppingDialogProduct, setShoppingDialogProduct] = useState<PantryProductSummary | null>(null);
  const [stockLotEditorProduct, setStockLotEditorProduct] = useState<PantryProductSummary | null>(null);
  const [lookupDialogProduct, setLookupDialogProduct] = useState<PantryProductSummary | null>(null);
  const [productIntelligenceProduct, setProductIntelligenceProduct] = useState<PantryProductSummary | null>(null);
  const [productEditorProduct, setProductEditorProduct] = useState<PantryProductSummary | null>(null);
  const [deleteProduct, setDeleteProduct] = useState<PantryProductSummary | null>(null);

  useEffect(() => {
    if (
      expandedProductId === null ||
      products.some((product) => product.product_external_id === expandedProductId)
    ) {
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

  function renderProductActions(product: PantryProductSummary, isExpanded: boolean, compact = false) {
    return (
      <div className={`inventory-row-actions${compact ? " inventory-row-actions-compact" : ""}`}>
        <button
          type="button"
          className="ghost-button compact-button"
          onClick={() =>
            setExpandedProductId(isExpanded ? null : product.product_external_id)
          }
        >
          {isExpanded ? "Hide details" : "Details"}
        </button>
        <button
          type="button"
          className="ghost-button compact-button"
          onClick={() => setStockLotEditorProduct(product)}
        >
          Add lot
        </button>
        <button
          type="button"
          className="ghost-button compact-button"
          disabled={product.is_in_shopping_list}
          onClick={() => setShoppingDialogProduct(product)}
        >
          {product.is_in_shopping_list ? "On shopping list" : "Buy again"}
        </button>
        {canAdminister ? (
          <button
            type="button"
            className="ghost-button compact-button"
            onClick={() => setProductEditorProduct(product)}
          >
            Edit
          </button>
        ) : null}
      </div>
    );
  }

  function renderProductDetail(product: PantryProductSummary, mobile = false) {
    const canonicalSummary = describeCanonicalSummary(product);
    return (
      <div className={`inventory-detail-grid${mobile ? " inventory-detail-grid-compact" : ""}`}>
        <div className="inventory-context-card">
          {!mobile ? (
            <div className="inventory-context-header">
              <div className="stack compact-stack">
                <strong>{product.product_name}</strong>
                <p className="helper-text">
                  {product.stock_status === "out_of_stock"
                    ? "This product record stays available so the household can restock it quickly."
                    : `${formatQuantityWithUnit(product.total_quantity, product.unit)} across ${product.lot_count} active lot${product.lot_count === 1 ? "" : "s"}.`}
                </p>
              </div>
              <div className="tag-row">{renderStatusPills(product)}</div>
            </div>
          ) : null}

          <dl className="inventory-meta-grid">
            <div>
              <dt>Rooms</dt>
              <dd>
                <WrappedValue>{product.room_summary}</WrappedValue>
              </dd>
            </div>
            <div>
              <dt>Storage</dt>
              <dd>
                <WrappedValue>{product.storage_summary}</WrappedValue>
              </dd>
            </div>
            <div>
              <dt>Expiry</dt>
              <dd>{formatExpirySummary(product)}</dd>
            </div>
            <div>
              <dt>Shopping</dt>
              <dd>{product.is_in_shopping_list ? "Already on shopping list" : "Not on shopping list"}</dd>
            </div>
          </dl>

          {product.locations.length > 0 ? (
            <div className="inventory-location-breakdown">
              <strong>Location breakdown</strong>
              <ul className="detail-list">
                {product.locations.map((location) => (
                  <li key={location.location_external_id}>
                    <strong>
                      <WrappedValue>{`${location.location_group_name} / ${location.location_name}`}</WrappedValue>
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

          {!mobile ? renderProductActions(product, true) : null}

          {canonicalSummary ? (
            <div className="inline-status-card">
              <div className="stack compact-stack">
                <strong>
                  {product.canonical?.link_status === "verified" ? "Canonical link" : "Canonical proposal"}
                </strong>
                <p className="helper-text">{canonicalSummary}</p>
              </div>
            </div>
          ) : null}

          {product.notes || product.manual_ingredient_tags.length > 0 || product.aliases.length > 0 ? (
            <details className="compact-disclosure">
              <summary>Product notes and labels</summary>
              <div className="compact-disclosure-body stack">
                {product.notes ? (
                  <div className="stack compact-stack">
                    <strong>Notes</strong>
                    <p className="helper-text">{product.notes}</p>
                  </div>
                ) : null}
                {product.manual_ingredient_tags.length > 0 ? (
                  <div className="stack compact-stack">
                    <strong>Manual ingredients</strong>
                    <p className="helper-text">{product.manual_ingredient_tags.join(", ")}</p>
                  </div>
                ) : null}
                {product.aliases.length > 0 ? (
                  <div className="stack compact-stack">
                    <strong>Aliases</strong>
                    <p className="helper-text">{product.aliases.join(", ")}</p>
                  </div>
                ) : null}
                {product.barcodes.length > 0 ? (
                  <div className="stack compact-stack">
                    <strong>Barcodes</strong>
                    <p className="helper-text">{product.barcodes.join(", ")}</p>
                  </div>
                ) : null}
              </div>
            </details>
          ) : null}

          {product.enrichment ? (
            <details className="compact-disclosure">
              <summary>Open Food Facts details</summary>
              <div className="compact-disclosure-body">
                <ProductEnrichmentDetails
                  enrichment={product.enrichment}
                  title="Linked data"
                />
              </div>
            </details>
          ) : null}

          {product.intelligence ? (
            <details className="compact-disclosure">
              <summary>AI product details</summary>
              <div className="compact-disclosure-body">
                <ProductIntelligenceDetails
                  intelligence={product.intelligence}
                  productName={product.product_name}
                />
              </div>
            </details>
          ) : null}

          {canAdminister ? (
            <details className="compact-disclosure">
              <summary>Product tools</summary>
              <div className="compact-disclosure-body">
                <div className="page-actions inventory-actions">
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => setProductEditorProduct(product)}
                  >
                    Edit product
                  </button>
                  {!product.enrichment ? (
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => setLookupDialogProduct(product)}
                    >
                      Lookup product data
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => setProductIntelligenceProduct(product)}
                  >
                    {product.intelligence?.is_stale
                      ? "Refresh AI product details"
                      : product.intelligence
                        ? "Recheck AI product details"
                        : "Add AI product details"}
                  </button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => setDeleteProduct(product)}
                  >
                    Delete product
                  </button>
                </div>
              </div>
            </details>
          ) : null}
        </div>

        <div className="inventory-lot-stack">
          <div className="inventory-context-header">
            <div className="stack compact-stack">
              <strong>Stock lots</strong>
              <p className="helper-text">
                {product.stock_lots.length > 0
                  ? "Lot actions stay available, but the product summary stays lighter on mobile."
                  : "No active stock lots remain for this product."}
              </p>
            </div>
            <button
              type="button"
              className="primary-button compact-button"
              onClick={() => setStockLotEditorProduct(product)}
            >
              Add lot
            </button>
          </div>

          {product.stock_lots.length === 0 ? (
            <div className="empty-state">
              <p>Add a new lot when this product comes back into stock.</p>
            </div>
          ) : (
            <div className="pantry-lot-list pantry-lot-list-compact">
              {product.stock_lots.map((lot) => (
                <article
                  key={lot.external_id}
                  className="pantry-lot-row pantry-lot-row-compact"
                  data-testid={`stock-lot-card-${lot.external_id}`}
                >
                  <div className="pantry-lot-row-main pantry-lot-row-main-compact">
                    <div className="pantry-lot-row-heading pantry-lot-row-heading-compact">
                      <strong>{formatQuantityWithUnit(lot.quantity, lot.unit)}</strong>
                      <span className="helper-text inventory-wrap-text">
                        {lot.location_group_name} / {lot.location_name}
                      </span>
                      <span className="helper-text">Purchased {formatDateLabel(lot.purchased_on)}</span>
                      <span className="helper-text">Expiry {formatDateLabel(lot.expires_on)}</span>
                      {lot.note ? <span className="helper-text inventory-wrap-text">Note {lot.note}</span> : null}
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

  function renderMobileProductActions(product: PantryProductSummary, isExpanded: boolean) {
    return (
      <div className="inventory-mobile-actions">
        <button
          type="button"
          className="ghost-button compact-button inventory-mobile-action-button"
          onClick={() =>
            setExpandedProductId(isExpanded ? null : product.product_external_id)
          }
        >
          {isExpanded ? "Hide details" : "Details"}
        </button>
        <button
          type="button"
          className="ghost-button compact-button inventory-mobile-action-button"
          onClick={() => setStockLotEditorProduct(product)}
        >
          Add lot
        </button>
        <button
          type="button"
          className="ghost-button compact-button inventory-mobile-action-button"
          disabled={product.is_in_shopping_list}
          onClick={() => setShoppingDialogProduct(product)}
        >
          {product.is_in_shopping_list ? "On list" : "Buy again"}
        </button>
        {canAdminister ? (
          <button
            type="button"
            className="ghost-button compact-button inventory-mobile-action-button"
            onClick={() => setProductEditorProduct(product)}
          >
            Edit
          </button>
        ) : (
          <span className="inventory-mobile-action-spacer" aria-hidden="true" />
        )}
      </div>
    );
  }

  function renderMobileSummary(product: PantryProductSummary) {
    if (product.stock_status === "out_of_stock") {
      return "Out of stock";
    }
    return `${formatQuantityWithUnit(product.total_quantity, product.unit)} · ${product.lot_count} lot${product.lot_count === 1 ? "" : "s"}`;
  }

  function renderMobileMeta(product: PantryProductSummary) {
    return (
      <dl className="inventory-mobile-meta">
        <div>
          <dt>Stored</dt>
          <dd>
            <WrappedValue>{`${product.room_summary} / ${product.storage_summary}`}</WrappedValue>
          </dd>
        </div>
        <div>
          <dt>State</dt>
          <dd>{formatExpirySummary(product)}</dd>
        </div>
      </dl>
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
            <p className="helper-text">
              {hasActiveFilters
                ? `${matchedProductCount} matching product${matchedProductCount === 1 ? "" : "s"}`
                : `${matchedProductCount} product${matchedProductCount === 1 ? "" : "s"} in this pantry`}
            </p>
          </div>
          <span className="pill">{matchedProductCount} results</span>
        </div>
        {renderPagination()}

        <div className="inventory-mobile-list">
          {products.map((product) => {
            const isExpanded = expandedProductId === product.product_external_id;
            return (
              <article
                key={product.product_external_id}
                className="inventory-mobile-card"
                data-testid={`mobile-product-card-${product.product_external_id}`}
              >
                <div className="inventory-mobile-card-header">
                  <div className="stack compact-stack">
                    <h3 className="inventory-product-name">{product.product_name}</h3>
                    <p className="helper-text">{renderMobileSummary(product)}</p>
                  </div>
                  {renderStatusPills(product)}
                </div>

                {renderMobileMeta(product)}

                {renderMobileProductActions(product, isExpanded)}

                {isExpanded ? (
                  <div className="inventory-mobile-detail">{renderProductDetail(product, true)}</div>
                ) : null}
              </article>
            );
          })}
        </div>

        <div className="table-wrap pantry-table-wrap inventory-desktop-table">
          <table className="data-table pantry-inventory-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Total</th>
                <th>Stored in</th>
                <th>Expiry</th>
                <th className="pantry-status-column-heading">Status</th>
                <th>Actions</th>
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
                        <span>
                          {product.stock_status === "out_of_stock"
                            ? "No active stock lots"
                            : `${product.lot_count} active lot${product.lot_count === 1 ? "" : "s"}`}
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
                    <td className="pantry-status-cell">{renderStatusPills(product)}</td>
                    <td>{renderProductActions(product, isExpanded)}</td>
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
        {renderPagination()}
      </section>

      {shoppingDialogProduct ? (
        <ShoppingListAddDialog
          householdExternalId={householdExternalId}
          productExternalId={shoppingDialogProduct.product_external_id}
          productName={shoppingDialogProduct.product_name}
          sourceType={
            shoppingDialogProduct.stock_status === "out_of_stock"
              ? "pantry_depleted"
              : "pantry_product"
          }
          defaultQuantity="1"
          defaultUnit={shoppingDialogProduct.unit}
          defaultLocationExternalId={shoppingDialogProduct.locations[0]?.location_external_id ?? null}
          locations={locations}
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
            locationExternalId:
              stockLotEditorProduct.locations[0]?.location_external_id ?? "",
            purchasedOn: null,
            expiresOn: null,
            note: null,
          }}
          onClose={() => setStockLotEditorProduct(null)}
        />
      ) : null}

      {lookupDialogProduct ? (
        <ProductEnrichmentLookupDialog
          householdExternalId={householdExternalId}
          product={lookupDialogProduct}
          onClose={() => setLookupDialogProduct(null)}
        />
      ) : null}

      {productIntelligenceProduct ? (
        <ProductIntelligenceRunDialog
          householdExternalId={householdExternalId}
          initialMode="product"
          initialProductExternalId={productIntelligenceProduct.product_external_id}
          onClose={() => setProductIntelligenceProduct(null)}
        />
      ) : null}

      {productEditorProduct ? (
        <PantryProductDialog
          householdExternalId={householdExternalId}
          mode="edit"
          title={`Edit ${productEditorProduct.product_name}`}
          description="Update the saved product details without changing stock-lot quantity, location, or expiry."
          submitLabel="Save product"
          initialValues={{
            externalId: productEditorProduct.product_external_id,
            name: productEditorProduct.product_name,
            defaultUnit: productEditorProduct.unit,
            aliases: productEditorProduct.aliases,
            barcodes: productEditorProduct.barcodes,
            notes: productEditorProduct.notes,
            manualIngredientTags: productEditorProduct.manual_ingredient_tags,
          }}
          onClose={() => setProductEditorProduct(null)}
        />
      ) : null}

      {deleteProduct ? (
        <PantryProductDeleteDialog
          householdExternalId={householdExternalId}
          product={deleteProduct}
          onClose={() => setDeleteProduct(null)}
        />
      ) : null}
    </>
  );
}
