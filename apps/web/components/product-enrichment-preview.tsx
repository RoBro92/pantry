"use client";

import type { PantryEnrichmentPreviewResponse } from "../lib/api-types";
import { ProductEnrichmentDetails } from "./product-enrichment-details";

type ProductEnrichmentPreviewProps = {
  preview: PantryEnrichmentPreviewResponse;
  selectedSourceProductId: string | null;
  onSelect: (sourceProductId: string) => void;
  onClearSelection: () => void;
};

export function ProductEnrichmentPreview({
  preview,
  selectedSourceProductId,
  onSelect,
  onClearSelection,
}: ProductEnrichmentPreviewProps) {
  if (preview.candidates.length === 0) {
    return preview.status === "matched" ? null : (
      <div className={preview.status === "unavailable" ? "warning-callout" : "info-callout"}>
        <strong>Product details lookup</strong>
        <p>{preview.message}</p>
      </div>
    );
  }

  return (
    <section className="stack">
      <div className="info-callout">
        <strong>Open Food Facts preview</strong>
        <p>{preview.message}</p>
      </div>

      <div className="enrichment-preview-list">
        {preview.candidates.map((candidate) => {
          const isSelected = candidate.source_product_id === selectedSourceProductId;
          return (
            <ProductEnrichmentDetails
              key={candidate.source_product_id}
              enrichment={candidate}
              subtitle={
                candidate.match_confidence
                  ? `Estimated match confidence ${(candidate.match_confidence * 100).toFixed(0)}%.`
                  : null
              }
            >
              {candidate.warnings.length > 0 ? (
                <ul className="detail-list">
                  {candidate.warnings.map((warning) => (
                    <li key={warning}>
                      <span>{warning}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
              <div className="page-actions">
                <button
                  type="button"
                  className={isSelected ? "ghost-button" : "primary-button"}
                  onClick={() => (isSelected ? onClearSelection() : onSelect(candidate.source_product_id))}
                >
                  {isSelected ? "Selected for save" : "Use this match"}
                </button>
                {isSelected ? (
                  <button type="button" className="ghost-button" onClick={onClearSelection}>
                    Skip enrichment
                  </button>
                ) : null}
              </div>
            </ProductEnrichmentDetails>
          );
        })}
      </div>
    </section>
  );
}
