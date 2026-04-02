import Link from "next/link";
import { LocationQRCodeCard } from "../../../../../components/location-qr-card";
import { PantryControls } from "../../../../../components/pantry-controls";
import { PantryLotActions } from "../../../../../components/pantry-lot-actions";
import { StatusCard } from "../../../../../components/status-card";
import {
  getNearExpiry,
  getPantryOverview,
  requireSession
} from "../../../../../lib/server-auth";

type PantryPageProps = {
  params: Promise<{
    householdExternalId: string;
  }>;
  searchParams: Promise<{
    q?: string;
    location_group_external_id?: string;
    location_external_id?: string;
  }>;
};

export default async function HouseholdPantryPage({
  params,
  searchParams
}: PantryPageProps) {
  await requireSession();
  const { householdExternalId } = await params;
  const filters = await searchParams;
  const overview = await getPantryOverview(householdExternalId, {
    q: filters.q ?? null,
    location_group_external_id: filters.location_group_external_id ?? null,
    location_external_id: filters.location_external_id ?? null
  });
  const nearExpiry = await getNearExpiry(householdExternalId);

  return (
    <div className="stack">
      <section className="panel">
        <p className="eyebrow">Household Pantry</p>
        <h1>{overview.household_name}</h1>
        <p>
          Household role: <strong>{overview.effective_role}</strong>. Stock totals are aggregated
          from active lots, and lot moves preserve identity when the entire lot moves intact.
        </p>
        <div className="page-actions">
          <Link
            href={`/app/households/${overview.household_external_id}/imports`}
            className="secondary-link"
          >
            View imports
          </Link>
          <Link
            href={`/app/households/${overview.household_external_id}/recipes`}
            className="secondary-link"
            >
            View recipes
          </Link>
          <Link
            href={`/app/households/${overview.household_external_id}/ai`}
            className="secondary-link"
          >
            View AI suggestions
          </Link>
        </div>
      </section>

      <section className="status-grid">
        <StatusCard
          title="Location Groups"
          value={String(overview.counts.location_group_count)}
          detail="Storage zones such as pantry, freezer, garage, or cellar."
        />
        <StatusCard
          title="Locations"
          value={String(overview.counts.location_count)}
          detail="Concrete shelves, drawers, bins, or racks within this household."
        />
        <StatusCard
          title="Products"
          value={String(overview.counts.product_count)}
          detail="Normalized household products with deterministic aliases and barcodes."
        />
        <StatusCard
          title="Near Expiry"
          value={String(overview.counts.near_expiry_lot_count)}
          detail="Lots expiring within the next 14 days."
        />
      </section>

      <section className="panel">
        <p className="eyebrow">Search And Filters</p>
        <form className="filter-form" method="GET">
          <label className="field">
            <span>Search</span>
            <input
              name="q"
              defaultValue={overview.filters.q ?? ""}
              placeholder="Product, alias, barcode, or location"
            />
          </label>
          <label className="field">
            <span>Location group</span>
            <select
              name="location_group_external_id"
              defaultValue={overview.filters.location_group_external_id ?? ""}
            >
              <option value="">All groups</option>
              {overview.location_groups.map((group) => (
                <option key={group.external_id} value={group.external_id}>
                  {group.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Location</span>
            <select
              name="location_external_id"
              defaultValue={overview.filters.location_external_id ?? ""}
            >
              <option value="">All locations</option>
              {overview.locations.map((location) => (
                <option key={location.external_id} value={location.external_id}>
                  {location.location_group_name} / {location.name}
                </option>
              ))}
            </select>
          </label>
          <div className="filter-actions">
            <button type="submit" className="primary-button">
              Apply filters
            </button>
            <Link
              href={`/app/households/${overview.household_external_id}`}
              className="secondary-link"
            >
              Clear
            </Link>
          </div>
        </form>
      </section>

      <PantryControls
        householdExternalId={overview.household_external_id}
        locationGroups={overview.location_groups}
        locations={overview.locations}
        products={overview.catalog_products}
      />

      <section className="panel">
        <p className="eyebrow">Location QR Links</p>
        <p>
          QR codes resolve to an authenticated browser route for each location and use the current
          configured public browser URL.
        </p>
        {overview.locations.length === 0 ? (
          <p>Create a location to generate its QR link.</p>
        ) : (
          <div className="location-link-grid">
            {overview.locations.map((location) => (
              <LocationQRCodeCard key={location.external_id} location={location} />
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <p className="eyebrow">Aggregated Pantry View</p>
        {overview.products.length === 0 ? (
          <p>No active pantry totals match the current filter set.</p>
        ) : (
          <div className="product-list">
            {overview.products.map((product) => (
              <article key={product.product_external_id} className="product-card">
                <div className="product-card-header">
                  <div>
                    <h2>{product.product_name}</h2>
                    <p>
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
                    {product.barcodes.map((barcode) => (
                      <span key={barcode} className="tag subtle-tag">
                        {barcode}
                      </span>
                    ))}
                  </div>
                </div>
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
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <p className="eyebrow">Stock Lots</p>
        {overview.stock_lots.length === 0 ? (
          <p>No active stock lots match the current filter set.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Location</th>
                  <th>Quantity</th>
                  <th>Expiry</th>
                  <th>Note</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {overview.stock_lots.map((lot) => (
                  <tr key={lot.external_id}>
                    <td>{lot.product_name}</td>
                    <td>
                      {lot.location_group_name} / {lot.location_name}
                    </td>
                    <td>
                      {lot.quantity} {lot.unit}
                    </td>
                    <td>{lot.expires_on ?? "None"}</td>
                    <td>{lot.note ?? "None"}</td>
                    <td className="table-action-cell">
                      <PantryLotActions
                        householdExternalId={overview.household_external_id}
                        lotExternalId={lot.external_id}
                        currentLocationExternalId={lot.location_external_id}
                        locations={overview.locations}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="content-grid">
        <article className="panel">
          <p className="eyebrow">Near Expiry</p>
          {nearExpiry.lots.length === 0 ? (
            <p>No active lots expire within the next {nearExpiry.days} days.</p>
          ) : (
            <ul className="detail-list">
              {nearExpiry.lots.map((lot) => (
                <li key={lot.external_id}>
                  <strong>
                    {lot.product_name} · {lot.quantity} {lot.unit}
                  </strong>
                  <span>
                    {lot.location_group_name} / {lot.location_name} · expires {lot.expires_on}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="panel">
          <p className="eyebrow">Recent Activity</p>
          {overview.recent_events.length === 0 ? (
            <p>No pantry activity has been recorded yet.</p>
          ) : (
            <ul className="detail-list">
              {overview.recent_events.map((event) => (
                <li key={event.external_id}>
                  <strong>{event.summary}</strong>
                  <span>
                    {event.actor_display ?? "Unknown actor"} ·{" "}
                    {new Date(event.occurred_at).toLocaleString("en-GB", {
                      dateStyle: "medium",
                      timeStyle: "short"
                    })}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </article>
      </section>
    </div>
  );
}
