import Link from "next/link";
import { LocationQRCodeCard } from "../../../../../components/location-qr-card";
import { PantryControls } from "../../../../../components/pantry-controls";
import { PantryProductCard } from "../../../../../components/pantry-product-card";
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
          Household role: <strong>{overview.effective_role}</strong>. Browse the pantry as one
          searchable list of products, with each stock lot shown where it is stored.
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
          title="Rooms"
          value={String(overview.counts.location_group_count)}
          detail="High-level spaces such as Kitchen, Garage, or Utility room."
        />
        <StatusCard
          title="Storage Locations"
          value={String(overview.counts.location_count)}
          detail="Shelves, drawers, bins, fridges, or racks inside each room."
        />
        <StatusCard
          title="Products"
          value={String(overview.counts.product_count)}
          detail="Named pantry products that can carry one or more active stock lots."
        />
        <StatusCard
          title="Near Expiry"
          value={String(overview.counts.near_expiry_lot_count)}
          detail="Lots expiring within the next 14 days."
        />
      </section>

      <PantryControls
        householdExternalId={overview.household_external_id}
        canAdminister={overview.can_administer}
        locationGroups={overview.location_groups}
        locations={overview.locations}
        filters={overview.filters}
      />

      <section className="panel">
        <p className="eyebrow">Pantry overview</p>
        <div className="setup-card-toolbar">
          <div className="stack compact-stack">
            <h2>
              {overview.filters.q
                ? `Search results for “${overview.filters.q}”`
                : "Everything currently in the pantry"}
            </h2>
            <p className="section-copy">
              {overview.products.length} product
              {overview.products.length === 1 ? "" : "s"} currently match the active search.
            </p>
          </div>
          {(overview.filters.q ||
            overview.filters.location_group_external_id ||
            overview.filters.location_external_id) ? (
            <Link href={`/app/households/${overview.household_external_id}`} className="secondary-link">
              Clear search
            </Link>
          ) : null}
        </div>
        {overview.products.length === 0 ? (
          <div className="empty-state">
            <p>
              {overview.filters.q ||
              overview.filters.location_group_external_id ||
              overview.filters.location_external_id
                ? "No pantry items match this search yet. Try a different product name or room."
                : "No pantry items have been added yet. Use Add product to create the first item and stock lot."}
            </p>
          </div>
        ) : (
          <div className="pantry-product-list">
            {overview.products.map((product) => (
              <PantryProductCard
                key={product.product_external_id}
                householdExternalId={overview.household_external_id}
                product={product}
                locations={overview.locations}
              />
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <p className="eyebrow">Location QR links</p>
        <p>
          QR codes resolve to an authenticated route for each storage location and use the current
          configured public browser URL.
        </p>
        {overview.locations.length === 0 ? (
          <p>Create a storage location to generate its QR link.</p>
        ) : (
          <div className="location-link-grid">
            {overview.locations.map((location) => (
              <LocationQRCodeCard key={location.external_id} location={location} />
            ))}
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
