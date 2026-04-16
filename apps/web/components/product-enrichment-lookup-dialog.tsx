"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  PantryEnrichmentPreviewResponse,
  PantryProductSummary,
} from "../lib/api-types";
import { postToApi } from "../lib/client-api";
import { ModalShell } from "./modal-shell";
import { ProductEnrichmentPreview } from "./product-enrichment-preview";

type ProductEnrichmentLookupDialogProps = {
  householdExternalId: string;
  product: PantryProductSummary;
  onClose: () => void;
};

export function ProductEnrichmentLookupDialog({
  householdExternalId,
  product,
  onClose,
}: ProductEnrichmentLookupDialogProps) {
  const router = useRouter();
  const [preview, setPreview] = useState<PantryEnrichmentPreviewResponse | null>(null);
  const [selectedSourceProductId, setSelectedSourceProductId] = useState<string | null>(null);
  const [lookupPending, setLookupPending] = useState(false);
  const [savePending, setSavePending] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedCandidate = useMemo(
    () =>
      preview?.candidates.find(
        (candidate) => candidate.source_product_id === selectedSourceProductId,
      ) ?? null,
    [preview, selectedSourceProductId],
  );

  async function runLookup() {
    setLookupPending(true);
    setError(null);
    setStatusMessage(null);
    try {
      const response = await postToApi<PantryEnrichmentPreviewResponse>(
        `/api/households/${householdExternalId}/pantry/enrichment/preview`,
        {
          product_name: product.product_name,
          barcode: product.barcodes[0] ?? null,
        },
      );
      setPreview(response);
      setSelectedSourceProductId(null);
      setStatusMessage(response.message);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not look up product details.",
      );
    } finally {
      setLookupPending(false);
    }
  }

  async function linkSelectedCandidate() {
    if (!selectedCandidate) {
      setError("Choose an Open Food Facts match first.");
      return;
    }

    setSavePending(true);
    setError(null);
    try {
      await postToApi(
        `/api/households/${householdExternalId}/products/${product.product_external_id}/enrichment`,
        {
          source_name: selectedCandidate.source_name,
          source_product_id: selectedCandidate.source_product_id,
          match_status: selectedCandidate.match_status,
        },
      );
      setStatusMessage("Open Food Facts details linked.");
      router.refresh();
      window.setTimeout(() => onClose(), 250);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Could not link product details.",
      );
    } finally {
      setSavePending(false);
    }
  }

  useEffect(() => {
    void runLookup();
  }, []);

  return (
    <ModalShell
      title={`Lookup product data for ${product.product_name}`}
      description="Pantro keeps the product name, aliases, and stock identity. This only links optional Open Food Facts enrichment."
      onClose={onClose}
      panelClassName="modal-panel modal-panel-wide"
    >
      <div className="stack">
        <div className="page-actions">
          <button
            type="button"
            className="ghost-button"
            disabled={lookupPending || savePending}
            onClick={() => void runLookup()}
          >
            {lookupPending ? "Looking up..." : "Run lookup again"}
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={savePending || !selectedCandidate}
            onClick={() => void linkSelectedCandidate()}
          >
            {savePending ? "Linking..." : "Link selected match"}
          </button>
        </div>

        {error ? <p className="error-text">{error}</p> : null}
        {statusMessage ? <p className="status-note">{statusMessage}</p> : null}

        {preview ? (
          <ProductEnrichmentPreview
            preview={preview}
            selectedSourceProductId={selectedSourceProductId}
            onSelect={setSelectedSourceProductId}
            onClearSelection={() => setSelectedSourceProductId(null)}
          />
        ) : (
          <div className="inline-status-card">
            <strong>Checking Open Food Facts</strong>
            <p className="helper-text">
              Pantro will try the barcode first, then fall back to a product-name search if needed.
            </p>
          </div>
        )}
      </div>
    </ModalShell>
  );
}
