import { LocationQRCodeCard } from "../../../../../components/location-qr-card";
import { PantryActivityFeed } from "../../../../../components/pantry-activity-feed";
import { PantryControls } from "../../../../../components/pantry-controls";
import { PantryProductBrowser } from "../../../../../components/pantry-product-browser";
import {
  getPantryItems,
  getPantrySupportData,
  requireHouseholdAccess
} from "../../../../../lib/server-auth";

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
  const filterParams = {
    q: filters.q ?? null,
    location_group_external_id: filters.location_group_external_id ?? null,
    location_external_id: filters.location_external_id ?? null,
    near_expiry_only:
      filters.near_expiry_only === "true" || filters.near_expiry_only === "1",
    page: filters.page ? Number(filters.page) : null,
    page_size: filters.page_size ? Number(filters.page_size) : null,
  };
  const [supportData, itemList] = await Promise.all([
    getPantrySupportData(householdExternalId),
    getPantryItems(householdExternalId, filterParams),
  ]);

  return (
    <div className="stack pantry-page-stack">
      <PantryControls
        householdExternalId={supportData.household_external_id}
        householdName={supportData.household_name}
        canAdminister={supportData.can_administer}
        locationGroups={supportData.location_groups}
        locations={supportData.locations}
        counts={supportData.counts}
        filters={itemList.filters}
      />

      <PantryProductBrowser
        householdExternalId={supportData.household_external_id}
        products={itemList.products}
        locations={supportData.locations}
        canAdminister={supportData.can_administer}
        page={itemList.page}
        pageSize={itemList.page_size}
        pageCount={itemList.page_count}
        matchedProductCount={itemList.matched_product_count}
        hasActiveFilters={Boolean(
          itemList.filters.q ||
            itemList.filters.location_group_external_id ||
            itemList.filters.location_external_id ||
            itemList.filters.near_expiry_only,
        )}
      />

      <details className="panel compact-disclosure pantry-support-disclosure">
        <summary>Activity and storage QR links</summary>
        <section className="content-grid pantry-support-grid compact-disclosure-body">
          <article className="support-surface">
            <div className="stack compact-stack">
              <h2 className="section-heading">Inventory log</h2>
              <p className="section-copy">Recent household changes for review.</p>
            </div>
            <PantryActivityFeed events={supportData.recent_events} />
          </article>

          <article className="support-surface">
            <div className="stack compact-stack">
              <h2 className="section-heading">Storage QR access</h2>
              <p className="section-copy">Quick links for storage-location views.</p>
            </div>
            {supportData.locations.length === 0 ? (
              <div className="empty-state">
                <p>Create a room and storage location to generate its QR link.</p>
              </div>
            ) : (
              <div className="location-link-grid compact-link-grid">
                {supportData.locations.map((location) => (
                  <LocationQRCodeCard key={location.external_id} location={location} />
                ))}
              </div>
            )}
          </article>
        </section>
      </details>
    </div>
  );
}
