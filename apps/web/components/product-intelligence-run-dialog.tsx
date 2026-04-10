"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  PantryCatalogProductSummary,
  ProductIntelligenceRunResponse,
  ProductIntelligenceStatusResponse
} from "../lib/api-types";
import { getFromApi, postToApi } from "../lib/client-api";
import { ModalShell } from "./modal-shell";

type ProductIntelligenceRunDialogProps = {
  householdExternalId: string;
  catalogProducts: PantryCatalogProductSummary[];
  onClose: () => void;
};

type RunMode = "all" | "product" | "unclassified";

function formatRunDate(value: string) {
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short"
  });
}

export function ProductIntelligenceRunDialog({
  householdExternalId,
  catalogProducts,
  onClose
}: ProductIntelligenceRunDialogProps) {
  const [status, setStatus] = useState<ProductIntelligenceStatusResponse | null>(null);
  const [result, setResult] = useState<ProductIntelligenceRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<RunMode>("unclassified");
  const [query, setQuery] = useState("");
  const [selectedProductExternalId, setSelectedProductExternalId] = useState("");
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    async function loadStatus() {
      setIsLoadingStatus(true);
      setError(null);
      try {
        const payload = await getFromApi<ProductIntelligenceStatusResponse>(
          `/api/households/${householdExternalId}/product-intelligence/status`
        );
        if (!isCancelled) {
          setStatus(payload);
        }
      } catch (loadError) {
        if (!isCancelled) {
          setError(loadError instanceof Error ? loadError.message : "Status request failed.");
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingStatus(false);
        }
      }
    }

    void loadStatus();
    return () => {
      isCancelled = true;
    };
  }, [householdExternalId]);

  const filteredProducts = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return catalogProducts;
    }
    return catalogProducts.filter((product) =>
      [
        product.name,
        ...product.aliases,
        ...product.barcodes,
        ...(product.intelligence?.ingredient_families ?? [])
      ].some((value) => value.toLowerCase().includes(normalizedQuery))
    );
  }, [catalogProducts, query]);

  async function handleRun() {
    setIsSubmitting(true);
    setError(null);
    try {
      const payload = await postToApi<ProductIntelligenceRunResponse>(
        `/api/households/${householdExternalId}/product-intelligence/classify`,
        {
          mode,
          product_external_id: mode === "product" ? selectedProductExternalId : null
        }
      );
      setResult(payload);
      const nextStatus = await getFromApi<ProductIntelligenceStatusResponse>(
        `/api/households/${householdExternalId}/product-intelligence/status`
      );
      setStatus(nextStatus);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Classification request failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ModalShell
      title="AI Product Intelligence"
      description="Run compact, structured AI classification without adding noise to the main pantry view."
      onClose={onClose}
      panelClassName="modal-panel modal-panel-wide"
    >
      <div className="stack">
        {error ? <p className="error-text">{error}</p> : null}

        {isLoadingStatus ? (
          <p className="helper-text">Loading product intelligence status…</p>
        ) : status ? (
          <>
            <div className="status-grid">
              <article className="status-card">
                <p className="eyebrow">Indexed</p>
                <h2>{String(status.counts.classified_product_count)}</h2>
                <p>Products with structured AI classification attached.</p>
              </article>
              <article className="status-card">
                <p className="eyebrow">Unclassified</p>
                <h2>{String(status.counts.unclassified_product_count)}</h2>
                <p>Products still relying on manual and enrichment fallback data.</p>
              </article>
              <article className="status-card">
                <p className="eyebrow">Stale</p>
                <h2>{String(status.counts.stale_product_count)}</h2>
                <p>Classifications that should be rerun because data or schema changed.</p>
              </article>
            </div>

            <div className="inline-status-card">
              <div className="tag-row">
                <span className="tag">{status.provider_type ?? "No provider"}</span>
                <span className="tag subtle-tag">{status.default_model ?? "No model"}</span>
                <span className="tag subtle-tag">{status.health_status ?? "unknown"}</span>
              </div>
              <p className="helper-text">
                {status.available
                  ? `Scope ${status.classification_scope} · classifier ${status.classification_version} · schema ${status.schema_version}`
                  : status.reason ?? "AI classification is unavailable."}
              </p>
            </div>

            <section className="modal-form-section">
              <h3 className="modal-section-title">Run classification</h3>
              <div className="split-fields">
                <label className="field">
                  <span>Mode</span>
                  <select value={mode} onChange={(event) => setMode(event.target.value as RunMode)}>
                    <option value="unclassified">Classify unclassified only</option>
                    <option value="all">Classify all products</option>
                    <option value="product">Classify one product</option>
                  </select>
                </label>
                {mode === "product" ? (
                  <label className="field">
                    <span>Search product</span>
                    <input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="Sauce, rice, barcode, alias"
                    />
                  </label>
                ) : null}
              </div>

              {mode === "product" ? (
                <label className="field">
                  <span>Product</span>
                  <select
                    value={selectedProductExternalId}
                    onChange={(event) => setSelectedProductExternalId(event.target.value)}
                  >
                    <option value="">Select a product</option>
                    {filteredProducts.map((product) => (
                      <option key={product.external_id} value={product.external_id}>
                        {product.name}
                        {product.intelligence?.food_category ? ` · ${product.intelligence.food_category}` : ""}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}

              <div className="page-actions">
                <button
                  type="button"
                  className="primary-button"
                  disabled={
                    isSubmitting ||
                    !status.available ||
                    (mode === "product" && !selectedProductExternalId)
                  }
                  onClick={handleRun}
                >
                  {isSubmitting ? "Running…" : "Run classification"}
                </button>
              </div>
            </section>
          </>
        ) : null}

        {result ? (
          <section className="modal-form-section">
            <h3 className="modal-section-title">Last run</h3>
            <div className="inline-status-card">
              <p className="helper-text">
                Started {formatRunDate(result.started_at)} · completed {formatRunDate(result.completed_at)}
              </p>
              <div className="tag-row">
                <span className="tag">classified {result.classified_count}</span>
                <span className="tag subtle-tag">skipped {result.skipped_count}</span>
                <span className="tag subtle-tag">failed {result.failed_count}</span>
                {result.stale_reclassified_count > 0 ? (
                  <span className="tag subtle-tag">
                    stale reclassified {result.stale_reclassified_count}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="stack intelligence-run-list">
              {result.items.map((item) => (
                <div key={`${item.product_external_id}-${item.status}`} className="intelligence-run-item">
                  <strong>{item.product_name}</strong>
                  <span>
                    {item.status}
                    {item.intelligence?.food_category ? ` · ${item.intelligence.food_category}` : ""}
                    {item.stale_before_run ? " · stale before run" : ""}
                  </span>
                  <span>{item.message}</span>
                </div>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </ModalShell>
  );
}
