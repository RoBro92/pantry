"use client";

import type { ProductIntelligenceSummary } from "../lib/api-types";

type ProductIntelligenceDetailsProps = {
  intelligence: ProductIntelligenceSummary;
  productName: string;
};

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short"
  });
}

function formatConfidence(value: number | null) {
  if (value === null) {
    return "Not scored";
  }
  return `${Math.round(value * 100)}%`;
}

function humanizeStaleReason(value: string) {
  if (value === "schema_changed") {
    return "Schema changed";
  }
  if (value === "classification_version_changed") {
    return "Classifier changed";
  }
  if (value === "source_product_data_changed") {
    return "Product data changed";
  }
  return value.replaceAll("_", " ");
}

function TagSection({ label, values }: { label: string; values: string[] }) {
  if (values.length === 0) {
    return null;
  }

  return (
    <div className="stack compact-stack">
      <strong>{label}</strong>
      <div className="tag-row">
        {values.map((value) => (
          <span key={`${label}-${value}`} className="tag">
            {value}
          </span>
        ))}
      </div>
    </div>
  );
}

export function ProductIntelligenceDetails({
  intelligence,
  productName
}: ProductIntelligenceDetailsProps) {
  return (
    <article className="intelligence-card">
      <div className="intelligence-card-header">
        <div className="stack compact-stack">
          <strong>AI product intelligence</strong>
          <p className="helper-text">
            Structured classification for {productName}. Pantro keeps the product identity user-owned.
          </p>
        </div>
        <div className="tag-row">
          <span className="pill">{intelligence.food_category ?? "Uncategorised"}</span>
          {intelligence.is_stale ? <span className="pill is-warning">Refresh recommended</span> : null}
        </div>
      </div>

      {intelligence.rationale_short ? (
        <div className={`inline-status-card${intelligence.is_stale ? " is-warning" : ""}`}>
          <strong>Rationale</strong>
          <p>{intelligence.rationale_short}</p>
        </div>
      ) : null}

      <dl className="inventory-meta-grid">
        <div>
          <dt>Primary ingredient</dt>
          <dd>{intelligence.primary_ingredient_type ?? "Not set"}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{formatConfidence(intelligence.confidence)}</dd>
        </div>
        <div>
          <dt>Classified at</dt>
          <dd>{formatDateTime(intelligence.classified_at)}</dd>
        </div>
        <div>
          <dt>Provider</dt>
          <dd>
            {intelligence.source_provider}
            {intelligence.source_model ? ` · ${intelligence.source_model}` : ""}
          </dd>
        </div>
        <div>
          <dt>Classification version</dt>
          <dd>{intelligence.classification_version}</dd>
        </div>
        <div>
          <dt>Schema version</dt>
          <dd>{intelligence.schema_version}</dd>
        </div>
        <div>
          <dt>Product format</dt>
          <dd>{intelligence.structured_metadata.product_format ?? "Not set"}</dd>
        </div>
        <div>
          <dt>Storage profile</dt>
          <dd>{intelligence.structured_metadata.storage_profile ?? "Not set"}</dd>
        </div>
      </dl>

      {intelligence.is_stale ? (
        <div className="stack compact-stack">
          <strong>Staleness</strong>
          <div className="tag-row">
            {intelligence.stale_reasons.map((reason) => (
              <span key={reason} className="tag subtle-tag">
                {humanizeStaleReason(reason)}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <div className="intelligence-section-grid">
        <TagSection label="Ingredient families" values={intelligence.ingredient_families} />
        <TagSection label="Dietary tags" values={intelligence.dietary_tags} />
        <TagSection label="Allergen tags" values={intelligence.allergen_tags} />
        <TagSection label="Recipe roles" values={intelligence.recipe_role_tags} />
        <TagSection label="Substitution groups" values={intelligence.substitution_groups} />
        <TagSection label="Pantro uses" values={intelligence.pantry_use_tags} />
        <TagSection label="Cuisine tags" values={intelligence.structured_metadata.cuisine_tags} />
        <TagSection label="Flavour tags" values={intelligence.structured_metadata.flavour_tags} />
        <TagSection
          label="Preparation tags"
          values={intelligence.structured_metadata.preparation_tags}
        />
      </div>
    </article>
  );
}
