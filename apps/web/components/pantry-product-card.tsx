import type { PantryLocationSummary, PantryProductSummary } from "../lib/api-types";
import { PantryLotActions } from "./pantry-lot-actions";

type PantryProductCardProps = {
  householdExternalId: string;
  product: PantryProductSummary;
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

export function PantryProductCard({
  householdExternalId,
  product,
  locations,
}: PantryProductCardProps) {
  return (
    <article
      className="pantry-product-card"
      data-testid={`product-card-${product.product_external_id}`}
    >
      <div className="pantry-product-card-header">
        <div className="stack compact-stack">
          <h2>{product.product_name}</h2>
          <p className="section-copy">
            {product.total_quantity} {product.unit} across {product.lot_count} lot
            {product.lot_count === 1 ? "" : "s"}.
          </p>
        </div>
        <div className="tag-row">
          {product.aliases.map((alias) => (
            <span key={alias} className="tag">
              {alias}
            </span>
          ))}
        </div>
      </div>

      <div className="pantry-product-card-metadata">
        <div className="pantry-product-location-summary">
          <strong>Stored in</strong>
          <ul className="detail-list">
            {product.locations.map((location) => (
              <li key={location.location_external_id}>
                <strong>
                  {location.location_group_name} / {location.location_name}
                </strong>
                <span>
                  {location.total_quantity} {product.unit} in {location.lot_count} lot
                  {location.lot_count === 1 ? "" : "s"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="pantry-lot-list" data-testid={`product-card-${product.product_external_id}`}>
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
              {lot.is_near_expiry ? <span className="pill is-warning">Near expiry</span> : null}
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
              currentLocationExternalId={lot.location_external_id}
              locations={locations}
            />
          </article>
        ))}
      </div>
    </article>
  );
}
