import { LocationQRCodeCard } from "../../../../../components/location-qr-card";
import { PantryActivityFeed } from "../../../../../components/pantry-activity-feed";
import { PantryControls } from "../../../../../components/pantry-controls";
import { PantryProductBrowser } from "../../../../../components/pantry-product-browser";
import { getPantryOverview, requireHouseholdAccess } from "../../../../../lib/server-auth";

type PantryPageProps = {
  params: Promise<{
    householdExternalId: string;
  }>;
  searchParams: Promise<{
    q?: string;
    location_group_external_id?: string;
    location_external_id?: string;
    near_expiry_only?: string;
    page?: string;
    page_size?: string;
  }>;
};

export default async function HouseholdPantryPage({
  params,
  searchParams,
}: PantryPageProps) {
  const { householdExternalId } = await params;
  await requireHouseholdAccess(householdExternalId);
  const filters = await searchParams;
  const overview = await getPantryOverview(householdExternalId, {
    q: filters.q ?? null,
    location_group_external_id: filters.location_group_external_id ?? null,
    location_external_id: filters.location_external_id ?? null,
    near_expiry_only:
      filters.near_expiry_only === "true" || filters.near_expiry_only === "1",
    page: filters.page ? Number(filters.page) : null,
    page_size: filters.page_size ? Number(filters.page_size) : null,
  });

  return (
    <div className="stack pantry-page-stack">
      <PantryControls
        householdExternalId={overview.household_external_id}
        householdName={overview.household_name}
        canAdminister={overview.can_administer}
        catalogProducts={overview.catalog_products}
        locationGroups={overview.location_groups}
        locations={overview.locations}
        counts={overview.counts}
        filters={overview.filters}
      />

      <PantryProductBrowser
        householdExternalId={overview.household_external_id}
        catalogProducts={overview.catalog_products}
        products={overview.products}
        locations={overview.locations}
        canAdminister={overview.can_administer}
        page={overview.page}
        pageSize={overview.page_size}
        pageCount={overview.page_count}
        matchedProductCount={overview.matched_product_count}
        hasActiveFilters={Boolean(
          overview.filters.q ||
            overview.filters.location_group_external_id ||
            overview.filters.location_external_id ||
            overview.filters.near_expiry_only,
        )}
      />

      <section className="content-grid pantry-support-grid">
        <article className="panel">
          <div className="stack compact-stack">
            <p className="eyebrow">Recent Activity</p>
            <h2 className="section-heading">Inventory log</h2>
            <p className="section-copy">
              A compact record of product creation, stock changes, enrichment links, and setup
              milestones.
            </p>
          </div>
          <PantryActivityFeed events={overview.recent_events} />
        </article>

        <article className="panel">
          <div className="stack compact-stack">
            <p className="eyebrow">Location Links</p>
            <h2 className="section-heading">Storage QR access</h2>
            <p className="section-copy">
              QR links resolve to the authenticated location view using the current public browser
              URL.
            </p>
          </div>
          {overview.locations.length === 0 ? (
            <div className="empty-state">
              <p>Create a room and storage location to generate its QR link.</p>
            </div>
          ) : (
            <div className="location-link-grid compact-link-grid">
              {overview.locations.map((location) => (
                <LocationQRCodeCard key={location.external_id} location={location} />
              ))}
            </div>
          )}
        </article>
      </section>
    </div>
  );
}
