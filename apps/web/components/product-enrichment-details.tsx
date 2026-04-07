"use client";

import type { ReactNode } from "react";
import type {
  PantryEnrichmentCandidate,
  ProductEnrichmentSummary,
} from "../lib/api-types";

type EnrichmentLike = PantryEnrichmentCandidate | ProductEnrichmentSummary;

type ProductEnrichmentDetailsProps = {
  enrichment: EnrichmentLike;
  title?: string;
  subtitle?: string | null;
  children?: ReactNode;
};

function formatSyncedAt(value: string | null) {
  if (!value) {
    return null;
  }
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function summarizeNutrition(enrichment: EnrichmentLike) {
  return enrichment.nutrition_summary
    .slice(0, 6)
    .map((item) => `${item.label} ${item.value}${item.unit ? ` ${item.unit}` : ""}`)
    .join(" · ");
}

function summarizeTags(values: string[]) {
  return values.slice(0, 6).join(", ");
}

export function ProductEnrichmentDetails({
  enrichment,
  title = "Open Food Facts details",
  subtitle,
  children,
}: ProductEnrichmentDetailsProps) {
  const nutritionSummary = summarizeNutrition(enrichment);
  const syncedAt = "last_synced_at" in enrichment ? formatSyncedAt(enrichment.last_synced_at) : null;
  const incompleteFields = "incomplete_fields" in enrichment ? enrichment.incomplete_fields : [];

  return (
    <article className="enrichment-card">
      <div className="enrichment-card-header">
        <div className="stack compact-stack">
          <strong>{title}</strong>
          {subtitle ? <p className="helper-text">{subtitle}</p> : null}
          <p className="helper-text">
            {enrichment.attribution.source_label} · {enrichment.attribution.data_notice}
          </p>
        </div>
        {enrichment.match_status ? <span className="pill">{enrichment.match_status.replaceAll("_", " ")}</span> : null}
      </div>

      <div className="enrichment-layout">
        {enrichment.product_image_url ? (
          <div className="enrichment-image-frame">
            <img
              src={enrichment.product_image_url}
              alt={enrichment.source_product_name ?? "Product preview"}
              className="enrichment-image"
            />
          </div>
        ) : null}

        <div className="stack compact-stack">
          <div className="stack compact-stack">
            <strong>{enrichment.source_product_name ?? "Unnamed Open Food Facts product"}</strong>
            {enrichment.source_barcode ? <span className="helper-text">Barcode: {enrichment.source_barcode}</span> : null}
          </div>

          {enrichment.ingredients_text ? (
            <p className="helper-text">
              <strong>Ingredients:</strong> {enrichment.ingredients_text}
            </p>
          ) : null}

          {enrichment.allergens_text || enrichment.allergen_tags.length > 0 ? (
            <p className="helper-text">
              <strong>Allergens:</strong>{" "}
              {enrichment.allergens_text ?? summarizeTags(enrichment.allergen_tags)}
            </p>
          ) : null}

          {enrichment.traces_text || enrichment.trace_tags.length > 0 ? (
            <p className="helper-text">
              <strong>Traces:</strong> {enrichment.traces_text ?? summarizeTags(enrichment.trace_tags)}
            </p>
          ) : null}

          {nutritionSummary ? (
            <p className="helper-text">
              <strong>Nutrition:</strong> {nutritionSummary}
            </p>
          ) : null}

          {enrichment.labels.length > 0 ? (
            <p className="helper-text">
              <strong>Labels:</strong> {summarizeTags(enrichment.labels)}
            </p>
          ) : null}

          {enrichment.categories.length > 0 ? (
            <p className="helper-text">
              <strong>Categories:</strong> {summarizeTags(enrichment.categories)}
            </p>
          ) : null}

          <div className="tag-row">
            {incompleteFields.map((field) => (
              <span key={field} className="tag">
                Missing {field}
              </span>
            ))}
          </div>

          {syncedAt ? <p className="helper-text">Last synced: {syncedAt}</p> : null}
          {children}
        </div>
      </div>
    </article>
  );
}
