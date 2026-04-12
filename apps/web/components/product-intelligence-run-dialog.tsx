"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  PantryCatalogProductSummary,
  ProductIntelligenceRunResponse,
  ProductIntelligenceStatusResponse
} from "../lib/api-types";
import {
  getAIProviderSupport,
  normalizeAIProviderType,
} from "../lib/ai-provider-config";
import { getFromApi, postToApi } from "../lib/client-api";
import { ModalShell } from "./modal-shell";

type ProductIntelligenceRunDialogProps = {
  householdExternalId: string;
  catalogProducts: PantryCatalogProductSummary[];
  onClose: () => void;
};

type RunMode = "all" | "product" | "unclassified";

const ACTIVE_RUN_STATUSES = new Set(["queued", "running"]);

function formatRunDate(value: string | null) {
  if (!value) {
    return "Waiting for worker";
  }
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short"
  });
}

function formatRunLabel(status: string) {
  if (status === "queued") {
    return "Queued";
  }
  if (status === "running") {
    return "Running";
  }
  if (status === "partially_completed") {
    return "Partially completed";
  }
  if (status === "completed") {
    return "Completed";
  }
  if (status === "failed") {
    return "Failed";
  }
  return status;
}

export function ProductIntelligenceRunDialog({
  householdExternalId,
  catalogProducts,
  onClose
}: ProductIntelligenceRunDialogProps) {
  const [status, setStatus] = useState<ProductIntelligenceStatusResponse | null>(null);
  const [currentRun, setCurrentRun] = useState<ProductIntelligenceRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<RunMode>("unclassified");
  const [query, setQuery] = useState("");
  const [selectedProductExternalId, setSelectedProductExternalId] = useState("");
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  const progressPercent = useMemo(() => {
    if (!currentRun || currentRun.total_candidates <= 0) {
      return 0;
    }
    return Math.min(
      Math.round((currentRun.processed_count / currentRun.total_candidates) * 100),
      100
    );
  }, [currentRun]);

  const activeRunInProgress = currentRun ? ACTIVE_RUN_STATUSES.has(currentRun.status) : false;
  const normalizedProviderType = normalizeAIProviderType(status?.provider_type);
  const providerSupport = normalizedProviderType ? getAIProviderSupport(normalizedProviderType) : null;

  useEffect(() => {
    let isCancelled = false;

    async function loadStatus() {
      setIsLoadingStatus(true);
      setError(null);
      try {
        const payload = await getFromApi<ProductIntelligenceStatusResponse>(
          `/api/households/${householdExternalId}/product-intelligence/status`
        );
        if (isCancelled) {
          return;
        }
        setStatus(payload);
        setCurrentRun((current) => {
          if (!payload.latest_run) {
            return current && ACTIVE_RUN_STATUSES.has(current.status) ? current : null;
          }
          const latestRun = { ...payload.latest_run, created: false };
          if (!current) {
            return latestRun;
          }
          if (current.external_id === latestRun.external_id) {
            return { ...current, ...latestRun };
          }
          if (ACTIVE_RUN_STATUSES.has(current.status)) {
            return current;
          }
          return latestRun;
        });
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

  useEffect(() => {
    if (!currentRun || !ACTIVE_RUN_STATUSES.has(currentRun.status)) {
      return undefined;
    }

    let isCancelled = false;

    async function pollRun() {
      try {
        const [runPayload, statusPayload] = await Promise.all([
          getFromApi<ProductIntelligenceRunResponse>(
            `/api/households/${householdExternalId}/product-intelligence/runs/${currentRun.external_id}`
          ),
          getFromApi<ProductIntelligenceStatusResponse>(
            `/api/households/${householdExternalId}/product-intelligence/status`
          )
        ]);
        if (isCancelled) {
          return;
        }
        setCurrentRun(runPayload);
        setStatus(statusPayload);
      } catch (pollError) {
        if (!isCancelled) {
          setError(pollError instanceof Error ? pollError.message : "Run status request failed.");
        }
      }
    }

    const intervalId = window.setInterval(() => {
      void pollRun();
    }, 3000);
    void pollRun();

    return () => {
      isCancelled = true;
      window.clearInterval(intervalId);
    };
  }, [currentRun?.external_id, currentRun?.status, householdExternalId]);

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
      setCurrentRun(payload);
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
      description="Run compact, structured AI classification in the background without cluttering the pantry workspace."
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
                {status.latest_run ? (
                  <span className="tag subtle-tag">{formatRunLabel(status.latest_run.status)}</span>
                ) : null}
              </div>
              <p className="helper-text">
                {status.available
                  ? `Scope ${status.classification_scope} · classifier ${status.classification_version} · schema ${status.schema_version}`
                  : status.reason ?? "AI classification is unavailable."}
              </p>
              {providerSupport && !providerSupport.isCurrentlySupported ? (
                <p className="helper-text is-error">{providerSupport.description}</p>
              ) : null}
            </div>

            <section className="modal-form-section">
              <div className="stack compact-stack">
                <h3 className="modal-section-title">Queue classification</h3>
                <p className="helper-text">
                  Classification runs through the worker, stores results batch by batch, and keeps
                  progress visible if you leave the page.
                </p>
              </div>

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

              {activeRunInProgress ? (
                <p className="helper-text">
                  A classification run is already {currentRun?.status}. Use the run monitor below to
                  follow progress.
                </p>
              ) : null}

              <div className="page-actions">
                <button
                  type="button"
                  className="primary-button"
                  disabled={
                    isSubmitting ||
                    !status.available ||
                    activeRunInProgress ||
                    (mode === "product" && !selectedProductExternalId)
                  }
                  onClick={handleRun}
                >
                  {isSubmitting ? "Queueing…" : "Queue classification"}
                </button>
              </div>
            </section>
          </>
        ) : null}

        {currentRun ? (
          <section className="modal-form-section">
            <div className="stack compact-stack">
              <h3 className="modal-section-title">
                {activeRunInProgress ? "Active run" : "Latest run"}
              </h3>
              <p className="helper-text">
                Requested {formatRunDate(currentRun.created_at)} · started{" "}
                {formatRunDate(currentRun.started_at)} · completed {formatRunDate(currentRun.completed_at)}
              </p>
            </div>

            <div className="inline-status-card">
              <div className="tag-row">
                <span className="tag">{formatRunLabel(currentRun.status)}</span>
                <span className="tag subtle-tag">processed {currentRun.processed_count}</span>
                <span className="tag subtle-tag">classified {currentRun.classified_count}</span>
                <span className="tag subtle-tag">skipped {currentRun.skipped_count}</span>
                <span className="tag subtle-tag">failed {currentRun.failed_count}</span>
                <span className="tag subtle-tag">
                  batches {currentRun.completed_batch_count}/{currentRun.batch_count}
                </span>
              </div>
              <div className="run-progress-meter" aria-hidden="true">
                <div className="run-progress-fill" style={{ width: `${progressPercent}%` }} />
              </div>
              <p className="helper-text">
                {progressPercent}% complete · {currentRun.total_candidates} targeted product
                {currentRun.total_candidates === 1 ? "" : "s"}
              </p>
              {currentRun.last_error ? <p className="error-text">{currentRun.last_error}</p> : null}
            </div>

            {currentRun.events.length > 0 ? (
              <div className="stack intelligence-run-list">
                {currentRun.events
                  .slice()
                  .reverse()
                  .map((event, index) => (
                    <div
                      key={`${event.occurred_at}-${event.message}-${index}`}
                      className="intelligence-run-item"
                    >
                      <strong>{event.message}</strong>
                      <span>
                        {event.level}
                        {event.batch_index ? ` · batch ${event.batch_index}` : ""}
                      </span>
                      <span>{formatRunDate(event.occurred_at)}</span>
                    </div>
                  ))}
              </div>
            ) : null}

            {currentRun.items.length > 0 ? (
              <div className="stack intelligence-run-list">
                {currentRun.items
                  .slice()
                  .reverse()
                  .slice(0, 10)
                  .map((item) => (
                    <div key={`${item.product_external_id}-${item.status}`} className="intelligence-run-item">
                      <strong>{item.product_name}</strong>
                      <span>
                        {item.status}
                        {item.batch_index ? ` · batch ${item.batch_index}` : ""}
                        {item.intelligence?.food_category ? ` · ${item.intelligence.food_category}` : ""}
                        {item.stale_before_run ? " · stale before run" : ""}
                      </span>
                      <span>{item.message}</span>
                    </div>
                  ))}
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
    </ModalShell>
  );
}
